import logging
import math
import re
from collections.abc import Callable
from functools import cached_property

import pandas as pd
from dateutil.relativedelta import relativedelta
from dateutil.rrule import rrule, DAILY, WEEKLY, MONTHLY, YEARLY

# ruff: noqa: E402
logging.getLogger("darts").setLevel(logging.ERROR)
from darts import TimeSeries
from darts.models import ExponentialSmoothing

from lve_store import LveStore
from constants import CPI_CSV_PATH
from schemas import (
    LvePlanID,
    LveCategory,
    PAY_CATEGORIES,
    LVE_BILL_CATEGORIES,
    LVE_SCHEMA_BY_CATEGORY,
    LVE_DTYPE_BY_CATEGORY,
)


_FREQ = {"Day": DAILY, "Week": WEEKLY, "Month": MONTHLY, "Year": YEARLY}


def wipe_time(ts: pd.Timestamp) -> pd.Timestamp:
    """Drop timezone and time-of-day, keeping only the calendar date."""

    if ts.tz is not None:
        ts = ts.tz_localize(None)
    return ts.normalize()


class LveProjector:
    """Represents a set of data and methods for projecting living expenses."""

    def __init__(
        self,
        plan_id: LvePlanID,
        proj_span: int,
        gst_rate: float,
    ):
        # TODO: Add parameter validations.
        self.plan_id = plan_id
        self.base_date = wipe_time(pd.Timestamp.today())
        self.base_year = self.base_date.year
        self.proj_span = proj_span  # int >= 1.
        self.proj_head = self.base_date + pd.offsets.YearBegin(-1)
        self.proj_tail = self.base_date + pd.offsets.YearEnd(self.proj_span)
        self.gst_rate = gst_rate
        self.gst_mult = 1 + gst_rate

    @cached_property
    def cpi_schedule(self) -> pd.DataFrame:
        """Daily CPI over the projection window, rebased to the current day."""

        historic_cpi = self._load_cpi_data()
        forecast_tail = pd.Timestamp(year=self.proj_tail.year + 1, month=1, day=1)
        forecast_delta = relativedelta(forecast_tail, historic_cpi.index[-1])
        forecast_steps = math.ceil(forecast_delta.years * 12 + forecast_delta.months)

        def forecast(cpi_category: str) -> pd.Series:
            cpi_tseries = TimeSeries.from_series(historic_cpi[cpi_category])
            fitted_model = ExponentialSmoothing(seasonal_periods=12).fit(cpi_tseries)
            return fitted_model.predict(forecast_steps).to_series()

        forecast_cpi = pd.concat(map(forecast, historic_cpi), axis=1)
        windowed_cpi = (
            pd.concat([historic_cpi, forecast_cpi])
            .loc[self.proj_head :]
            .asfreq("D")
            .interpolate("spline", order=4)
            # Drop trailing day: an extra month was forcasted for spline anchoring
            .iloc[:-1]
        )
        cpi_baseline = windowed_cpi.loc[self.base_date]

        return windowed_cpi.div(cpi_baseline)

    @cached_property
    def lve_schedule(self) -> pd.DataFrame:
        """Daily LVEs scaled with inflation over the projection window."""

        # Setup base result and load data
        schedule = pd.DataFrame(0.0, self.cpi_schedule.index, PAY_CATEGORIES, "float64")
        lve_data = self._load_lve_data()

        # Mount data onto result
        for bill_category in LVE_BILL_CATEGORIES:
            bills = lve_data[bill_category]
            find_base_bill_cost = self._base_bill_cost_dispatch()[bill_category]

            for _, bill in bills.iterrows():
                # Extract relevant bill fields
                base_cost = find_base_bill_cost(bill)
                pay_category = bill.get("Pay Category")
                cpi_category = bill.get("CPI Category")
                billing_dates = self._get_bill_dates(bill)

                # Apply cost to schedule, adjusted for inflation when necessary
                # BUG: cpi_category issue: determine what you expect value to be.
                if not cpi_category:
                    schedule.loc[billing_dates, pay_category] += base_cost
                else:
                    cpi_mults = self.cpi_schedule.loc[billing_dates, cpi_category]
                    schedule.loc[billing_dates, pay_category] += base_cost * cpi_mults

        return schedule

    @cached_property
    def lve_by_year(self) -> pd.DataFrame:
        """Yearly LVEs over the projection window, scaled with inflation."""

        result = self.lve_schedule.groupby(self.lve_schedule.index.year).sum()
        result.index.name = "Year"
        return result

    # Private Methods
    # --------------------------------------------------------------------------

    def _load_cpi_data(self) -> pd.DataFrame:
        """Loads monthly CPI data (from local file) into a DataFrame, tz-naive and
        normalized."""

        result = pd.read_csv(
            CPI_CSV_PATH,
            usecols=["REF_DATE", "Products and product groups", "VALUE"],
            parse_dates=["REF_DATE"],
        ).pivot(index="REF_DATE", columns="Products and product groups", values="VALUE")

        suffix_pattern = re.compile(r"\s*\(\d+=\d+\)\s*$")

        result.index = result.index.map(wipe_time)
        result.columns = result.columns.str.replace(suffix_pattern, "", regex=True)
        result.rename_axis(index="Date", columns="CPI Categories", inplace=True)

        # NOTE: Data validation with pandera should be added before returning result.
        return result

    def _load_lve_data(self) -> dict[LveCategory, pd.DataFrame]:
        """Loads LVE plan (on Google Sheets) into a dict, keyed by category."""

        # Setup base result
        result = {
            lve_category: pd.DataFrame(columns=lve_dtype).astype(lve_dtype)
            for lve_category, lve_dtype in LVE_DTYPE_BY_CATEGORY.items()
            if lve_category in LVE_BILL_CATEGORIES
        }
        lve_store = LveStore(self.plan_id)

        # Mount data onto result
        for lve_category in result.keys():
            head_row_found, *data_rows_found = lve_store.get_table(lve_category.value)

            lve_construct = pd.DataFrame(columns=head_row_found, data=data_rows_found)
            if lve_construct.empty:
                continue

            # Validate and mount
            lve_schema = LVE_SCHEMA_BY_CATEGORY[lve_category]
            result[lve_category] = lve_schema.validate(lve_construct)

        return result

    def _get_bill_dates(self, bill: pd.Series) -> pd.DatetimeIndex:
        """Return a Generator of billing dates (timestamps) over the projection window."""
        if self.proj_span == 0:
            return
        start_date = bill.get("Start Date")
        close_date = bill.get("Close Date")
        if pd.isna(start_date):
            return
        if pd.isna(close_date):
            close_date = self.proj_tail
        close_date = min(close_date, self.proj_tail)
        if start_date > self.proj_tail or close_date < self.proj_head:
            return

        period_type = bill.get("Period Type")
        period_size = int(bill.get("Period Size"))
        kwargs = dict(
            freq=_FREQ[period_type],
            dtstart=start_date,
            interval=period_size,
            until=close_date,
        )
        # Only Month/Year bills with a day-of-month of 29-31 are ever ambiguous;
        # roll back to the original day the moment a month has it again,
        # falling back to that month's last day otherwise.
        if period_type in ("Month", "Year") and start_date.day >= 29:
            kwargs["bymonthday"] = (start_date.day, -1)
            kwargs["bysetpos"] = 1
            if period_type == "Year":
                kwargs["bymonth"] = start_date.month

        rule = rrule(**kwargs)
        return pd.DatetimeIndex(rule.between(self.proj_head, self.proj_tail, inc=True))

    def _base_bill_cost_dispatch(self) -> dict[LveCategory, Callable[[pd.Series], float]]:
        """Returns the base cost function for bills under the given bill category."""

        return {
            LveCategory.SERVICES: self._base_plain_bill_cost,
            LveCategory.OBLIGATIONS: self._base_plain_bill_cost,
            LveCategory.NONDURABLES: self._base_usage_bill_cost,
        }

    def _base_plain_bill_cost(self, bill: pd.Series) -> float:
        cost = bill["Period Cost"]
        return cost if not bill["Sales Taxed"] else self._apply_gst(cost)

    def _base_usage_bill_cost(self, bill: pd.Series) -> float:
        cost = bill["Unit Cost"] * bill["Usage Rate"] / bill["Unit Cost Base"]
        return cost if not bill["Sales Taxed"] else self._apply_gst(cost)

    def _apply_gst(self, cost: float) -> float:
        return cost * self.gst_mult

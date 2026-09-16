from collections.abc import Callable
from functools import cached_property
import logging
import re

# ruff: noqa: E402
logging.getLogger("darts").setLevel(logging.ERROR)

from darts import TimeSeries
from darts.models import ExponentialSmoothing
from dateutil.relativedelta import relativedelta
from dateutil.rrule import rrule, DAILY, WEEKLY, MONTHLY, YEARLY
import pandas as pd

from constants import CPI_CSV_PATH
from lve_plan import LvePlan
from schemas import LveBillCategory, PAY_CATEGORIES, LVE_BILL_CATEGORIES


_FREQ = {"Day": DAILY, "Week": WEEKLY, "Month": MONTHLY, "Year": YEARLY}


def wipe_time(ts: pd.Timestamp) -> pd.Timestamp:
    """Drop timezone and time-of-day, keeping only the calendar date."""

    if ts.tz is not None:
        ts = ts.tz_localize(None)
    return ts.normalize()


class LveProjector:
    """Represents a set of data and methods for projecting living expenses."""

    def __init__(self, plan: LvePlan, proj_len: int, gst_rate: float):
        if not isinstance(plan, LvePlan):
            raise TypeError(f"plan must be an LvePlan, got {type(plan).__name__}")

        if not isinstance(proj_len, int) or isinstance(proj_len, bool):
            raise TypeError(f"proj_len to be an int, got {type(proj_len).__name__}")
        if not (1 <= proj_len):
            raise ValueError(f"proj_len to be a positive integer, got {proj_len}")

        if not isinstance(gst_rate, (int, float)) or isinstance(gst_rate, bool):
            raise TypeError(f"gst_rate must be a number, got {type(gst_rate).__name__}")
        if not (0 <= gst_rate < 1):
            raise ValueError(f"gst_rate must be in [0, 1), got {gst_rate}")

        self.lve_plan = plan
        self.proj_len = proj_len
        self.base_date = wipe_time(pd.Timestamp.today())
        self.proj_head = self.base_date + pd.offsets.YearBegin(-1)
        self.proj_tail = self.base_date + pd.offsets.YearEnd(self.proj_len)
        self.gst_rate = gst_rate
        self.gst_mult = 1 + gst_rate

    @cached_property
    def cpi_schedule(self) -> pd.DataFrame:
        """Daily CPI over the projection window, rebased to the current day."""

        historic_cpi = self._load_cpi_data()
        forecast_tail = pd.Timestamp(year=self.proj_tail.year + 1, month=1, day=1)
        forecast_delta = relativedelta(forecast_tail, historic_cpi.index[-1])
        forecast_steps = forecast_delta.years * 12 + forecast_delta.months

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

        # Mount data onto result template
        base_bill_cost_dispatch = self._base_bill_cost_dispatch()
        for bill_category in LVE_BILL_CATEGORIES:
            bill_table = self.lve_plan[bill_category]
            find_base_bill_cost = base_bill_cost_dispatch[bill_category]

            # Apply inflation adjusted billing costs to schedule.
            for _, bill in bill_table.iterrows():
                base_cost = find_base_bill_cost(bill)
                pay_category = bill["Pay Category"]
                cpi_category = bill["CPI Category"]
                billing_dates = self._get_bill_dates(bill)
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

        # TODO: Add data validation with pandera before returning result.
        return result

    def _get_bill_dates(self, bill: pd.Series) -> pd.DatetimeIndex:
        """Return a DatetimeIndex of billing dates over the projection window."""

        start_date = bill.get("Start Date")
        close_date = bill.get("Close Date")
        if pd.isna(start_date):
            return pd.DatetimeIndex([])
        if pd.isna(close_date):
            close_date = self.proj_tail
        close_date = min(close_date, self.proj_tail)
        if start_date > self.proj_tail or close_date < self.proj_head:
            return pd.DatetimeIndex([])

        period_type = bill["Period Type"]
        period_size = int(bill["Period Size"])
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

    def _base_bill_cost_dispatch(
        self,
    ) -> dict[LveBillCategory, Callable[[pd.Series], float]]:
        """Returns the base cost function for bills under the given bill category."""

        return {
            LveBillCategory.SERVICES: self._base_plain_bill_cost,
            LveBillCategory.OBLIGATIONS: self._base_plain_bill_cost,
            LveBillCategory.NONDURABLES: self._base_usage_bill_cost,
        }

    def _base_plain_bill_cost(self, bill: pd.Series) -> float:
        cost = bill["Period Cost"]
        return cost if not bill["Sales Taxed"] else self._apply_gst(cost)

    def _base_usage_bill_cost(self, bill: pd.Series) -> float:
        cost = bill["Unit Cost"] * bill["Usage Rate"] / bill["Unit Cost Base"]
        return cost if not bill["Sales Taxed"] else self._apply_gst(cost)

    def _apply_gst(self, cost: float) -> float:
        return cost * self.gst_mult

from itertools import count, islice
from math import ceil, floor, inf
from typing import Generator, Optional
from dateutil.relativedelta import relativedelta
import pandas as pd
from constants import BILLING_DATE_MIN, BILLING_DATE_MAX
from schemata import PERIOD_TYPES

# BUG: Planned expenses with a start date prior to `BILLING_DATE_MIN` are not included in
#      expense reporting. Inspect `get_billing_date_head()` and related logic to resolve
#      this issue.


# TODO: Reevaluate the design of this class. There are lots of places for errors to arise.
class BillingDater:
    """Helper class for finding billing dates on expenses within a window of time."""

    def __init__(
        self,
        billing_date_min: pd.Timestamp = BILLING_DATE_MIN,
        billing_date_max: pd.Timestamp = BILLING_DATE_MAX,
    ):
        if not isinstance(billing_date_min, pd.Timestamp):
            raise TypeError(
                "Parameter 'billing_date_min' must be a Pandas.TimeStamp, got "
                f"{type(billing_date_min).__name__}."
            )
        if not isinstance(billing_date_max, pd.Timestamp):
            raise TypeError(
                "Parameter 'billing_date_max' must be a Pandas.TimeStamp, got "
                f"{type(billing_date_max).__name__}."
            )
        if billing_date_min > billing_date_max:
            raise ValueError(
                "Parameter 'billing_date_min' cannot exceed 'billing_date_max'."
            )
        self.billing_date_min = billing_date_min
        self.billing_date_max = billing_date_max

    # --------------------------------------------------------------------------
    # Public Methods
    # --------------------------------------------------------------------------

    def get_billing_dates(
        self, expense: pd.Series
    ) -> Generator[pd.Timestamp, None, None]:
        """Return a Timestamp Generator of 'expense' occurrences in the BillingDater's
        window."""
        start_date = self.get_billing_date_head(expense)
        if not start_date:
            return
        period_delta = self._get_period_delta(expense)
        total_periods = expense.get("Periods")
        if total_periods and not pd.api.types.is_integer(total_periods):
            return
        period_counter = islice(count(), total_periods)
        for period_count in period_counter:
            billing_date = start_date + (period_count * period_delta)
            if billing_date > self.billing_date_max:
                return
            yield billing_date

    def get_billing_date_head(self, expense: pd.Series) -> Optional[pd.Timestamp]:
        """Return the first date 'expense' occurs in the BillingDater's window. If
        no such date exists, then None is returned."""
        start_date = expense.get("Start Date")
        if not isinstance(start_date, pd.Timestamp) or start_date > self.billing_date_max:
            return None
        if start_date >= self.billing_date_min:
            return start_date
        total_periods = expense.get("Periods")
        if not pd.api.types.is_integer(total_periods):
            total_periods = inf
        min_periods = ceil(
            self._count_periods(start_date, self.billing_date_min, expense)
        )
        max_periods = floor(
            self._count_periods(start_date, self.billing_date_max, expense)
        )
        if not min_periods or not max_periods:
            return None
        if total_periods < min_periods or min_periods > max_periods:
            return None
        return start_date + (min_periods * self._get_period_delta(expense))

    # ----------------------------------------------------------------------
    # Private Methods
    # ----------------------------------------------------------------------

    def _count_periods(
        self, head_date: pd.Timestamp, tail_date: pd.Timestamp, expense: pd.Series
    ) -> Optional[float]:
        """Return the number of periods from 'expense' fitting between the head and tail
        Timestamps."""
        period_type = expense.get("Period Type")
        if not self._is_valid_period_type(period_type):
            return None
        period_size = expense.get("Period Size")
        if not isinstance(period_size, int):
            return None
        period_counter_by_type = {
            "Year": lambda s, e: relativedelta(e, s).years,
            "Month": lambda s, e: relativedelta(e, s).years + relativedelta(e, s).months,
            "Week": lambda s, e: (e - s).days / 7,
            "Day": lambda s, e: (e - s).days,
        }
        period_counter = period_counter_by_type[period_type]
        return period_counter(head_date, tail_date) / period_size

    def _get_period_delta(self, expense: pd.Series) -> Optional[relativedelta]:
        """Return the relativedelta corresponding to the expense's period data."""
        period_type = expense.get("Period Type")
        if not self._is_valid_period_type(period_type):
            return None
        period_size = expense.get("Period Size")
        if not pd.api.types.is_integer(period_size):
            return None
        period_attribute = f"{period_type.lower()}s"
        return relativedelta(**{period_attribute: period_size})

    def _is_valid_period_type(self, period_type: str) -> bool:
        """Check if the period type is valid."""
        return period_type in PERIOD_TYPES

from calendar import isleap
from collections.abc import Callable
from functools import cache, cached_property
from typing import Union
import numpy as np
import pandas as pd
from scipy.optimize import brentq
from scipy.interpolate import make_interp_spline
from billing_dater import BillingDater
from constants import BASE_YEAR
from schemata import EXPENSE_CATEGORIES, PLANNED_EXPENSE_TYPES
from store import Store, ExpenseSSheetVersion, ExpenseType
from tax_calculator import TaxCalculator, FIT_BRACKETS, SIT_BRACKETS

VALID_COST_TIMELINE_FREQUENCIES = {"ME", "W", "D"}


# TODO: Add parameter validations to methods.
class Calculator:
    """Calculator for cost of living metrics."""

    def __init__(
        self,
        expense_ssheet_version: ExpenseSSheetVersion,
        sales_tax_rate: Union[int, float] = 0.05,
        self_employed: bool = False,
    ):
        self._expense_ssheet_version = expense_ssheet_version
        self._sales_tax_rate = sales_tax_rate
        self._sales_tax_multiplier = 1 + sales_tax_rate
        self._self_employed = self_employed
        self._bill_dater = BillingDater()
        self._tax_calculator = TaxCalculator()
        self._store = Store()

    @property
    def _cpi(self) -> pd.DataFrame:
        return self._store.cpi

    @cached_property
    def _expenses_by_type(self) -> dict[ExpenseType, pd.DataFrame]:
        return self._store.get_expenses(self._expense_ssheet_version)

    # -------------------------------------------------------------------------
    # Public Methods
    # -------------------------------------------------------------------------

    def living_wage_curve(self, this_year: bool = True) -> pd.Series:
        """Return a Series relating weekly hours and living wage."""
        x_min, x_max = 20, 60
        x_known = np.arange(x_min, x_max + 1, 2)
        y_known = [self.living_wage(x, this_year) for x in x_known]
        spline = make_interp_spline(x_known, y_known)
        x_points = np.arange(x_min, x_max + 1, 1)
        return pd.Series(spline(x_points), x_points)

    def living_wage(self, weekly_hours: float, this_year: bool = True) -> float:
        """Compute wage needed to meet all expenses (including tax) in the current or
        following year."""
        base_expense = float(self.years_planned_cost_totals(this_year).sum())
        return self._living_income(base_expense) / self._get_total_work_hours(
            weekly_hours
        )

    def durable_residuals(self) -> pd.DataFrame:
        """Return a DataFrame of pending/"uncovered" durable expenses."""
        return (
            self._expenses_by_type[ExpenseType.DURABLES]
            .assign(Required=lambda df: (df["Demand"] - df["Supply"]).clip(0))
            .groupby("Category", sort=False)
            .apply(lambda df: (df["Required"] * df["Unit Cost"]).sum())
            .to_frame()
            .T.reset_index(drop=True)
            .reindex(columns=EXPENSE_CATEGORIES, fill_value=0.0)
            .assign(Total=lambda df: df.sum(axis=1))
            .rename_axis(None, axis=1)
        )

    def planned_cost_allocation(self, this_year: bool = True) -> pd.DataFrame:
        """Return a DataFrame reflecting spending allocations over planned expenses."""
        years_cost_totals = self.years_planned_cost_totals(this_year)
        cost_allocation = years_cost_totals / years_cost_totals.sum()
        return cost_allocation.to_frame().T

    def planned_cost_averages(self, this_year: bool = True) -> pd.DataFrame:
        """Return a DataFrame of planned cost averaged across periods."""
        base_year = BASE_YEAR + (0 if this_year else 1)
        days_in_year = 365 if not isleap(base_year) else 366
        period_type_index = pd.Index(["Year", "Month", "Week", "Day"], name="Period")
        years_period_bases = (1, 12, days_in_year / 7, days_in_year)
        years_period_means = [
            self.years_planned_cost_totals(this_year) / period_base
            for period_base in years_period_bases
        ]
        return (
            pd.concat(years_period_means, axis=1)
            .transpose()
            .set_index(period_type_index)
            .assign(Total=lambda df: df.sum(axis=1))
        )

    def planned_cost_totals_timeline(self, freq: str = "D") -> pd.Series:
        """Return a Series of total planned costs with a periodicity of 'freq'."""
        if not isinstance(freq, str):
            raise TypeError(
                f"Paramenter 'freq' must be a string, got {type(freq).__name__}."
            )
        if freq not in VALID_COST_TIMELINE_FREQUENCIES:
            raise ValueError(
                "Parameter 'freq' is not a valid value, expected one of "
                f"{VALID_COST_TIMELINE_FREQUENCIES}."
            )
        cost_timeline = self._daily_planned_cost_totals().sum(axis=1)
        current_day = pd.Timestamp.now().normalize()
        if freq != "D":
            cost_timeline = cost_timeline.resample(freq).sum()
        else:
            closing_day = current_day + pd.offsets.Day(13)
            cost_timeline = cost_timeline.loc[current_day:closing_day]
            cost_timeline.index = cost_timeline.index.strftime("%Y-%m-%d").astype(
                "string"
            )
            return cost_timeline
        if freq == "ME":
            head_month_head = current_day.replace(day=1)
            tail_month_tail = head_month_head + pd.offsets.MonthEnd(12)
            cost_timeline = cost_timeline.loc[head_month_head:tail_month_tail]
            cost_timeline.index = cost_timeline.index.strftime("%Y-%m").astype("string")
        if freq == "W":
            head_week_head = current_day - pd.Timedelta(days=current_day.weekday())
            tail_week_tail = head_week_head + pd.offsets.Week(12, weekday=6)
            cost_timeline = cost_timeline.loc[head_week_head:tail_week_tail]
            cost_timeline.index = pd.Index(
                cost_timeline.index.isocalendar().apply(
                    lambda iso_data: f"{iso_data['year']}-W{iso_data['week']:02d}",
                    axis=1,
                ),
                dtype="string",
            )
        return cost_timeline

    @cache
    def years_planned_cost_totals(self, this_year: bool = True) -> pd.Series:
        """Return the total planned cost in the current or following year."""
        base_year = BASE_YEAR + (0 if this_year else 1)
        year_head = pd.Timestamp(year=base_year, month=1, day=1)
        year_tail = pd.Timestamp(year=base_year, month=12, day=31)
        return self._daily_planned_cost_totals().loc[year_head:year_tail].sum()

    # -------------------------------------------------------------------------
    # Private Methods
    # -------------------------------------------------------------------------

    def _living_income(self, base_expense: float) -> float:
        """Computes the income needed to meet all expenses and tax incurred in the current
        or following year."""
        # NOTE: Leverages Brent's Method: tax function continuity is required and assumed.
        max_fit_rate = FIT_BRACKETS[max(FIT_BRACKETS.keys())].rate
        max_sit_rate = SIT_BRACKETS[max(SIT_BRACKETS.keys())].rate
        max_tax_rate = max_fit_rate + max_sit_rate
        income_lower = base_expense
        income_upper = (1 + max_tax_rate) * base_expense

        def root_function(income: float) -> float:
            return income - (base_expense + self._tax_calculator.tax_total(income))

        return brentq(root_function, income_lower, income_upper, xtol=1e-3)

    def _daily_planned_cost_totals(self) -> pd.DataFrame:
        """Return a DataFrame of daily planned cost totals."""
        return sum(map(self._daily_planned_costs, PLANNED_EXPENSE_TYPES))

    def _daily_planned_costs(self, expense_type: ExpenseType) -> pd.DataFrame:
        """Return a DataFrame of daily planned costs under 'expense_type'."""
        if not isinstance(expense_type, ExpenseType):
            raise TypeError(
                "Parameter 'expense_type' must be an ExpenseType, got "
                f"{type(expense_type).__name__}."
            )
        if expense_type not in ExpenseType:
            raise ValueError(
                "Parameter 'expense_type' is not a planned ExpenseType, expected one of "
                f"{PLANNED_EXPENSE_TYPES}."
            )
        result = pd.DataFrame(0.0, self._cpi.index, EXPENSE_CATEGORIES, "float64")
        expenses = self._expenses_by_type[expense_type]
        get_base_cost = self._get_base_cost_func(expense_type)
        for _, expense in expenses.iterrows():
            bill_dates = list(self._bill_dater.get_billing_dates(expense))
            base_cost = get_base_cost(expense)
            category = expense["Category"]
            cpi_category = expense.get("CPI Category")
            if not cpi_category:
                result.loc[bill_dates, category] += base_cost
            else:
                cpi_multipliers = self._cpi.loc[bill_dates, cpi_category]
                result.loc[bill_dates, category] += base_cost * cpi_multipliers
        return result

    def _get_base_cost_func(
        self, expense_type: ExpenseType
    ) -> Callable[[pd.Series], float]:
        """Return the cost finding function for expenses under `expense_type`."""
        if not isinstance(expense_type, ExpenseType):
            raise TypeError(
                "Parameter 'expense_type' must be an ExpenseType, got "
                f"{type(expense_type).__name__}."
            )
        if expense_type is ExpenseType.SERVICES:
            return self._base_cost_of_service
        elif expense_type is ExpenseType.NONDURABLES:
            return self._base_cost_of_nondurable
        elif expense_type is ExpenseType.OBLIGATIONS:
            return self._base_cost_of_obligation
        else:
            raise ValueError(
                "Parameter 'expense_type' is not a planned ExpenseType, expected one of "
                f"{PLANNED_EXPENSE_TYPES}."
            )

    def _base_cost_of_service(self, service: pd.Series) -> float:
        """Return the cost of a 'service' expense (not inflation adjusted)."""
        cost = service["Period Cost"]
        if service.get("Add Sales Tax"):
            return cost * self._sales_tax_multiplier
        return cost

    def _base_cost_of_nondurable(self, nondurable: pd.Series) -> float:
        """Return the cost of a 'nondurable' expense (not inflation adjusted)."""
        cost = (
            nondurable["Unit Cost"]
            * nondurable["Usage Rate"]
            / nondurable["Unit Cost Base"]
        )
        if nondurable.get("Add Sales Tax"):
            return cost * self._sales_tax_multiplier
        return cost

    def _base_cost_of_obligation(self, obligation: pd.Series) -> float:
        """Return the cost of an 'obligation' expenses (not inflation adjusted)."""
        return obligation["Period Cost"]

    def _get_total_work_hours(self, weekly_hours: float = None) -> float:
        """Compute total work hours in current year."""
        if not weekly_hours:
            weekly_hours = self.weekly_hours
        week_total = (365 if not isleap(BASE_YEAR) else 366) / 7
        return week_total * weekly_hours

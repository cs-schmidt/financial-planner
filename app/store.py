from functools import cached_property
import re
from darts import TimeSeries
from darts.models import ExponentialSmoothing
from dateutil.relativedelta import relativedelta
import gspread as gs
import pandas as pd
from constants import ROOT_DIR, BILLING_DATE_MIN, BILLING_DATE_MAX
from schemata import (
    ExpenseSSheetVersion,
    ExpenseType,
    EXPENSE_SHEET_NAMES,
    EXPENSE_SCHEMA_BY_NAME,
    EXPENSE_DTYPE_BY_NAME,
)
from singleton import Singleton


# FIXME: Prevent warning logs in Jupyter caused by importing from the "darts.models".


class Store(metaclass=Singleton):
    """A singleton class whose instance provides the interface to all financial data."""

    # --------------------------------------------------------------------------
    # Static Attributes
    # --------------------------------------------------------------------------

    _EXPENSE_SSHEET_ID_BY_VERSION = {
        ExpenseSSheetVersion.MAIN: "1sEsvTncXi8bpqGRHbYMPes4gt9zSfFFwnM5qcACL7e4",
        ExpenseSSheetVersion.GOAL: "1RqdNOlCkBXK1RPxsNCPItxWMpm9saT-uQHkomZPsXj8",
        ExpenseSSheetVersion.TEST: "1FTm3XgSL055NgRTBbD40ye7ObA1cmvdFiAW2hyPY8tA",
    }
    _CPI_PATH = ROOT_DIR / "data/cpi_canada_2013-01_2025-12.csv"
    _GCP_SERVICE_ACCOUNT_KEY = ROOT_DIR / ".env/gcp-service-account-key.json"

    @cached_property
    def cpi(self) -> pd.DataFrame:
        """Return a DataFrame of the (interpolated) daily CPI normalized to today."""
        base_cpi = self._get_base_cpi()
        forecast_head = BILLING_DATE_MIN
        forecast_tail = BILLING_DATE_MAX
        cpi_tail_date = base_cpi.index[-1]
        forecast_delta = relativedelta(forecast_tail, cpi_tail_date)
        forecast_steps = forecast_delta.years * 12 + forecast_delta.months
        forecast_model = ExponentialSmoothing(seasonal_periods=12)

        def column_forecaster(header: str) -> pd.Series:
            column_tseries = TimeSeries.from_series(base_cpi[header])
            return forecast_model.fit(column_tseries).predict(forecast_steps).to_series()

        forecast_data = pd.concat(map(column_forecaster, base_cpi), axis=1)
        trailing_data = base_cpi.loc[forecast_head:forecast_tail]
        daily_cpi = (
            pd.concat([trailing_data, forecast_data])
            .reindex(pd.date_range(forecast_head, forecast_tail, freq="D"), copy=False)
            .interpolate("spline", order=4)
            .bfill()
        )
        baselines = daily_cpi.loc[pd.Timestamp.now().normalize()]
        return daily_cpi.div(baselines)

    # --------------------------------------------------------------------------
    # Public Methods
    # --------------------------------------------------------------------------

    def get_expenses(
        self, version: ExpenseSSheetVersion
    ) -> dict[ExpenseType, pd.DataFrame]:
        """Read the expenses spreadsheet under `version`, returning a dictionary mapping
        each ExpenseType to a DataFrame of its expense entries."""
        if not isinstance(version, ExpenseSSheetVersion):
            raise TypeError(
                "Parameter 'version' must be an ExpenseSSheetVersion, not "
                f"{type(version).__name__}"
            )

        ssheet_id = self._EXPENSE_SSHEET_ID_BY_VERSION[version]
        ssheet = self._get_gs_client().open_by_key(ssheet_id)
        sheet_by_name = {sheet.title: sheet for sheet in ssheet.worksheets()}
        missing_names = EXPENSE_SHEET_NAMES - set(sheet_by_name.keys())
        if missing_names:
            raise ValueError(f"Missing expense worksheets: {missing_names}")
        return {
            enum: self._expense_sheet_to_df(sheet_by_name[enum.value])
            for enum in ExpenseType
        }

    # --------------------------------------------------------------------------
    # Private Methods
    # --------------------------------------------------------------------------

    def _expense_sheet_to_df(self, sheet: gs.Worksheet) -> pd.DataFrame:
        """Return a DataFrame of the expense worksheet.

        Raise an error if `sheet` is not a valid expense worksheet. For durable expense
        sheets, only 'uncovered' entries are included in the result."""
        if not isinstance(sheet, gs.Worksheet):
            raise TypeError(
                "Parameter 'sheet' must be a gspread.Worksheet, not "
                f"{type(sheet).__name__}."
            )
        if sheet.title not in EXPENSE_SHEET_NAMES:
            raise ValueError(
                f"Parameter 'sheet.title' must be one of {EXPENSE_SHEET_NAMES}, got "
                f"{sheet.title}."
            )
        data_grid = sheet.get_values(
            value_render_option=gs.utils.ValueRenderOption.unformatted,
            date_time_render_option=gs.utils.DateTimeOption.formatted_string,
        )
        schema = EXPENSE_SCHEMA_BY_NAME[sheet.title]
        columns = data_grid[0]
        if len(columns) != len(schema.columns):
            raise ValueError(
                f"Invalid 'gspread.Worksheet' instance: expected {len(schema.columns)} "
                f"columns, got {len(columns)}."
            )
        missing_columns = set(schema.columns) - set(columns)
        if missing_columns:
            raise ValueError(
                "Expected 'sheet' to have a header row with schema's columns, missing "
                f"columns {missing_columns}."
            )
        result = pd.DataFrame(columns=columns, data=data_grid[1:])
        if sheet.title == ExpenseType.DURABLES.value:
            result = result[result["Cover"].eq("")]
        if not result.empty:
            result = schema.validate(result)
        return result.astype(EXPENSE_DTYPE_BY_NAME[sheet.title])

    def _get_base_cpi(self) -> pd.DataFrame:
        """Return a DataFrame of month-end CPI data from the local CPI CSV file."""
        cpi = pd.read_csv(
            self._CPI_PATH,
            usecols=["REF_DATE", "Products and product groups", "VALUE"],
            parse_dates=["REF_DATE"],
        ).pivot(index="REF_DATE", columns="Products and product groups", values="VALUE")
        head_date = cpi.index[0]
        tail_date = cpi.index[-1] + pd.offsets.MonthEnd()
        cpi.index = pd.date_range(head_date, tail_date, freq="ME")
        cpi.columns = [re.sub(r" \(\d+=\d+\)", "", column_name) for column_name in cpi]
        cpi.rename_axis(index="Date", columns="CPI Category", inplace=True)
        return cpi

    def _get_gs_client(self) -> gs.Client:
        """Return a gspread Client with read-only access to your Google sheets files."""
        return gs.service_account(self._GCP_SERVICE_ACCOUNT_KEY, gs.auth.READONLY_SCOPES)

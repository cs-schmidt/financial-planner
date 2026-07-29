import calendar
import pandas as pd
from functools import partial

from dash import dash_table, html
from dash.development.base_component import Component

from inc_metrics import lvi
from eqt_metrics import lps
from tax_profiler import TaxProfiler


def days_in_year(year: int) -> int:
    """Calendar length of the given year: 365 (common years) or 366 (leap years)."""

    return 366 if calendar.isleap(year) else 365


def lve_totals_table(lve_by_year: pd.DataFrame) -> Component:
    """Table of LVE totals per year, shown over Yearly, Monthly, and Biweekly periods."""

    cost_by_year = lve_by_year.sum(axis=1)
    days_by_year = cost_by_year.index.to_series().map(days_in_year)
    freq_in_year = {
        "Yearly": 1,
        "Monthly": 12,
        "Biweekly": days_by_year / 14,
    }
    base_data = pd.DataFrame(freq_in_year).rdiv(cost_by_year, axis=0)
    base_data.columns.name = "Period"
    base_data.index.name = "Year"
    base_data = base_data.reset_index()

    data = base_data.to_dict(orient="records")
    data_format = dash_table.FormatTemplate.money(2)

    year_column = base_data.columns[0]
    freq_columns = base_data.columns[1:]
    column_specs = [
        {"name": year_column, "id": year_column},
        *[
            {"name": c, "id": c, "type": "numeric", "format": data_format}
            for c in freq_columns
        ],
    ]

    return html.Div(
        [
            html.H3("LVE Totals"),
            dash_table.DataTable(
                data,
                column_specs,
                style_table={"overflowX": "auto", "width": "fit-content"},
                style_header={
                    "fontWeight": "500",
                    "whiteSpace": "normal",
                    "paddingLeft": "6px",
                    "paddingRight": "6px",
                },
                style_cell={"textAlign": "center"},
            ),
        ],
        style={"padding": "8px 16px", "background-color": "white"},
    )


def lvi_totals_table(lve_by_year: pd.DataFrame, tax_profiler: TaxProfiler) -> Component:
    """Table of LVI totals per year, shown over Yearly, Monthly, and Biweekly periods."""

    value_getter = partial(lvi, tax_profiler=tax_profiler)
    cost_by_year = lve_by_year.sum(axis=1).map(value_getter)
    days_by_year = cost_by_year.index.to_series().map(days_in_year)
    freq_in_year = {
        "Yearly": 1,
        "Monthly": 12,
        "Biweekly": days_by_year / 14,
    }

    base_data = pd.DataFrame(freq_in_year).rdiv(cost_by_year, axis=0)
    base_data.columns.name = "Period"
    base_data.index.name = "Year"
    base_data = base_data.reset_index()

    data = base_data.to_dict(orient="records")
    data_format = dash_table.FormatTemplate.money(2)

    year_column = base_data.columns[0]
    freq_columns = base_data.columns[1:]
    column_specs = [
        {"name": year_column, "id": year_column},
        *[
            {"name": c, "id": c, "type": "numeric", "format": data_format}
            for c in freq_columns
        ],
    ]

    return html.Div(
        [
            html.H3("LVI Totals"),
            dash_table.DataTable(
                data,
                column_specs,
                style_table={"overflowX": "auto", "width": "fit-content"},
                style_header={
                    "fontWeight": "500",
                    "whiteSpace": "normal",
                    "paddingLeft": "6px",
                    "paddingRight": "6px",
                },
                style_cell={"textAlign": "center"},
            ),
        ],
        style={"padding": "8px 16px", "background-color": "white"},
    )


def lps_targets_table(
    lve_by_year: pd.DataFrame, r: float, i: float, tax_profiler: TaxProfiler
) -> Component:
    """Table of LPS targets per year, shown over Yearly, Monthly, and Biweekly periods."""

    value_getter = partial(lps, r=r, i=i, tax_profiler=tax_profiler)
    size_by_year = lve_by_year.sum(axis=1).map(value_getter)
    size_by_year = size_by_year.rename_axis("Year").reset_index(name="Valuation")

    data = size_by_year.to_dict(orient="records")
    data_format = dash_table.FormatTemplate.money(2)

    year_column = size_by_year.columns[0]
    freq_columns = size_by_year.columns[1:]
    column_specs = [
        {"name": year_column, "id": year_column},
        *[
            {"name": c, "id": c, "type": "numeric", "format": data_format}
            for c in freq_columns
        ],
    ]

    return html.Div(
        [
            html.H3("LPS Targets"),
            dash_table.DataTable(
                data,
                column_specs,
                style_table={"overflowX": "auto", "width": "fit-content"},
                style_header={
                    "fontWeight": "500",
                    "whiteSpace": "normal",
                    "paddingLeft": "6px",
                    "paddingRight": "6px",
                },
                style_cell={"textAlign": "center"},
            ),
        ],
        style={"padding": "8px 16px", "background-color": "white"},
    )


def lve_allocation_table(lve_by_year: pd.DataFrame) -> Component:
    """Table of LVE allocation per year."""

    base_data = lve_by_year.div(lve_by_year.sum(axis=1), axis=0)
    base_data.columns.name = "Period"
    base_data.index.name = "Year"
    base_data = base_data.reset_index()

    data = base_data.to_dict(orient="records")
    data_format = dash_table.FormatTemplate.percentage(2)

    year_column = base_data.columns[0]
    freq_columns = base_data.columns[1:]
    column_specs = [
        {"name": year_column, "id": year_column},
        *[
            {"name": c, "id": c, "type": "numeric", "format": data_format}
            for c in freq_columns
        ],
    ]

    return html.Div(
        [
            html.H3("LVE Allocation"),
            dash_table.DataTable(
                data,
                column_specs,
                style_table={"overflowX": "auto", "width": "fit-content"},
                style_header={
                    "fontWeight": "500",
                    "whiteSpace": "normal",
                    "paddingLeft": "6px",
                    "paddingRight": "6px",
                },
                style_cell={"textAlign": "center"},
            ),
        ],
        style={"padding": "8px 16px", "background-color": "white"},
    )

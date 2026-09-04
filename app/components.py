from functools import partial

import pandas as pd
from dash import dash_table, html
from dash.development.base_component import Component

from inc_metrics import lvi
from eqt_metrics import lps
from tax_profiler import TaxProfiler
from utils import days_in_year


# ------------------------------------------------------------------------------
# Shared Styles
# ------------------------------------------------------------------------------

CELL_FONT_SIZE = "12px"
HEADER_FONT_SIZE = "14px"

BASE_APP_STYLES = {
    "display": "flex",
    "flex-flow": "row wrap",
    "gap": "20px",
    "alignItems": "flex-start",
}
BASE_CARD_STYLES = {
    "flex-shrink": "0",
    "width": "fit-content",
    "padding": "8px",
    "backgroundColor": "white",
}
BASE_TABLE_STYLES = dict(
    style_as_list_view=True,
    style_table={"overflowX": "auto"},
    style_cell={
        "padding": "6px 8px",
        "textAlign": "right",
        "fontFamily": "inherit",
        "fontSize": CELL_FONT_SIZE,
    },
    style_header={
        "borderBottom": "2px solid #ddd",
        "fontSize": CELL_FONT_SIZE,
        "fontWeight": "600",
    },
    style_cell_conditional=[{"if": {"column_id": "Year"}, "textAlign": "center"}],
)

# ------------------------------------------------------------------------------
# Data Formatting
# ------------------------------------------------------------------------------

MONEY_FORMAT = dash_table.FormatTemplate.money(2)
PERCENT_FORMAT = dash_table.FormatTemplate.percentage(2)


def _make_numeric_column_spec(name: str) -> dict:
    return {"name": name, "id": name, "type": "numeric"}


def _make_money_column_spec(name: str) -> dict:
    return {**_make_numeric_column_spec(name), "format": MONEY_FORMAT}


def _make_percent_column_spec(name: str) -> dict:
    return {**_make_numeric_column_spec(name), "format": PERCENT_FORMAT}


def _validate_column_specs(column_specs: list[dict]) -> list[dict]:
    """Ensure column ids are unique before handing them to DataTable."""

    ids = [c["id"] for c in column_specs]
    seen = set()
    dupes = {i for i in ids if i in seen or seen.add(i)}
    if dupes:
        raise ValueError(f"Duplicate column ids: {sorted(dupes)}")
    return column_specs


# ------------------------------------------------------------------------------
# Private Components & Associated Helpers
# ------------------------------------------------------------------------------


def _get_subyear_costs(cost_by_year: pd.Series) -> pd.DataFrame:
    """Given yearly totals, return Yearly/Monthly/Biweekly amounts for each year."""

    days_by_year = cost_by_year.index.to_series().map(days_in_year)
    return pd.DataFrame(
        {
            "Yearly Cost": cost_by_year,
            "Monthly Cost": cost_by_year / 12,
            "Biweekly Cost": cost_by_year / (days_by_year / 14),
        }
    )


def _make_table_card(
    title: str,
    df: pd.DataFrame,
    column_specs: list[dict],
    table_styles: dict = BASE_TABLE_STYLES,
) -> Component:
    """Wrap a DataFrame + column spec in the standard titled DataTable card."""

    data = df.to_dict(orient="records")
    column_specs = _validate_column_specs(column_specs)

    return html.Div(
        [
            html.H3(title),
            dash_table.DataTable(data, column_specs, **table_styles),
        ],
        style=BASE_CARD_STYLES,
    )


# ------------------------------------------------------------------------------
# Public Components
# ------------------------------------------------------------------------------


def lve_totals_table(lve_by_year: pd.DataFrame) -> Component:
    """Table of LVE totals per year, shown over Yearly, Monthly, and Biweekly periods."""

    cost_by_year = lve_by_year.sum(axis=1)
    data = _get_subyear_costs(cost_by_year).reset_index(names="Year")

    freq_columns = data.columns[1:]
    column_specs = [
        _make_numeric_column_spec("Year"),
        *[_make_money_column_spec(header) for header in freq_columns],
    ]

    return _make_table_card("LVE Totals", data, column_specs)


def lvi_totals_table(lve_by_year: pd.DataFrame, tax_profiler: TaxProfiler) -> Component:
    """Table of LVI totals per year, shown over Yearly, Monthly, and Biweekly periods."""

    value_getter = partial(lvi, tax_profiler=tax_profiler)
    cost_by_year = lve_by_year.sum(axis=1).map(value_getter)
    data = _get_subyear_costs(cost_by_year).reset_index(names="Year")

    freq_columns = data.columns[1:]
    column_specs = [
        _make_numeric_column_spec("Year"),
        *[_make_money_column_spec(header) for header in freq_columns],
    ]

    empl_type = "Not Self-Employed" if tax_profiler.self_empl else "Self-Employed"
    title = f"LVI Totals ({empl_type})"

    return _make_table_card(title, data, column_specs)


def lps_targets_table(
    lve_by_year: pd.DataFrame, r: float, i: float, tax_profiler: TaxProfiler
) -> Component:
    """Table of LPS targets per year, shown over Yearly, Monthly, and Biweekly periods."""

    value_getter = partial(lps, r=r, i=i, tax_profiler=tax_profiler)
    size_by_year = lve_by_year.sum(axis=1).map(value_getter)
    data = size_by_year.rename_axis("Year").reset_index(name="Valuation")

    column_specs = [
        _make_numeric_column_spec("Year"),
        _make_money_column_spec("Valuation"),
    ]

    title = f"LPS Targets (r={round(r * 100, 2)}%, i={round(i * 100, 2)}%)"

    return _make_table_card(title, data, column_specs)


def lve_allocation_table(lve_by_year: pd.DataFrame) -> Component:
    """Table of LVE allocation per year."""

    table_styles = {
        **BASE_TABLE_STYLES,
        "style_header": {
            **BASE_TABLE_STYLES["style_header"],
            "whiteSpace": "normal",
            "height": "auto",
            "textAlign": "center",
        },
        "style_cell": {
            **BASE_TABLE_STYLES["style_cell"],
            "minWidth": "70px",
            "maxWidth": "110px",
        },
    }

    data = lve_by_year.div(lve_by_year.sum(axis=1), axis=0).reset_index(names="Year")

    percent_columns = data.columns[1:]
    column_specs = [
        _make_numeric_column_spec("Year"),
        *[_make_percent_column_spec(header) for header in percent_columns],
    ]

    return _make_table_card("LVE Allocation", data, column_specs, table_styles)

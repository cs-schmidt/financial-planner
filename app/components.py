from collections import Counter
from functools import partial
from typing import Dict, Union, Sequence, Optional

from dash import html, dash_table
from dash.dash_table.FormatTemplate import Sign
from dash.dash_table.DataTable import NumberType, DataTable
from dash.development.base_component import Component
import pandas as pd

from eqt_metrics import lps
from inc_metrics import lvi
from lve_plan import LvePlan
from schemas import LveCategory, PAY_CATEGORIES
from tax_profiler import TaxProfiler
from utils import days_in_year

# ------------------------------------------------------------------------------
# Typing Variables
# ------------------------------------------------------------------------------


RecordType = Dict[str, Union[str, NumberType, bool]]
ColumnType = DataTable.Columns


# ------------------------------------------------------------------------------
# Component Styles
# ------------------------------------------------------------------------------


BASE_APP_STYLES = {
    "display": "flex",
    "flexFlow": "row wrap",
    "alignItems": "flex-start",
    "gap": "10px",
}


BASE_CARD_STYLES = {
    "flex": "none",
    "width": "fit-content",
    "padding": "8px",
    "borderRadius": "8px",
    "backgroundColor": "#F5F5F5",
}

BASE_CARD_TITLE_STYLES = {
    "margin": "0px 0px 8px",
    "padding": "0px",
    "fontSize": "14px",
}

BASE_CARD_TABLE_STYLES_ARGS = dict(
    style_table={
        "overflowX": "auto",
    },
    style_cell={
        "padding": "4px 8px",
        "fontSize": "10px",
        "textAlign": "right",
    },
    style_header={
        "fontWeight": "600",
        "borderBottom": "2px solid #ddd",
    },
)

YEAR_STUB_TABLE_STYLES_ARGS = {
    **BASE_CARD_TABLE_STYLES_ARGS,
    "style_cell_conditional": [
        {
            "if": {"column_id": "Year"},
            "textAlign": "center",
        }
    ],
}

TYPE_STUB_TABLE_STYLES_ARGS = {
    **BASE_CARD_TABLE_STYLES_ARGS,
    "style_cell_conditional": [
        {
            "if": {"column_id": "Type"},
            "textAlign": "center",
        }
    ],
}

BASE_TAG_STYLES = {
    "display": "inline-block",
    "margin": "0px 0px 8px",
    "padding": "2px 4px",
    "fontSize": "10px",
    "fontWeight": "600",
    "borderRadius": "4px",
}

TABLE_CARD_TAGS = {
    "expense": {
        "title": "Expense",
        "styles": {**BASE_TAG_STYLES, "backgroundColor": "#E6F1FB", "color": "#0C447C"},
    },
    "income": {
        "title": "Income",
        "styles": {**BASE_TAG_STYLES, "backgroundColor": "#EAF3DE", "color": "#27500A"},
    },
    "equity": {
        "title": "Equity",
        "styles": {**BASE_TAG_STYLES, "backgroundColor": "#EEEDFE", "color": "#3C3489"},
    },
}


# ------------------------------------------------------------------------------
# Private Helpers
# ------------------------------------------------------------------------------


def _make_numeric_column_spec(name: str) -> ColumnType:
    return ColumnType(name=name, id=name, type="numeric")


def _make_money_column_spec(
    name: str, decimals: int = 2, sign: str = Sign.default
) -> ColumnType:
    return ColumnType(
        **_make_numeric_column_spec(name),
        format=dash_table.FormatTemplate.money(decimals, sign=sign),
    )


def _make_percent_column_spec(
    name: str, decimals: int = 2, rounded: bool = False
) -> ColumnType:
    return ColumnType(
        **_make_numeric_column_spec(name),
        format=dash_table.FormatTemplate.percentage(decimals, rounded=rounded),
    )


def _validate_column_specs(column_specs: Sequence[ColumnType]) -> Sequence[ColumnType]:
    """Ensure column ids are unique before handing them to DataTable."""

    ids = [c["id"] for c in column_specs]

    dupes = {i for i, n in Counter(ids).items() if n > 1}
    if dupes:
        raise ValueError(f"Duplicate column ids: {sorted(dupes)}")
    return column_specs


def _validate_records_against_columns(
    records: Sequence[RecordType], column_specs: Sequence[ColumnType]
) -> Sequence[RecordType]:
    """Ensure record keys match the given column spec."""

    valid_ids = {c["id"] for c in column_specs}
    for record in records:
        unknown = set(record.keys()) - valid_ids
        if unknown:
            raise ValueError(f"Record has keys not present in columns: {sorted(unknown)}")
    return records


def _get_subyear_costs_table(cost_by_year: pd.Series) -> pd.DataFrame:
    """Produce a table of costs over yearly, monthly, and biweekly periods."""

    days_by_year = cost_by_year.index.to_series().map(days_in_year)
    return pd.DataFrame(
        {
            "Yearly Cost": cost_by_year,
            "Monthly Cost": cost_by_year / 12,
            "Biweekly Cost": cost_by_year / (days_by_year / 14),
        }
    )


# ------------------------------------------------------------------------------
# Public Component Factory Functions
# ------------------------------------------------------------------------------


def table_card(
    title: str,
    records: Sequence[RecordType],
    columns: Sequence[ColumnType],
    *,
    tag: Optional[str] = None,
    card_styles: Optional[Dict] = None,
    title_styles: Optional[Dict] = None,
    table_style_args: Optional[Dict] = None,
) -> Component:
    """Produce a titled card presenting a data table."""

    columns = _validate_column_specs(columns)
    records = _validate_records_against_columns(records, columns)

    heading_children = []
    if tag is not None:
        tag_spec = TABLE_CARD_TAGS[tag]
        heading_children.append(html.Span(tag_spec["title"], style=tag_spec["styles"]))
    heading_children.append(
        html.H3(title, style={**BASE_CARD_TITLE_STYLES, **(title_styles or {})})
    )

    heading_comp = html.Div(heading_children)
    tabular_comp = dash_table.DataTable(
        records, columns, **{**BASE_CARD_TABLE_STYLES_ARGS, **(table_style_args or {})}
    )
    return html.Div(
        [heading_comp, tabular_comp],
        style={**BASE_CARD_STYLES, **(card_styles or {})},
    )


def lve_totals_card(lve_by_year: pd.DataFrame) -> Component:
    """Table card of LVE totals per year, shown at yearly, monthly, and biweekly
    levels."""

    cost_by_year = lve_by_year.sum(axis=1).round()
    table = _get_subyear_costs_table(cost_by_year).reset_index(names="Year")

    data_columns = table.columns[1:]
    columns = [
        _make_numeric_column_spec("Year"),
        *[_make_money_column_spec(header, 0) for header in data_columns],
    ]

    return table_card(
        "LVE Totals",
        table.to_dict("records"),
        columns,
        tag="expense",
        table_style_args=YEAR_STUB_TABLE_STYLES_ARGS,
    )


def lvi_totals_card(lve_by_year: pd.DataFrame, tax_profiler: TaxProfiler) -> Component:
    """Table card of LVI totals per year, shown at yearly, monthly, and biweekly
    levels."""

    value_getter = partial(lvi, tax_profiler=tax_profiler)
    cost_by_year = lve_by_year.sum(axis=1).map(value_getter).round()
    table = _get_subyear_costs_table(cost_by_year).reset_index(names="Year")

    data_columns = table.columns[1:]
    columns = [
        _make_numeric_column_spec("Year"),
        *[_make_money_column_spec(header, 0) for header in data_columns],
    ]

    empl_tag = "Self-Employed" if tax_profiler.self_empl else "Not Self-Employed"
    title = f"LVI Totals ({empl_tag})"

    return table_card(
        title,
        table.to_dict("records"),
        columns,
        tag="income",
        table_style_args=YEAR_STUB_TABLE_STYLES_ARGS,
    )


def lps_targets_card(
    lve_by_year: pd.DataFrame, r: float, i: float, tax_profiler: TaxProfiler
) -> Component:
    """Table card of LPS targets per year, shown at yearly, monthly, and biweekly
    levels."""

    value_getter = partial(lps, r=r, i=i, tax_profiler=tax_profiler)
    size_by_year = lve_by_year.sum(axis=1).map(value_getter).round()
    table = size_by_year.rename_axis("Year").reset_index(name="Valuation")

    columns = [_make_numeric_column_spec("Year"), _make_money_column_spec("Valuation", 0)]

    vars_tag = f"r={round(r * 100, 2)}%, i={round(i * 100, 2)}%"
    title = f"LPS Targets ({vars_tag})"

    return table_card(
        title,
        table.to_dict("records"),
        columns,
        tag="equity",
        table_style_args=YEAR_STUB_TABLE_STYLES_ARGS,
    )


def lve_allocation_card(lve_by_year: pd.DataFrame) -> Component:
    """Table card of LVE allocation per year (hides negligible data columns)."""

    table = lve_by_year.div(lve_by_year.sum(axis=1), axis=0).round(4)
    table = table.loc[:, (table != 0).any(axis=0)].reset_index(names="Year")

    data_columns = table.columns[1:]
    columns = [
        _make_numeric_column_spec("Year"),
        *[_make_percent_column_spec(header) for header in data_columns],
    ]

    return table_card(
        "LVE Allocation",
        table.to_dict("records"),
        columns,
        tag="expense",
        table_style_args=YEAR_STUB_TABLE_STYLES_ARGS,
    )


def dsc_summary_card(lve_plan: LvePlan) -> Component:
    """Table card of DSC data, summarizing remaining and total costs across categories
    (hides negligible data columns)."""

    base_table = lve_plan[LveCategory.DURABLES].copy()
    unit_cost = base_table["Unit Cost"]
    base_table["Lasting"] = (base_table["Demand"] - base_table["Supply"]) * unit_cost
    base_table["Totaled"] = base_table["Demand"] * unit_cost

    table = (
        base_table.melt(
            id_vars=["Pay Category"],
            value_vars=["Lasting", "Totaled"],
            var_name="Type",
            value_name="Cost",
        )
        .pivot_table(
            index="Type",
            columns="Pay Category",
            values="Cost",
            aggfunc="sum",
        )
        .filter(PAY_CATEGORIES)
        .round()
        .reset_index()
    )
    categories = [category for category in PAY_CATEGORIES if category in table.columns]
    table["Totaled"] = table[categories].sum(axis=1)

    data_columns = table.columns[1:]
    columns = [
        {"name": "Type", "id": "Type"},
        *[_make_money_column_spec(header, 0) for header in data_columns],
    ]

    return table_card(
        "DSC Summary",
        table.to_dict("records"),
        columns,
        tag="expense",
        table_style_args=TYPE_STUB_TABLE_STYLES_ARGS,
    )

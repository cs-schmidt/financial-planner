from dash import dash_table, dcc, html
from dash.development.base_component import Component
import plotly.graph_objs as go
from calculator import Calculator
from constants import BASE_YEAR


def LivingWageCurves(calculator: Calculator) -> Component:
    """Dash component showing living wage curves over the current and following year."""
    year1_curve = calculator.living_wage_curve(this_year=True)
    year2_curve = calculator.living_wage_curve(this_year=False)
    year1_trace = go.Scatter(
        x=year1_curve.index,
        y=year1_curve,
        mode="lines",
        name=f"Living Wage Curve ({BASE_YEAR})",
    )
    year2_trace = go.Scatter(
        x=year2_curve.index,
        y=year2_curve,
        mode="lines",
        name=f"Living Wage Curve ({BASE_YEAR + 1})",
    )
    figure = go.Figure(
        [year1_trace, year2_trace],
        layout=dict(
            height=600,
            title_text="Living Wage at Weekly Hours",
            legend=dict(x=0.5, xanchor="center", yanchor="top"),
            xaxis=dict(
                minor=dict(showgrid=True),
                title_text="Weekly Hours",
            ),
            yaxis=dict(
                minor=dict(showgrid=True),
                minallowed=15,
                tickformat="$.2f",
                title_text="Living Wage",
            ),
        ),
    )
    return html.Div(
        [
            html.H2("Living Wage Curves"),
            dcc.Graph(figure=figure),
        ]
    )


def DurableResiduals(calculator: Calculator) -> Component:
    """Dash component showing a table of residual durable expenses."""
    data = calculator.durable_residuals()
    data_format = dash_table.FormatTemplate.money(2)
    return html.Div(
        [
            html.H2("Durable Residuals"),
            dash_table.DataTable(
                data.to_dict(orient="records"),
                columns=[
                    {"name": c, "id": c, "type": "numeric", "format": data_format}
                    for c in data.columns
                ],
                style_table={"overflowX": "auto"},
                style_cell={"textAlign": "center"},
                style_header={
                    "whiteSpace": "normal",
                    "paddingLeft": "6px",
                    "paddingRight": "6px",
                },
            ),
        ]
    )


def PlannedCostAverages(calculator: Calculator, this_year: bool = True) -> Component:
    """Dash component showing a table of planned cost averages."""
    year = BASE_YEAR + (0 if this_year else 1)
    data = calculator.planned_cost_averages(this_year).reset_index()
    data_format = dash_table.FormatTemplate.money(2)
    return html.Div(
        [
            html.H2(f"Planned Cost Averages ({year})"),
            dash_table.DataTable(
                data.to_dict(orient="records"),
                columns=[
                    {"name": c, "id": c, "type": "numeric", "format": data_format}
                    for c in data.columns
                ],
                style_table={"overflowX": "auto"},
                style_cell={"textAlign": "center"},
                style_header={
                    "whiteSpace": "normal",
                    "paddingLeft": "6px",
                    "paddingRight": "6px",
                },
            ),
        ]
    )


def PlannedCostAllocation(calculator: Calculator, this_year: bool = True) -> Component:
    """Dash component showing a table of planned cost allocation."""
    year = BASE_YEAR + (0 if this_year else 1)
    data = calculator.planned_cost_allocation(this_year)
    data_format = dash_table.FormatTemplate.percentage(2)
    return html.Div(
        [
            html.H2(f"Planned Cost Allocation ({year})"),
            dash_table.DataTable(
                data.to_dict(orient="records"),
                columns=[
                    {"name": c, "id": c, "type": "numeric", "format": data_format}
                    for c in data.columns
                ],
                style_table={"overflowX": "auto"},
                style_cell={"textAlign": "center"},
                style_header={
                    "whiteSpace": "normal",
                    "paddingLeft": "6px",
                    "paddingRight": "6px",
                },
            ),
        ]
    )


def PlannedCostTotalsTimeline(calculator: Calculator, freq: str = "D") -> Component:
    """Dash component showing a graph of planned costs over time."""
    period_by_freq = {"D": "Daily", "W": "Weekly", "ME": "Monthly"}
    data = calculator.planned_cost_totals_timeline(freq)
    trace = go.Bar(x=data.index.to_list(), y=data.to_list())
    figure = go.Figure(
        trace,
        layout=dict(
            title_text=f"{period_by_freq[freq]} Planned Costs",
            yaxis=dict(
                minor=dict(showgrid=True),
                tickformat="$.2f",
            ),
        ),
    )
    return dcc.Graph(figure=figure)

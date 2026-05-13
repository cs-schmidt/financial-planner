from enum import Enum
import pandas as pd
import pandera as pda
import pandera.extensions as pda_extensions


class ExpenseSSheetVersion(Enum):
    MAIN = "main"
    GOAL = "goal"
    TEST = "test"


class ExpenseType(Enum):
    SERVICES = "services"
    NONDURABLES = "nondurables"
    OBLIGATIONS = "obligations"
    DURABLES = "durables"


PLANNED_EXPENSE_TYPES = frozenset(
    [
        ExpenseType.SERVICES,
        ExpenseType.NONDURABLES,
        ExpenseType.OBLIGATIONS,
    ]
)
EXPENSE_SHEET_NAMES = frozenset([enum.value for enum in ExpenseType])
EXPENSE_CATEGORIES = [
    "Housing",
    "Auto",
    "Food & Dining",
    "Health & Personal Care",
    "Clothing",
    "Education & Research",
    "Furnishings & Textiles",
    "Kitchen Equipment & Supplies",
    "Electronics & Software",
    "Cleaning",
    "Other Operations & Equipment",
    "Transport & Travel",
    "Finance & Legal",
    "Recreation",
    "Other Expenses",
]
CPI_CATEGORIES = {
    "Food purchased from stores",
    "Food purchased from restaurants",
    "Rent",
    "Tenants' insurance premiums",
    "Electricity",
    "Water",
    "Natural gas",
    "Fuel oil and other fuels",
    "Telephone services",
    "Postal and other communications services",
    "Internet access services",
    "Laundry detergents and soaps",
    "Detergents and rinse agents for dish washing",
    "Household cleaning and polishing products",
    "Bleach and other household chemical products",
    "Fabric softener",
    "Household paper supplies",
    "Stationery",
    "Plastic and aluminum foil supplies",
    "Other household supplies",
    "Other household services",
    "Financial services",
    "Upholstered furniture",
    "Wooden furniture",
    "Other furniture",
    "Bedding and other household textiles",
    "Cooking appliances",
    "Refrigerators and freezers",
    "Laundry and dishwashing appliances",
    "Other household appliances",
    "Non-electric kitchen utensils, tableware and cookware",
    "Household tools (including lawn, garden and snow removal equipment)",
    "Other household equipment",
    "Men's clothing",
    "Men's footwear (excluding athletic)",
    "Athletic footwear",
    "Clothing accessories",
    "Watches",
    "Clothing material, notions and services",
    "Gasoline",
    "Passenger vehicle parts, accessories and supplies",
    "Passenger vehicle maintenance and repair services",
    "Passenger vehicle insurance premiums",
    "Passenger vehicle registration fees",
    "Drivers' licences",
    "Parking fees",
    "City bus and subway transportation",
    "Air transportation",
    "Prescribed medicines (excluding medicinal cannabis)",
    "Non-prescribed medicines",
    "Eye care goods",
    "Other health care goods",
    "Eye care services",
    "Dental care services",
    "Other health care services",
    "Personal soap",
    "Toiletry items and cosmetics",
    "Oral-hygiene products",
    "Other personal care supplies and equipment",
    "Personal care services",
    "Computer equipment, software and supplies",
    "Multipurpose digital devices",
    "Recreational services",
    "School textbooks and supplies",
    "Other lessons, courses and education services",
    "Books and reading material (excluding textbooks)",
    "Alcoholic beverages purchased from stores",
}
PERIOD_TYPES = {"Year", "Month", "Week", "Day"}


@pda_extensions.register_check_method()
def is_numeric(series: pd.Series) -> bool:
    """Return True if `series` is of int or float dtype, False otherwise."""
    # NOTE: An empty Series has an "object" dtype.
    valid_dtype_kinds = {"i", "f"}
    return (
        pd.api.types.is_any_real_numeric_dtype(series)
        and series.dtype.kind in valid_dtype_kinds
    )


@pda_extensions.register_check_method()
def is_valid_start_date_string(series: pd.Series) -> bool:
    """Check if all values in `series` are valid YYYY-MM-DD date strings."""
    if not series.map(lambda x: isinstance(x, str)).all():
        return False
    # Check that all strings of YYYY-MM-DD form.
    if not series.str.fullmatch(r"\d{4}-\d{2}-\d{2}").all():
        return False
    if not pd.to_datetime(series, format="%Y-%m-%d", errors="coerce").notna().all():
        return False
    return True


EXPENSE_SCHEMA_BY_NAME = {
    "services": pda.DataFrameSchema(
        {
            "Item": pda.Column(str, pda.Check.ne(""), unique=True),
            "Category": pda.Column(str, pda.Check.isin(EXPENSE_CATEGORIES)),
            "Period Cost": pda.Column(checks=[pda.Check.is_numeric(), pda.Check.gt(0)]),
            "Period Type": pda.Column(str, pda.Check.isin(PERIOD_TYPES)),
            "Period Size": pda.Column(int, pda.Check.ge(1)),
            "Start Date": pda.Column(str, pda.Check.is_valid_start_date_string()),
            "Add Sales Tax": pda.Column(bool),
            "CPI Category": pda.Column(str, pda.Check.isin(CPI_CATEGORIES)),
            "Notes": pda.Column(str),
        }
    ),
    "nondurables": pda.DataFrameSchema(
        {
            "Item": pda.Column(str, pda.Check.ne(""), unique=True),
            "Category": pda.Column(str, pda.Check.isin(EXPENSE_CATEGORIES)),
            "Unit Cost": pda.Column(checks=[pda.Check.is_numeric(), pda.Check.gt(0)]),
            "Unit Cost Base": pda.Column(int, pda.Check.ge(1)),
            "Unit": pda.Column(str, pda.Check.ne("")),
            "Usage Rate": pda.Column(checks=[pda.Check.is_numeric(), pda.Check.gt(0)]),
            "Period Type": pda.Column(str, pda.Check.isin(PERIOD_TYPES)),
            "Period Size": pda.Column(int, pda.Check.ge(1)),
            "Start Date": pda.Column(str, pda.Check.is_valid_start_date_string()),
            "Add Sales Tax": pda.Column(bool),
            "CPI Category": pda.Column(str, pda.Check.isin(CPI_CATEGORIES)),
            "Item Notes": pda.Column(str),
            "Usage Notes": pda.Column(str),
        }
    ),
    "obligations": pda.DataFrameSchema(
        {
            "Item": pda.Column(str, pda.Check.ne(""), unique=True),
            "Category": pda.Column(str, pda.Check.isin(EXPENSE_CATEGORIES)),
            "Period Cost": pda.Column(checks=[pda.Check.is_numeric(), pda.Check.gt(0)]),
            "Period Type": pda.Column(str, pda.Check.isin(PERIOD_TYPES)),
            "Period Size": pda.Column(int, pda.Check.ge(1)),
            "Periods": pda.Column(int, pda.Check.ge(1)),
            "Start Date": pda.Column(str, pda.Check.is_valid_start_date_string()),
            "CPI Category": pda.Column(str, pda.Check.isin(CPI_CATEGORIES)),
            "Notes": pda.Column(str),
        }
    ),
    "durables": pda.DataFrameSchema(
        {
            "Item": pda.Column(str, pda.Check.ne(""), unique=True),
            "Category": pda.Column(str, pda.Check.isin(EXPENSE_CATEGORIES)),
            "Unit Cost": pda.Column(checks=[pda.Check.is_numeric(), pda.Check.gt(0)]),
            "Supply": pda.Column(int, pda.Check.ge(0)),
            "Demand": pda.Column(int, pda.Check.ge(1)),
            "Add Sales Tax": pda.Column(bool),
            "Cover": pda.Column(str),
            "Notes": pda.Column(str),
        }
    ),
}
EXPENSE_DTYPE_BY_NAME = {
    "services": {
        "Item": "string",
        "Category": "string",
        "Period Cost": "float",
        "Period Type": "string",
        "Period Size": "int",
        "Start Date": "datetime64[ns]",
        "Add Sales Tax": "bool",
        "CPI Category": "string",
        "Notes": "string",
    },
    "nondurables": {
        "Item": "string",
        "Category": "string",
        "Unit Cost": "float",
        "Unit Cost Base": "int",
        "Unit": "string",
        "Usage Rate": "float",
        "Period Type": "string",
        "Period Size": "int",
        "Start Date": "datetime64[ns]",
        "Add Sales Tax": "bool",
        "CPI Category": "string",
        "Item Notes": "string",
        "Usage Notes": "string",
    },
    "obligations": {
        "Item": "string",
        "Category": "string",
        "Period Cost": "float",
        "Period Type": "string",
        "Period Size": "int",
        "Periods": "int",
        "Start Date": "datetime64[ns]",
        "CPI Category": "string",
        "Notes": "string",
    },
    "durables": {
        "Item": "string",
        "Category": "string",
        "Unit Cost": "float",
        "Supply": "int",
        "Demand": "int",
        "Add Sales Tax": "bool",
        "Cover": "string",
        "Notes": "string",
    },
}

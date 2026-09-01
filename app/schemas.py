from enum import StrEnum

import pandas as pd
import pandera as pda
import pandera.extensions as pda_extensions
from pandera.engines.pandas_engine import DateTime


class LvePlanID(StrEnum):
    MAIN = "1RxN51OOplOzo8RTqI3-3BrMgBf4FpJOGVgMxyp6Ox54"
    NEXT = "18BIDjez8kELHFFibeVEXJwj0HXtkdEMUPTN0VFewHDg"


class LveCategory(StrEnum):
    SERVICES = "services"
    OBLIGATIONS = "obligations"
    NONDURABLES = "nondurables"
    DURABLES = "durables"


class PeriodType(StrEnum):
    YEAR = "Year"
    MONTH = "Month"
    WEEK = "Week"
    DAY = "Day"


PAY_CATEGORIES: tuple[str, ...] = (
    "Housing",
    "Auto",
    "Diet",
    "Health & Self-Care",
    "Clothing",
    "Learning",
    "Electronics, Apps, & Comms",
    "Furnishings & Textiles",
    "Kitchen",
    "Cleaning",
    "Other Household Costs",
    "Transport & Travel",
    "Finance & Legal",
    "Recreation",
    "Other Costs",
)

# NOTE: Maybe derive from data source (don't store as Enum or closed set of strings).
CPI_CATEGORIES: tuple[str, ...] = (
    # Shelter
    "Rent",
    "Tenants' insurance premiums",
    "Tenants' maintenance, repairs and other expenses",
    "Electricity",
    "Water",
    "Natural gas",
    "Fuel oil and other fuels",
    # Food
    "Food",
    "Food purchased from stores",
    "Food purchased from restaurants",
    # Household Operations
    "Telephone services",
    "Internet access services",
    "Postal and other communications services",
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
    # Household Furnishing and Equpment
    "Upholstered furniture",
    "Wooden furniture",
    "Other furniture",
    "Window Coverings",
    "Bedding and other household textiles",
    "Cooking appliances",
    "Refrigerators and freezers",
    "Laundry and dishwashing appliances",
    "Other household appliances",
    "Non-electric kitchen utensils, tableware and cookware",
    "Household tools (including lawn, garden and snow removal equipment)",
    "Other household equipment",
    # Clothing
    "Men's clothing",
    "Men's footwear (excluding athletic)",
    "Athletic footwear",
    "Clothing accessories",
    "Watches",
    "Clothing material, notions and services",
    # Transportation
    "Gasoline",
    "Passenger vehicle parts, accessories and supplies",
    "Passenger vehicle maintenance and repair services",
    "Passenger vehicle insurance premiums",
    "Passenger vehicle registration fees",
    "Drivers' licences",
    "Parking fees",
    "City bus and subway transportation",
    "Air transportation",
    # Health
    "Prescribed medicines (excluding medicinal cannabis)",
    "Non-prescribed medicines",
    "Eye care goods",
    "Other health care goods",
    "Eye care services",
    "Dental care services",
    "Other health care services",
    # Personal Care
    "Personal soap",
    "Toiletry items and cosmetics",
    "Oral-hygiene products",
    "Other personal care supplies and equipment",
    "Personal care services",
    # Recreation, Education, and Reading
    "Computer equipment, software and supplies",
    "Multipurpose digital devices",
    "Recreational services",
    "School textbooks and supplies",
    "Other lessons, courses and education services",
    "Books and reading material (excluding textbooks)",
    "Alcoholic beverages purchased from stores",
)


# --------------------------------------------------------------------------
# LVE Table Data Translation Schemas
# --------------------------------------------------------------------------


DATE_DTYPE = DateTime(to_datetime_kwargs={"format": "%Y-%m-%d", "errors": "raise"})


@pda_extensions.register_check_method()
def is_non_blank(series: pd.Series) -> bool:
    """Return True if `series` is composed of strings that are non-empty."""

    return series.str.strip().ne("")


# BUG: Schemas won't handle missing cpi_category bills correctly.

PLAIN_BILL_SCHEMA = pda.DataFrameSchema(
    columns={
        "Item": pda.Column(str, pda.Check.is_non_blank(), unique=True),
        "Pay Category": pda.Column(str, pda.Check.isin(PAY_CATEGORIES)),
        "Period Cost": pda.Column(float, pda.Check.ge(0), coerce=True),
        "Period Size": pda.Column(float, pda.Check.ge(0), coerce=True),
        "Period Type": pda.Column(str, pda.Check.isin([p.value for p in PeriodType])),
        "Start Date": pda.Column(DATE_DTYPE, nullable=True, coerce=True),
        "Close Date": pda.Column(DATE_DTYPE, nullable=True, coerce=True),
        "CPI Category": pda.Column(str, pda.Check.isin(CPI_CATEGORIES)),
        "Sales Taxed": pda.Column(bool),
        "Notes": pda.Column(str),
    },
)

USAGE_BILL_SCHEMA = pda.DataFrameSchema(
    columns={
        "Item": pda.Column(str, pda.Check.is_non_blank(), unique=True),
        "Pay Category": pda.Column(str, pda.Check.isin(PAY_CATEGORIES)),
        "Unit Cost": pda.Column(float, pda.Check.ge(0), coerce=True),
        "Unit Cost Base": pda.Column(float, pda.Check.ge(0), coerce=True),
        "Unit": pda.Column(str, pda.Check.is_non_blank()),
        "Usage Rate": pda.Column(float, pda.Check.ge(0), coerce=True),
        "Period Size": pda.Column(float, pda.Check.ge(0), coerce=True),
        "Period Type": pda.Column(str, pda.Check.isin([p.value for p in PeriodType])),
        "Start Date": pda.Column(DATE_DTYPE, nullable=True, coerce=True),
        "Close Date": pda.Column(DATE_DTYPE, nullable=True, coerce=True),
        "CPI Category": pda.Column(str, pda.Check.isin(CPI_CATEGORIES)),
        "Sales Taxed": pda.Column(bool),
        "Item Notes": pda.Column(str),
        "Usage Notes": pda.Column(str),
    },
)

SUPPLY_COST_SCHEMA = pda.DataFrameSchema(
    columns={
        "Item": pda.Column(str, pda.Check.is_non_blank(), unique=True),
        "Pay Category": pda.Column(str, pda.Check.isin(PAY_CATEGORIES)),
        "Unit Cost": pda.Column(float, pda.Check.ge(0), coerce=True),
        "Supply": pda.Column(float, pda.Check.ge(0), coerce=True),
        "Demand": pda.Column(float, pda.Check.ge(0), coerce=True),
        "Sales Taxed": pda.Column(bool),
        "Notes": pda.Column(str),
    }
)


LVE_SCHEMA_BY_CATEGORY: dict[LveCategory, pda.DataFrameSchema] = {
    LveCategory.SERVICES: PLAIN_BILL_SCHEMA,
    LveCategory.OBLIGATIONS: PLAIN_BILL_SCHEMA,
    LveCategory.NONDURABLES: USAGE_BILL_SCHEMA,
    LveCategory.DURABLES: SUPPLY_COST_SCHEMA,
}


def _extract_dtypes(schema: pda.DataFrameSchema) -> dict[str, str]:
    dtypes: dict[str, str] = {}
    for name, dtype in schema.dtypes.items():
        if dtype is None:
            raise ValueError(f"Column {name!r} in schema has no dtype declared.")
        dtypes[name] = str(dtype)
    return dtypes


# --------------------------------------------------------------------------
# LVE Table Dtype Definitions
# --------------------------------------------------------------------------

PLAIN_BILL_DTYPE: dict[str, str] = _extract_dtypes(PLAIN_BILL_SCHEMA)
USAGE_BILL_DTYPE: dict[str, str] = _extract_dtypes(USAGE_BILL_SCHEMA)
SUPPLY_COST_DTYPE: dict[str, str] = _extract_dtypes(SUPPLY_COST_SCHEMA)

LVE_BILL_CATEGORIES: tuple[LveCategory, ...] = (
    LveCategory.SERVICES,
    LveCategory.OBLIGATIONS,
    LveCategory.NONDURABLES,
)


LVE_DTYPE_BY_CATEGORY: dict[LveCategory, dict[str, str]] = {
    LveCategory.SERVICES: PLAIN_BILL_DTYPE,
    LveCategory.OBLIGATIONS: PLAIN_BILL_DTYPE,
    LveCategory.NONDURABLES: USAGE_BILL_DTYPE,
    LveCategory.DURABLES: SUPPLY_COST_DTYPE,
}

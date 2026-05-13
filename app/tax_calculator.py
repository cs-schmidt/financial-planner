from math import inf

# NOTE: Module is designed to compute Canadian taxes. Regular updates are needed to keep
#       results in line with the tax code (see RESOURCES at the bottom).


class TaxBracket:
    """Represents a taxation bracket."""

    def __init__(self, min: float = 0.0, max: float = inf, rate: float = 0.0):
        # TODO: Validate parameters.
        self.min = min
        self.max = max
        self.rate = rate


# Federal and state/provincial income tax brackets (2.1).
FIT_BRACKETS = {
    1: TaxBracket(min=0.0, max=57375, rate=0.145),
    2: TaxBracket(min=57375, max=114750, rate=0.205),
    3: TaxBracket(min=114750, max=177882, rate=0.26),
    4: TaxBracket(min=177882, max=253414, rate=0.29),
    5: TaxBracket(min=253414, max=inf, rate=0.33),
}
SIT_BRACKETS = {
    1: TaxBracket(min=0.0, max=60000, rate=0.08),
    2: TaxBracket(min=60000, max=151234, rate=0.10),
    3: TaxBracket(min=151234, max=181481, rate=0.12),
    4: TaxBracket(min=181481, max=241974, rate=0.13),
    5: TaxBracket(min=241974, max=362961, rate=0.14),
    6: TaxBracket(min=362961, max=inf, rate=0.15),
}


# Base and enhanced CPP Parameters (3.1).
CPP1 = {"pensionable_max": 71300, "exemption": 3500, "added_rate": 0.01, "rate": 0.0595}
CPP2 = {"pensionable_max": 81200, "rate": 0.04}

# EI Parameters (3.2)
EI = {"insurable_max": 65700, "rate": 0.0164}

# Federal basic personal amount (4.1).
FBPA = {"min": 14538, "max": 16129}

# Provincial Basic Personal Amount (4.2).
PBPA = 22323

# Canada employment amount (4.3).
CEBA = 1471


# TODO: Add parameter validations to methods.
class TaxCalculator:
    """Calculator for taxation metrics."""

    def __init__(self, self_employed: bool = False):
        self.self_employed = self_employed

    # --------------------------------------------------------------------------
    # Public Methods
    # --------------------------------------------------------------------------

    def taxable_income(self, earned_income: float) -> float:
        """Compute taxable income."""
        return max(earned_income - self.tax_deduction(earned_income), 0)

    def tax_total(self, earned_income: float) -> float:
        """Compute total taxes owed."""
        gross_taxes = (
            self.income_tax(earned_income),
            self.cpp_contribution(earned_income),
            self.ei_premium(earned_income),
        )
        return sum(gross_taxes)

    def income_tax(self, earned_income: float) -> float:
        """Compute income tax owed."""
        income_taxes = (
            self.federal_income_tax(earned_income),
            self.state_income_tax(earned_income),
        )
        return sum(income_taxes)

    def federal_income_tax(self, earned_income: float) -> float:
        """Compute gross federal income tax owed."""
        gross_tax_due = self._get_progressive_tax(earned_income, FIT_BRACKETS)
        nr_tax_credit = self.federal_credit(earned_income)
        return max(gross_tax_due - nr_tax_credit, 0)

    def state_income_tax(self, earned_income: float) -> float:
        """Compute gross state/provincial income tax owed."""
        gross_tax_due = self._get_progressive_tax(earned_income, SIT_BRACKETS)
        nr_tax_credit = self.state_credit(earned_income)
        return max(gross_tax_due - nr_tax_credit, 0)

    def cpp_contribution(self, earned_income: float) -> float:
        """Compute CPP contribution owed."""
        contributions = (
            self.cpp1_contribution(earned_income),
            self.cpp2_contribution(earned_income),
        )
        return sum(contributions)

    def cpp1_contribution(self, earned_income: float) -> float:
        """Compute base CPP contribution owed."""
        if earned_income <= CPP1["exemption"]:
            return 0.0
        pensionable_total = min(earned_income, CPP1["pensionable_max"])
        rate = 2 * CPP1["rate"] if self.self_employed else CPP1["rate"]
        return (pensionable_total - CPP1["exemption"]) * rate

    def cpp2_contribution(self, earned_income: float) -> float:
        """Compute enhanced CPP contribution owed."""
        if earned_income <= CPP1["pensionable_max"]:
            return 0.0
        pensionable_total = min(earned_income, CPP2["pensionable_max"])
        rate = 2 * CPP2["rate"] if self.self_employed else CPP2["rate"]
        return (pensionable_total - CPP1["pensionable_max"]) * rate

    def ei_premium(self, earned_income: float) -> float:
        """Compute EI premium owed."""
        if self.self_employed:
            return 0.0
        insurable_total = min(earned_income, EI["insurable_max"])
        return insurable_total * EI["rate"]

    # Tax Deductions
    # --------------------------------------------

    def tax_deduction(self, earned_income: float) -> float:
        """Compute total tax deductions received."""
        deductions = (
            self.cpp1_deduction(earned_income),
            self.cpp2_deduction(earned_income),
        )
        return sum(deductions)

    def cpp1_deduction(self, earned_income: float) -> float:
        """Compute base CPP tax deduction."""
        if not self.self_employed:
            return 0.0
        employer_base_portion = (CPP1["rate"] - CPP1["added_rate"]) / (2 * CPP1["rate"])
        return employer_base_portion * self.cpp1_contribution(earned_income)

    def cpp2_deduction(self, earned_income: float) -> float:
        """Compute enhanced CPP tax deduction."""
        added_rate_portion = CPP1["added_rate"] / CPP1["rate"]
        return (
            added_rate_portion * self.cpp1_contribution(earned_income)
        ) + self.cpp2_contribution(earned_income)

    # Tax Credits
    # --------------------------------------------

    def tax_credit(self, earned_income: float) -> float:
        """Compute total non-refundable tax credit received."""
        return self.federal_credit(earned_income) + self.state_credit(earned_income)

    def federal_credit(self, earned_income: float) -> float:
        return self.federal_credit_total(earned_income) * FIT_BRACKETS[1].rate

    def state_credit(self, earned_income: float) -> float:
        return self.state_credit_total(earned_income) * SIT_BRACKETS[1].rate

    def federal_credit_total(self, earned_income: float) -> float:
        """Compute total non-refundable federal tax credit."""
        credits = (
            self.fbpa_credit(earned_income),
            self.cea_credit(earned_income),
            self.cpp_credit(earned_income),
            self.ei_premium(earned_income),
        )
        return sum(credits)

    def state_credit_total(self, earned_income: float) -> float:
        """Compute total non-refundable state/provincial tax credit."""
        credits = (
            self.pbpa_credit(),
            self.cpp_credit(earned_income),
            self.ei_premium(earned_income),
        )
        return sum(credits)

    def fbpa_credit(self, earned_income: float) -> float:
        """Compute Federal Basic Personal Amount (non-refundable) tax credit."""
        diminish_lower = FIT_BRACKETS[4].min
        diminish_upper = FIT_BRACKETS[4].max
        taxable_income = self.taxable_income(earned_income)
        if taxable_income <= diminish_lower:
            return FBPA["max"]
        if taxable_income >= diminish_upper:
            return FBPA["min"]
        diminish_rate = (FBPA["max"] - FBPA["min"]) / (diminish_upper - diminish_lower)
        bpa_adjusment = (taxable_income - diminish_lower) * diminish_rate
        return FBPA["max"] - bpa_adjusment

    def pbpa_credit(self) -> float:
        """Compute Provincial Basic Personal Amount (non-refundable) tax credit."""
        return PBPA

    def cea_credit(self, earned_income: float) -> float:
        """Compute Canada Employment Amount (non-refundable) tax credit."""
        if self.self_employed:
            return 0.0
        return min(CEBA, earned_income)

    def cpp_credit(self, earned_income: float) -> float:
        """Compute CPP contribution (non-refundable) tax credit."""
        if earned_income <= CPP1["exemption"]:
            return 0.0
        pensionable_total = min(earned_income, CPP1["pensionable_max"])
        rate = CPP1["rate"] - CPP1["added_rate"]
        return (pensionable_total - CPP1["exemption"]) * rate

    # --------------------------------------------------------------------------
    # Private Methods
    # --------------------------------------------------------------------------

    def _get_progressive_tax(
        self, earned_income: float, brackets: dict[int, TaxBracket]
    ) -> float:
        result = 0.0
        taxable_income = self.taxable_income(earned_income)
        for bracket in brackets.values():
            if taxable_income <= 0:
                break
            base = min(taxable_income, bracket.max - bracket.min)
            result += base * bracket.rate
            taxable_income -= base
        return result


"""
------------------------------------------------------------------------
RESOURCES (Canadian Taxes)
------------------------------------------------------------------------
(1) General:
    (1.1) Tax Tips: 
        - https://www.taxtips.ca/calculators/canadian-tax/canadian-tax-calculator.htm
(2) Income Tax:
    (2.1) Income Tax Rates: 
        - https://www.canada.ca/en/revenue-agency/services/tax/individuals/frequently-asked-questions-individuals/canadian-income-tax-rates-individuals-current-previous-years.html
(3) CPP, CPP2, and EI:
    (3.1) CPP and CPP2:
        - https://www.canada.ca/en/revenue-agency/services/tax/businesses/topics/payroll/payroll-deductions-contributions/canada-pension-plan-cpp/cpp-contribution-rates-maximums-exemptions.html
        - https://www.canada.ca/en/revenue-agency/services/tax/businesses/topics/payroll/calculating-deductions/making-deductions/second-additional-cpp-contribution-rates-maximums.html
        - https://www.taxtips.ca/cpp-qpp-and-ei/cpp-qpp-contribution-rates.htm#cpp-contributions-tax-return
    (3.2) EI: 
        - https://www.canada.ca/en/revenue-agency/services/tax/businesses/topics/payroll/payroll-deductions-contributions/employment-insurance-ei/ei-premium-rates-maximums.html
(4) Tax Credits:
    (4.1) Federal Basic Personal Amount: 
        - https://www.taxtips.ca/filing/personal-amount-tax-credit.htm
    (4.2) Provincial Basic Personal Amount: 
        - https://www.taxtips.ca/non-refundable-personal-tax-credits.htm
    (4.3) Canada Employment Amount: 
        - https://www.taxtips.ca/filing/canada-employment-amount-tax-credit.htm
"""

import math

# NOTE: Module is designed to compute Canadian federal + Alberta taxes. Regular updates
#       are needed to keep results in line with the tax code (see RESOURCES at the
#       bottom). Bracket/rate values below are 2025 vintage; Alberta and federal brackets
#       are indexed ~2% for 2026 and haven't been refreshed yet.

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
    (4.2) Alberta Basic Personal Amount:
        - https://www.taxtips.ca/non-refundable-personal-tax-credits.htm
    (4.3) Canada Employment Amount:
        - https://www.taxtips.ca/filing/canada-employment-amount-tax-credit.htm
(5) Capital Gains:
    (5.1) Inclusion Rate (50%, flat -- the 2024 proposal to raise this to 66.67%
          above $250k/year was cancelled in March 2025):
        - https://www.canada.ca/en/department-finance/news/2025/01/government-of-canada-announces-deferral-in-implementation-of-change-to-capital-gains-inclusion-rate.html
"""


class TaxBracket:
    """A single marginal-rate slice of a tax schedule."""

    def __init__(self, min_amount: float, max_amount: float, rate: float):
        if min_amount < 0:
            raise ValueError(f"min_amount must be >= 0, got {min_amount}")
        if max_amount <= min_amount:
            raise ValueError(
                f"max_amount ({max_amount}) must exceed min_amount ({min_amount})"
            )
        if not 0.0 <= rate <= 1.0:
            raise ValueError(f"rate must be between 0 and 1, got {rate}")
        self.min = min_amount
        self.max = max_amount
        self.rate = rate


class TaxSchedule:
    """An ordered, gap-free set of tax brackets, built from (threshold, rate) pairs.

    Each bracket's upper bound is derived as the next threshold (or math.inf
    for the last one), so brackets can never be built with a gap or overlap.
    """

    def __init__(self, thresholds_and_rates: list[tuple[float, float]]):
        if not thresholds_and_rates:
            raise ValueError("thresholds_and_rates must not be empty")

        ordered = sorted(thresholds_and_rates, key=lambda pair: pair[0])
        starts = [start for start, _ in ordered]
        if starts[0] != 0:
            raise ValueError(f"the first bracket must start at 0, got {starts[0]}")
        if len(starts) != len(set(starts)):
            raise ValueError("bracket start thresholds must be unique")

        brackets = []
        for i, (start, rate) in enumerate(ordered):
            end = ordered[i + 1][0] if i + 1 < len(ordered) else math.inf
            brackets.append(TaxBracket(min_amount=start, max_amount=end, rate=rate))
        self._brackets: tuple[TaxBracket, ...] = tuple(brackets)

    @property
    def brackets(self) -> tuple[TaxBracket, ...]:
        return self._brackets

    @property
    def lowest_rate(self) -> float:
        """Rate of the first bracket, used to value non-refundable credits."""
        return self._brackets[0].rate

    def tax_on(self, taxable_income: float) -> float:
        """Total progressive tax owed on a given taxable income."""
        if taxable_income < 0:
            raise ValueError(f"taxable_income must be >= 0, got {taxable_income}")
        result = 0.0
        remaining = taxable_income
        for bracket in self._brackets:
            if remaining <= 0:
                break
            base = min(remaining, bracket.max - bracket.min)
            result += base * bracket.rate
            remaining -= base
        return result


# Federal income tax schedule (2.1).
FIT_SCHEDULE = TaxSchedule(
    [
        (0, 0.145),
        (57375, 0.205),
        (114750, 0.26),
        (177882, 0.29),
        (253414, 0.33),
    ]
)
# Alberta provincial income tax schedule (2.1).
AB_SCHEDULE = TaxSchedule(
    [
        (0, 0.08),
        (60000, 0.10),
        (151234, 0.12),
        (181481, 0.13),
        (241974, 0.14),
        (362961, 0.15),
    ]
)

# Base and enhanced CPP Parameters (3.1).
CPP_1 = {"pensionable_max": 71300, "exemption": 3500, "added_rate": 0.01, "rate": 0.0595}
CPP_2 = {"pensionable_max": 81200, "rate": 0.04}
# EI Parameters (3.2)
EI = {"insurable_max": 65700, "rate": 0.0164}
# Federal basic personal amount (4.1).
FBPA = {"min": 14538, "max": 16129}
# Alberta basic personal amount (4.2).
AB_BPA = 22323
# Canada employment amount (4.3).
CEBA = 1471
# Capital gains inclusion rate for individuals (5.1).
CAPITAL_GAINS_INCLUSION_RATE = 0.5

# Federal BPA phases out between the 4th and 5th federal bracket thresholds.
FBPA_DIMINISH_LOWER = FIT_SCHEDULE.brackets[3].min
FBPA_DIMINISH_UPPER = FIT_SCHEDULE.brackets[3].max


class TaxProfiler:
    """Represents a set of data and methods for federal + Alberta tax calculations."""

    def __init__(self, self_empl: bool):
        self.self_empl = self_empl

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
            self.provincial_income_tax(earned_income),
        )
        return sum(income_taxes)

    def federal_income_tax(self, earned_income: float) -> float:
        """Compute gross federal income tax owed."""
        gross_tax_due = FIT_SCHEDULE.tax_on(self.taxable_income(earned_income))
        nr_tax_credit = self.federal_credit(earned_income)
        return max(gross_tax_due - nr_tax_credit, 0)

    def provincial_income_tax(self, earned_income: float) -> float:
        """Compute gross Alberta income tax owed."""
        gross_tax_due = AB_SCHEDULE.tax_on(self.taxable_income(earned_income))
        nr_tax_credit = self.provincial_credit(earned_income)
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
        if earned_income <= CPP_1["exemption"]:
            return 0.0
        pensionable_total = min(earned_income, CPP_1["pensionable_max"])
        rate = 2 * CPP_1["rate"] if self.self_empl else CPP_1["rate"]
        return (pensionable_total - CPP_1["exemption"]) * rate

    def cpp2_contribution(self, earned_income: float) -> float:
        """Compute enhanced CPP contribution owed."""
        if earned_income <= CPP_1["pensionable_max"]:
            return 0.0
        pensionable_total = min(earned_income, CPP_2["pensionable_max"])
        rate = 2 * CPP_2["rate"] if self.self_empl else CPP_2["rate"]
        return (pensionable_total - CPP_1["pensionable_max"]) * rate

    def ei_premium(self, earned_income: float) -> float:
        """Compute EI premium owed."""
        if self.self_empl:
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
        if not self.self_empl:
            return 0.0
        employer_base_portion = (CPP_1["rate"] - CPP_1["added_rate"]) / (
            2 * CPP_1["rate"]
        )
        return employer_base_portion * self.cpp1_contribution(earned_income)

    def cpp2_deduction(self, earned_income: float) -> float:
        """Compute enhanced CPP tax deduction."""
        added_rate_portion = CPP_1["added_rate"] / CPP_1["rate"]
        return (
            added_rate_portion * self.cpp1_contribution(earned_income)
        ) + self.cpp2_contribution(earned_income)

    # Tax Credits
    # --------------------------------------------
    def tax_credit(self, earned_income: float) -> float:
        """Compute total non-refundable tax credit received."""
        return self.federal_credit(earned_income) + self.provincial_credit(earned_income)

    def federal_credit(self, earned_income: float) -> float:
        return self.federal_credit_total(earned_income) * FIT_SCHEDULE.lowest_rate

    def provincial_credit(self, earned_income: float) -> float:
        return self.provincial_credit_total(earned_income) * AB_SCHEDULE.lowest_rate

    def federal_credit_total(self, earned_income: float) -> float:
        """Compute total non-refundable federal tax credit."""
        credits = (
            self.fbpa_credit(earned_income),
            self.cea_credit(earned_income),
            self.cpp_credit(earned_income),
            self.ei_premium(earned_income),
        )
        return sum(credits)

    def provincial_credit_total(self, earned_income: float) -> float:
        """Compute total non-refundable Alberta tax credit."""
        credits = (
            self.ab_bpa_credit(),
            self.cpp_credit(earned_income),
            self.ei_premium(earned_income),
        )
        return sum(credits)

    def fbpa_credit(self, earned_income: float) -> float:
        """Compute Federal Basic Personal Amount (non-refundable) tax credit."""
        taxable_income = self.taxable_income(earned_income)
        if taxable_income <= FBPA_DIMINISH_LOWER:
            return FBPA["max"]
        if taxable_income >= FBPA_DIMINISH_UPPER:
            return FBPA["min"]
        diminish_rate = (FBPA["max"] - FBPA["min"]) / (
            FBPA_DIMINISH_UPPER - FBPA_DIMINISH_LOWER
        )
        bpa_adjusment = (taxable_income - FBPA_DIMINISH_LOWER) * diminish_rate
        return FBPA["max"] - bpa_adjusment

    def ab_bpa_credit(self) -> float:
        """Compute Alberta Basic Personal Amount (non-refundable) tax credit."""
        return AB_BPA

    def cea_credit(self, earned_income: float) -> float:
        """Compute Canada Employment Amount (non-refundable) tax credit."""
        if self.self_empl:
            return 0.0
        return min(CEBA, earned_income)

    def cpp_credit(self, earned_income: float) -> float:
        """Compute CPP contribution (non-refundable) tax credit."""
        if earned_income <= CPP_1["exemption"]:
            return 0.0
        pensionable_total = min(earned_income, CPP_1["pensionable_max"])
        rate = CPP_1["rate"] - CPP_1["added_rate"]
        return (pensionable_total - CPP_1["exemption"]) * rate

    # Capital Gains
    # --------------------------------------------
    def taxable_capital_gain(self, capital_gain: float) -> float:
        """The portion of a capital gain added to taxable income."""
        return max(capital_gain, 0) * CAPITAL_GAINS_INCLUSION_RATE

    def capital_gains_tax(self, capital_gain: float, earned_income: float = 0.0) -> float:
        """Income tax attributable to a capital gain, stacked on top of earned_income.

        The tax on a gain depends on what bracket it lands in, which depends on your other
        income -- there's no such thing as "the" tax rate on a gain in isolation.
        earned_income defaults to 0, i.e. "the gain is my only income this year"; pass
        your salary/self-employment income to stack it on top of that instead.

        Capital gains don't affect CPP/EI, but they do stack on top of ordinary income for
        bracket purposes -- computed as the marginal difference in income tax with vs.
        without the gain, not gain * some flat rate. This is self-contained: it doesn't
        touch income_tax/tax_total, which know nothing about capital gains.
        """
        base_taxable_income = self.taxable_income(earned_income)
        stacked_taxable_income = base_taxable_income + self.taxable_capital_gain(
            capital_gain
        )

        federal_before = max(
            FIT_SCHEDULE.tax_on(base_taxable_income) - self.federal_credit(earned_income),
            0,
        )
        federal_after = max(
            FIT_SCHEDULE.tax_on(stacked_taxable_income)
            - self.federal_credit(earned_income),
            0,
        )

        state_before = max(
            AB_SCHEDULE.tax_on(base_taxable_income)
            - self.provincial_credit(earned_income),
            0,
        )
        state_after = max(
            AB_SCHEDULE.tax_on(stacked_taxable_income)
            - self.provincial_credit(earned_income),
            0,
        )

        return (federal_after - federal_before) + (state_after - state_before)

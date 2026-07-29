import math
import sys
from scipy.optimize import brentq
from tax_profiler import TaxProfiler


def lps(lve: float, r: float, i: float, tax_profiler: TaxProfiler) -> float:
    """Computes equity needed to meet inflation if living expenses, rate of return,
    and inflation hold."""

    if lve == 0 or r == 0:
        return 0.0
    if r <= i:
        return math.nan

    def residual(P: float) -> float:
        return (r - i) * P - tax_profiler.capital_gains_tax(r * P) - lve

    return brentq(residual, 0, sys.float_info.max)


def tps(lve: float, r: float, i: float, inc: float, tax_profiler: TaxProfiler) -> float:
    """Computes equity needed to meet inflation if living expenses, rate of return,
    and inflation hold."""

    if inc + lve == 0 or r == 0:
        return 0.0
    if r <= i:
        return math.nan

    def residual(P: float):
        return (r - i) * P - tax_profiler.capital_gains_tax(r * P) - (inc + lve)

    return brentq(residual, 0, sys.float_info.max)

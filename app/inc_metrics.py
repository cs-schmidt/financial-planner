import sys
from scipy.optimize import brentq
from tax_profiler import TaxProfiler


def lvi(lve: float, tax_profiler: TaxProfiler) -> float:
    """Computes income needed to meet living expenses."""

    def residual(inc: float) -> float:
        return inc - tax_profiler.tax_total(inc) - lve

    return brentq(residual, lve, sys.float_info.max)

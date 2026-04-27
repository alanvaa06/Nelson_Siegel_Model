"""
Nelson-Siegel Model Library

A Python library for yield curve modeling using the Nelson-Siegel methodology.
Supports both nominal Treasury and real TIPS yield curve analysis.
"""

__version__ = "1.1.0"
__author__ = "Economics Research Team"
__email__ = "research@example.com"

from .model import NelsonSiegelModel, TreasuryNelsonSiegelModel, TIPSNelsonSiegelModel
from .data import TreasuryDataDownloader, TIPSDataDownloader, DataManager
from .analysis import YieldCurveAnalyzer
from .plotting import YieldCurvePlotter

# Optional interactive components (requires ipywidgets)
try:
    from .interactive import InteractiveYieldCurveExplorer, HistoricalFactorExplorer, create_yield_curve_tutorial
    HAS_INTERACTIVE = True
except (ImportError, NameError):
    # NameError can occur when ipywidgets is missing because the module's
    # class annotations reference `widgets.Widget` at class definition time.
    HAS_INTERACTIVE = False

# Optional web UI (requires Flask)
try:
    from .webapp import create_app, run_app
    HAS_WEBAPP = True
except ImportError:
    HAS_WEBAPP = False

__all__ = [
    "NelsonSiegelModel",
    "TreasuryNelsonSiegelModel",
    "TIPSNelsonSiegelModel",
    "TreasuryDataDownloader",
    "TIPSDataDownloader",
    "DataManager",
    "YieldCurveAnalyzer",
    "YieldCurvePlotter",
]

if HAS_INTERACTIVE:
    __all__.extend([
        "InteractiveYieldCurveExplorer",
        "HistoricalFactorExplorer",
        "create_yield_curve_tutorial",
    ])

if HAS_WEBAPP:
    __all__.extend(["create_app", "run_app"])

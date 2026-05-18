# Fix for transformers metadata MemoryError on Windows Python 3.11
import importlib.metadata
_orig_packages_distributions = importlib.metadata.packages_distributions
def _safe_packages_distributions():
    try:
        return _orig_packages_distributions()
    except MemoryError:
        return {}
importlib.metadata.packages_distributions = _safe_packages_distributions

# Also patch importlib_metadata if it is installed and used
try:
    import importlib_metadata
    _orig_packages_distributions_fallback = importlib_metadata.packages_distributions
    def _safe_packages_distributions_fallback():
        try:
            return _orig_packages_distributions_fallback()
        except MemoryError:
            return {}
    importlib_metadata.packages_distributions = _safe_packages_distributions_fallback
except ImportError:
    pass

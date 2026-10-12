"""Bridge module exposing packages/model-adapters/ssrf_retriever.py for clean Python imports."""
import importlib.util
import os

_spec = importlib.util.spec_from_file_location(
    "model_adapters_ssrf",
    os.path.join(os.path.dirname(__file__), "model-adapters", "ssrf_retriever.py")
)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

validate_url_ssrf_safe = _mod.validate_url_ssrf_safe
sanitize_untrusted_text = _mod.sanitize_untrusted_text
ALLOWLISTED_REFERENCE_DOMAINS = _mod.ALLOWLISTED_REFERENCE_DOMAINS

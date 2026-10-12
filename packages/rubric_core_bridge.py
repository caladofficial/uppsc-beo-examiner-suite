"""Bridge module exposing packages/rubric-core/validator.py for clean Python imports."""
import importlib.util
import os

_spec = importlib.util.spec_from_file_location(
    "rubric_core_validator",
    os.path.join(os.path.dirname(__file__), "rubric-core", "validator.py")
)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

count_unicode_words = _mod.count_unicode_words
evaluate_word_limit = _mod.evaluate_word_limit
validate_and_compute_grade = _mod.validate_and_compute_grade
snap_to_increment = _mod.snap_to_increment

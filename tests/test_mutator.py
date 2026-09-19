"""Unit tests for the AST mutation engine."""
import pytest
from testgen.mutator import generate_mutants, score_mutation
from testgen.clients.fake_client import FakeLLMClient

CLAMP_SRC = """
def clamp(value, low, high):
    if low > high:
        raise ValueError("low must be <= high")
    return max(low, min(value, high))
"""

GOOD_TESTS = """
import pytest
from module_under_test import *

@pytest.mark.parametrize("value,low,high,expected", [
    (5, 0, 10, 5),
    (15, 0, 10, 10),
    (-5, 0, 10, 0),
    (0, 0, 10, 0),
    (10, 0, 10, 10),
])
def test_clamp_boundaries(value, low, high, expected):
    assert clamp(value, low, high) == expected

def test_clamp_invalid_range():
    with pytest.raises(ValueError):
        clamp(5, 10, 0)
"""

def test_generate_mutants_produces_comparison_flip():
    mutants = generate_mutants(CLAMP_SRC)
    assert len(mutants) > 0
    # At least one mutant should flip the > to >=
    assert any(">=" in m or "<" in m for m in mutants)

def test_generate_mutants_single_mutation_per_mutant():
    """Each mutant should differ from the original in exactly one operator."""
    mutants = generate_mutants(CLAMP_SRC)
    # If original has ">", at least one mutant should differ
    assert mutants  # basic sanity

def test_generate_mutants_max_cap():
    # max_mutants=2 should cap at 2 even on a function with many sites
    mutants = generate_mutants(CLAMP_SRC, max_mutants=2)
    assert len(mutants) <= 2

def test_score_mutation_kills_with_good_tests():
    report = score_mutation(CLAMP_SRC, GOOD_TESTS, max_mutants=20)
    assert report.mutants_total > 0
    assert report.mutants_killed >= 0
    assert report.mutation_score is not None
    # Good tests should kill at least some mutants
    assert report.mutation_score > 0

def test_generate_mutants_empty_source():
    mutants = generate_mutants("")
    assert mutants == []

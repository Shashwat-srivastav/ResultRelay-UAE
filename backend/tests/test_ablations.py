"""H-4: the comparison must be able to carry the claim placed on it.

Two properties are enforced here rather than asserted in prose:

1. every `ablate_*` configuration differs from the full system in exactly one input, so a difference
   in an outcome is attributable to that input and not to a package of six changes;
2. the compound baselines are marked as compound, so nothing in the report can present them as
   single-variable evidence.
"""

from __future__ import annotations

import dataclasses

import pytest

from app.evaluation.runner import changed_inputs
from app.orchestration.engine import CONFIGS

ABLATIONS = [name for name, cfg in CONFIGS.items() if cfg.ablation_of]
IGNORED = {"name", "label", "description", "ablation_of"}


def test_there_is_more_than_one_ablation():
    assert len(ABLATIONS) >= 5, "the discrimination claim needs a family of single-flag ablations"


@pytest.mark.parametrize("name", ABLATIONS)
def test_each_ablation_changes_exactly_one_input(name):
    diff = changed_inputs(name)
    assert len(diff) == 1, f"{name} changes {sorted(diff)}; an ablation may change one input"
    assert CONFIGS[name].ablation_of == "resultrelay"


@pytest.mark.parametrize("name", ABLATIONS)
def test_an_ablation_matches_the_full_system_everywhere_else(name):
    full = dataclasses.asdict(CONFIGS["resultrelay"])
    other = dataclasses.asdict(CONFIGS[name])
    differing = {
        k for k, v in other.items() if k not in IGNORED and full[k] != v
    }
    assert len(differing) == 1, differing


def test_the_compound_baselines_are_marked_compound():
    for name in ("policy_blind", "retrieval_only", "static_rules"):
        assert CONFIGS[name].ablation_of is None
        assert len(changed_inputs(name)) >= 3, f"{name} is expected to be a compound comparison"


def test_the_full_configuration_is_not_an_ablation_of_itself():
    assert CONFIGS["resultrelay"].ablation_of is None
    assert changed_inputs("resultrelay") == {}

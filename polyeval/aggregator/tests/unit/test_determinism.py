"""Unit tests for non-determinism detection — spec §8.2."""

from __future__ import annotations


def _outcomes_to_non_det(passed_outcomes: list[bool]) -> bool:
    """Reproduce the pipeline non_deterministic logic for testing."""
    return len(set(passed_outcomes)) > 1 and len(passed_outcomes) > 1


class TestNonDeterminism:
    def test_all_pass_is_deterministic(self) -> None:
        assert not _outcomes_to_non_det([True, True, True, True, True])

    def test_all_fail_is_deterministic(self) -> None:
        assert not _outcomes_to_non_det([False, False, False])

    def test_mixed_is_non_deterministic(self) -> None:
        assert _outcomes_to_non_det([True, False, True, True, False])

    def test_single_trial_never_non_deterministic(self) -> None:
        assert not _outcomes_to_non_det([True])
        assert not _outcomes_to_non_det([False])

    def test_two_trials_same_outcome(self) -> None:
        assert not _outcomes_to_non_det([True, True])

    def test_two_trials_different_outcome(self) -> None:
        assert _outcomes_to_non_det([True, False])

    def test_empty_trials(self) -> None:
        assert not _outcomes_to_non_det([])

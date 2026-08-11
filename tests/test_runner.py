import os
import pytest

"""
Unit tests for SimulationRunner.

These tests actually invoke OpenMC (via the `runner` fixture's simple
single-sphere model), so they're closer to integration tests than
true unit tests — slower than test_perturber.py, but this is the
simplest way to validate real statepoint I/O behavior without mocking
OpenMC internals. Cross-section data must be available via the
OPENMC_CROSS_SECTIONS environment variable.
"""

def test_run_returns_sane_result(runner):
    result = runner.run('nominal')
    assert 0.0 < result.keff_mean < 2.0
    assert result.keff_std > 0.0


def test_run_creates_labeled_file(runner):
    result = runner.run('nominal')
    assert os.path.basename(result.path) == 'nominal.h5'
    assert os.path.exists(result.path)


def test_run_same_label_overwrites(runner):
    result1 = runner.run('nominal')
    result2 = runner.run('nominal')
    assert result1.path == result2.path
    assert os.path.exists(result2.path)


def test_run_different_labels_produce_different_files(runner):
    result1 = runner.run('nominal')
    result2 = runner.run('perturbed')
    assert result1.path != result2.path
    assert os.path.exists(result1.path)
    assert os.path.exists(result2.path)

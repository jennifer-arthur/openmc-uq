import pytest
from openmc_uq.analysis import UQAnalysis
from openmc_uq.config import Parameter
from fakes import FakeRunner, FakePerturber
from openmc_uq.runner import RunResult
from openmc_uq.config import UncertaintyConfig


def test_compute_sensitivity_correct_value():
    param = Parameter(name='sph10.r', ptype='geometry', sigma=0.01)

    fake_runner = FakeRunner(results={
        'sph10.r_+1sigma': RunResult(keff_mean=1.00100, keff_std=0.0005, path='fake_plus.h5'),
        'sph10.r_-1sigma': RunResult(keff_mean=0.99900, keff_std=0.0005, path='fake_minus.h5'),
    })
    fake_perturber = FakePerturber()

    analysis = UQAnalysis(config=None, perturber=fake_perturber, runner=fake_runner)
    sensitivity = analysis._compute_sensitivity(param)

    expected = (1.00100 - 0.99900) / (2 * 0.01)
    assert sensitivity == pytest.approx(expected)

def test_compute_sensitivity_call_order_and_arguments():
    param = Parameter(name='sph10.r', ptype='geometry', sigma=0.01)

    fake_runner = FakeRunner(results={
        'sph10.r_+1sigma': RunResult(keff_mean=1.00100, keff_std=0.0005, path='fake_plus.h5'),
        'sph10.r_-1sigma': RunResult(keff_mean=0.99900, keff_std=0.0005, path='fake_minus.h5'),
    })
    fake_perturber = FakePerturber()

    analysis = UQAnalysis(config=None, perturber=fake_perturber, runner=fake_runner)
    analysis._compute_sensitivity(param)

    # perturb should be called with +sigma first, then -sigma
    assert fake_perturber.perturb_calls == [
        ('sph10.r', 0.01, 'geometry'),
        ('sph10.r', -0.01, 'geometry'),
    ]
    # restore should be called once after each perturb
    assert fake_perturber.restore_calls == ['sph10.r', 'sph10.r']
    # runner should be called with +1sigma before -1sigma
    assert fake_runner.calls == ['sph10.r_+1sigma', 'sph10.r_-1sigma']

def test_compute_sensitivity_restores_on_plus_run_failure():
    param = Parameter(name='sph10.r', ptype='geometry', sigma=0.01)

    fake_runner = FakeRunner(
        results={
            'sph10.r_-1sigma': RunResult(keff_mean=0.99900, keff_std=0.0005, path='fake_minus.h5'),
        },
        raises_on={'sph10.r_+1sigma': RuntimeError('simulated run failure')},
    )
    fake_perturber = FakePerturber()

    analysis = UQAnalysis(config=None, perturber=fake_perturber, runner=fake_runner)

    with pytest.raises(RuntimeError, match='simulated run failure'):
        analysis._compute_sensitivity(param)

    # restore should still have been called for the failed +1sigma leg,
    # even though the run raised
    assert fake_perturber.restore_calls == ['sph10.r']
    # the -1sigma leg should never have been attempted
    assert fake_runner.calls == ['sph10.r_+1sigma']

def test_compute_sensitivity_restores_on_minus_run_failure():
    param = Parameter(name='sph10.r', ptype='geometry', sigma=0.01)

    fake_runner = FakeRunner(
        results={
            'sph10.r_+1sigma': RunResult(keff_mean=1.00100, keff_std=0.0005, path='fake_plus.h5'),
        },
        raises_on={'sph10.r_-1sigma': RuntimeError('simulated run failure')},
    )
    fake_perturber = FakePerturber()

    analysis = UQAnalysis(config=None, perturber=fake_perturber, runner=fake_runner)

    with pytest.raises(RuntimeError, match='simulated run failure'):
        analysis._compute_sensitivity(param)

    # restore should have been called for BOTH legs: the successful
    # +1sigma leg, and the failed -1sigma leg
    assert fake_perturber.restore_calls == ['sph10.r', 'sph10.r']
    # both runner calls should have been attempted, in order
    assert fake_runner.calls == ['sph10.r_+1sigma', 'sph10.r_-1sigma']

def test_compute_sensitivity_label_formatting_with_special_characters():
    # param names can contain dots (dotted "name.attr" convention),
    # and the +/-1sigma suffixes add + and - characters -- confirm
    # the exact label strings passed to runner.run() are as expected,
    # since SimulationRunner uses them directly as filenames.
    param = Parameter(name='u1.density', ptype='density', sigma=0.0001)

    fake_runner = FakeRunner(results={
        'u1.density_+1sigma': RunResult(keff_mean=1.00050, keff_std=0.0005, path='fake_plus.h5'),
        'u1.density_-1sigma': RunResult(keff_mean=0.99950, keff_std=0.0005, path='fake_minus.h5'),
    })
    fake_perturber = FakePerturber()

    analysis = UQAnalysis(config=None, perturber=fake_perturber, runner=fake_runner)
    analysis._compute_sensitivity(param)

    assert fake_runner.calls == ['u1.density_+1sigma', 'u1.density_-1sigma']


def test_compute_sensitivities_returns_correct_length():
    parameters = [
        Parameter(name='sph10.r', ptype='geometry', sigma=0.01),
        Parameter(name='u1.density', ptype='density', sigma=0.0001),
        Parameter(name='u1.U235', ptype='isotopic', sigma=1e-4),
    ]
    config = UncertaintyConfig(parameters)

    fake_runner = FakeRunner(results={
        'sph10.r_+1sigma': RunResult(keff_mean=1.001, keff_std=0.0005, path='a.h5'),
        'sph10.r_-1sigma': RunResult(keff_mean=0.999, keff_std=0.0005, path='b.h5'),
        'u1.density_+1sigma': RunResult(keff_mean=1.002, keff_std=0.0005, path='c.h5'),
        'u1.density_-1sigma': RunResult(keff_mean=0.998, keff_std=0.0005, path='d.h5'),
        'u1.U235_+1sigma': RunResult(keff_mean=1.003, keff_std=0.0005, path='e.h5'),
        'u1.U235_-1sigma': RunResult(keff_mean=0.997, keff_std=0.0005, path='f.h5'),
    })
    fake_perturber = FakePerturber()

    analysis = UQAnalysis(config=config, perturber=fake_perturber, runner=fake_runner)
    S = analysis.compute_sensitivities()

    assert len(S) == 3

def test_compute_sensitivities_matches_config_index_order():
    # Declare parameters in a non-trivial order, and give each one a
    # distinct, easily-recognizable sensitivity so an ordering 
    # bug can be caught(e.g. S assembled by declaration order instead of
    # by config.index) rather than just "does it run without crashing."
    parameters = [
        Parameter(name='u1.U235', ptype='isotopic', sigma=1e-4),   # declared first
        Parameter(name='sph10.r', ptype='geometry', sigma=0.01),   # declared second
        Parameter(name='u1.density', ptype='density', sigma=0.0001),  # declared third
    ]
    config = UncertaintyConfig(parameters)

    # Sensitivities are engineered to be easy to tell apart:
    # u1.U235   -> (1.010 - 0.990) / (2e-4)      = 100.0
    # sph10.r   -> (1.020 - 0.980) / (2*0.01)    = 2.0
    # u1.density-> (1.030 - 0.970) / (2*0.0001)  = 300.0
    fake_runner = FakeRunner(results={
        'u1.U235_+1sigma':    RunResult(keff_mean=1.010, keff_std=0.0005, path='a.h5'),
        'u1.U235_-1sigma':    RunResult(keff_mean=0.990, keff_std=0.0005, path='b.h5'),
        'sph10.r_+1sigma':    RunResult(keff_mean=1.020, keff_std=0.0005, path='c.h5'),
        'sph10.r_-1sigma':    RunResult(keff_mean=0.980, keff_std=0.0005, path='d.h5'),
        'u1.density_+1sigma': RunResult(keff_mean=1.030, keff_std=0.0005, path='e.h5'),
        'u1.density_-1sigma': RunResult(keff_mean=0.970, keff_std=0.0005, path='f.h5'),
    })
    fake_perturber = FakePerturber()

    analysis = UQAnalysis(config=config, perturber=fake_perturber, runner=fake_runner)
    S = analysis.compute_sensitivities()

    assert S[config.index['u1.U235']] == pytest.approx(100.0)
    assert S[config.index['sph10.r']] == pytest.approx(2.0)
    assert S[config.index['u1.density']] == pytest.approx(300.0)

def test_compute_sensitivities_fails_fast_on_single_parameter_error():
    parameters = [
        Parameter(name='sph10.r', ptype='geometry', sigma=0.01),
        Parameter(name='u1.density', ptype='density', sigma=0.0001),
        Parameter(name='u1.U235', ptype='isotopic', sigma=1e-4),
    ]
    config = UncertaintyConfig(parameters)

    fake_runner = FakeRunner(
        results={
            'sph10.r_+1sigma': RunResult(keff_mean=1.001, keff_std=0.0005, path='a.h5'),
            'sph10.r_-1sigma': RunResult(keff_mean=0.999, keff_std=0.0005, path='b.h5'),
            # u1.density deliberately has no scripted results at all --
            # simulates a run failure for the second parameter
            'u1.U235_+1sigma': RunResult(keff_mean=1.003, keff_std=0.0005, path='e.h5'),
            'u1.U235_-1sigma': RunResult(keff_mean=0.997, keff_std=0.0005, path='f.h5'),
        },
        raises_on={'u1.density_+1sigma': RuntimeError('simulated run failure')},
    )
    fake_perturber = FakePerturber()

    analysis = UQAnalysis(config=config, perturber=fake_perturber, runner=fake_runner)

    with pytest.raises(RuntimeError, match='simulated run failure'):
        analysis.compute_sensitivities()

    # the first parameter (sph10.r) should have completed successfully
    # before the second (u1.density) failed
    assert fake_runner.calls == [
        'sph10.r_+1sigma', 'sph10.r_-1sigma',
        'u1.density_+1sigma',
    ]
    # the third parameter (u1.U235) should never have been attempted,
    # since the loop aborts on the first failure
    assert 'u1.U235_+1sigma' not in fake_runner.calls

def test_compute_sensitivities_empty_parameter_list():
    config = UncertaintyConfig(parameters=[])

    fake_runner = FakeRunner(results={})
    fake_perturber = FakePerturber()

    analysis = UQAnalysis(config=config, perturber=fake_perturber, runner=fake_runner)
    S = analysis.compute_sensitivities()

    assert len(S) == 0
    assert fake_runner.calls == []
    assert fake_perturber.perturb_calls == []

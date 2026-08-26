import numpy as np

class UQAnalysis:
    """Computes sensitivities and propagates uncertainty via the sandwich rule.

    Parameters
    ----------
    config : UncertaintyConfig
        Parsed parameter list and covariance matrix.
    perturber : ModelPerturber
        Wraps the model to be perturbed; must be constructed against
        the same model `runner` will run.
    runner : SimulationRunner
        Executes OpenMC and extracts keff for each perturbed state.

    Attributes
    ----------
    config : UncertaintyConfig
    perturber : ModelPerturber
    runner : SimulationRunner
    """

    def __init__(self, config, perturber, runner):
        self.config = config
        self.perturber = perturber
        self.runner = runner

    def _compute_sensitivity(self, param):
        """Estimate dkeff/dparam via a central-difference +/-1sigma perturbation.

        Perturbs `param` by +sigma, runs, restores; then by -sigma, runs,
        restores. Sensitivity is the central-difference estimate
        Si = (keff_plus - keff_minus) / (2 * sigma). Each perturb/run
        pair is wrapped so that a failed run still restores the model
        to nominal before the exception propagates.

        Parameters
        ----------
        param : Parameter
            The parameter to perturb (from `self.config.parameters`).

        Returns
        -------
        float
            Sensitivity Si = d(keff)/d(param), in keff per unit of param.

        Raises
        ------
        KeyError, RuntimeError, ValueError
            Propagated from `ModelPerturber.perturb`/`restore` or
            `SimulationRunner.run` if the parameter target is invalid
            or a run fails. The model is guaranteed to be restored to
            nominal before the exception propagates.
        """
        self.perturber.perturb(param.name, param.sigma, param.ptype)
        try:
            result_plus = self.runner.run(f'{param.name}_+1sigma')
        finally:
            self.perturber.restore(param.name)

        self.perturber.perturb(param.name, -param.sigma, param.ptype)
        try:
            result_minus = self.runner.run(f'{param.name}_-1sigma')
        finally:
            self.perturber.restore(param.name)

        return (result_plus.keff_mean - result_minus.keff_mean) / (2 * param.sigma)

    def compute_sensitivities(self):
        """Compute the sensitivity vector S for all parameters in config.

        Calls `_compute_sensitivity` for each parameter in
        `self.config.parameters`, in declaration order (matching
        `self.config.index`). Fails fast: any exception from a single
        parameter's perturb/run/restore cycle aborts the whole
        analysis and propagates to the caller.

        Returns
        -------
        np.ndarray
            Sensitivity vector S, shape (N,), ordered to match
            `self.config.index` / `self.config.covariance`.

        Raises
        ------
        KeyError, RuntimeError, ValueError
            Propagated from `_compute_sensitivity` for whichever
            parameter failed first.
        """
        S = np.zeros(len(self.config.parameters))
        for param in self.config.parameters:
            i = self.config.index[param.name]
            S[i] = self._compute_sensitivity(param)
        return S

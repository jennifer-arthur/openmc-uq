import glob
import os
import shutil
import tempfile
from dataclasses import dataclass

import openmc

@dataclass
class RunResult:
    """Result of a single OpenMC run.

    Attributes
    ----------
    keff_mean : float
        Mean k-effective from the statepoint file.
    keff_std : float
        Standard deviation of k-effective (Monte Carlo uncertainty).
    path : str
        Path to the statepoint file this result was read from.
    """
    keff_mean: float
    keff_std: float
    path: str

class SimulationRunner:
    """Runs an OpenMC model and extracts keff results.

    Parameters
    ----------
    model : openmc.Model
        The OpenMC model to run. Perturbations should be applied
        (e.g. via ModelPerturber) before calling `run`.
    output_dir : str, optional
        Directory where labeled statepoint files are kept. Created
        if it doesn't exist. Default: './openmc_uq_runs'.

    Attributes
    ----------
    model : openmc.Model
        The wrapped model.
    output_dir : str
        Resolved output directory (see above).
    """

    def __init__(self, model, output_dir='./openmc_uq_runs'):
        self.model = model
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)

    def run(self, label):
        """Run the model in its current state and extract keff.

        If the model's settings produce multiple statepoint files
        (multiple statepoint batches), the one with the highest
        batch number is used, since it reflects the most converged
        result.

        Parameters
        ----------
        label : str
            Identifies this run, e.g. 'nominal' or 'sph10.r_+1sigma'.
            Used as the output filename — must be filesystem-safe
            and unique across runs, or an existing file with the
            same label will be overwritten.

        Returns
        -------
        RunResult

        Raises
        ------
        RuntimeError
            If no statepoint file is found after the run completes.
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            self.model.run(cwd=temp_dir)

            statepoint_matches = glob.glob(os.path.join(temp_dir, 'statepoint.*.h5'))
            if not statepoint_matches:
                raise RuntimeError(
                    f"No statepoint file found in '{temp_dir}' after running "
                    f"model for label '{label}'."
                )

            def batch_number(path):
                return int(path.split('.')[-2])

            statepoint_path = max(statepoint_matches, key=batch_number)

            dest_path = os.path.join(self.output_dir, f'{label}.h5')
            shutil.move(statepoint_path, dest_path)

        with openmc.StatePoint(dest_path) as sp:
            keff_mean = sp.keff.n
            keff_std = sp.keff.s

        return RunResult(keff_mean, keff_std, dest_path)

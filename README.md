# openmc_uq

Brute-force systematic uncertainty propagation for OpenMC, inspired by benchmark evaluation methods using mcnp_pstudy.

`nuclear-engineering` `monte-carlo` `openmc` `uncertainty-quantification` `python`

## The Problem

OpenMC has no equivalent to `mcnp_pstudy`. Its Python API is powerful enough to do everything `pstudy` does — parameter sweeps, batch submission, result aggregation — and more. But that flexibility means there's no standard tool for it: everyone doing perturbation-based uncertainty studies in OpenMC ends up writing, debugging, and maintaining their own one-off scripts from scratch.

**openmc_uq** is meant to be a reusable tool. It takes an OpenMC model and a JSON uncertainty specification (for densities, isotopics, and geometry parameters), perturbs each parameter directly in memory (no input-file proliferation — OpenMC models are just Python objects), runs the perturbation study, applies the sandwich rule to combine sensitivities into a total uncertainty, flags non-linear or asymmetric responses, and outputs an HDF5 + JSON report.

**Status:** Early development. Core functionality for perturbing and restoring an OpenMC model in memory is implemented and unit-tested, as is running a model and extracting k-effective results. The perturbation loop, sandwich-rule uncertainty calculation, and HDF5/JSON reporting are still in progress.

## Install

Requires an existing [OpenMC](https://docs.openmc.org/en/stable/quickinstall.html) installation with cross-section data configured. `openmc_uq` does not install OpenMC for you.

```bash
git clone https://github.com/jennifer-arthur/openmc_uq.git
cd openmc_uq
pip install -e .
```

## Usage

Currently, in-memory perturb/restore of model parameters and running a model to extract k-effective are implemented.

```python
import openmc
from openmc_uq.perturber import ModelPerturber
from openmc_uq.runner import SimulationRunner

# Build your OpenMC model as usual, naming any surface/material you want to perturb
# ... define geometry, materials, settings ...
# e.g. a sphere surface named "sph10", a material named "u1"

model = openmc.Model()
perturber = ModelPerturber(model)
runner = SimulationRunner(model)  # output_dir defaults to './openmc_uq_runs'

# Get a baseline k-effective before perturbing anything
nominal = runner.run("nominal")
print(nominal.keff_mean, nominal.keff_std)

# Perturb a geometry parameter (surface radius) by +0.01 cm, run, then restore
perturber.perturb("sph10.r", 0.01, ptype="geometry")
result = runner.run("sph10.r_+0.01")
print(result.keff_mean, result.keff_std, result.path)
perturber.restore("sph10.r")

# Perturb a material's density by +0.001 g/cc, run, then restore
perturber.perturb("u1.density", 0.001, ptype="density")
result = runner.run("u1.density_+0.001")
perturber.restore("u1.density")

# Perturb a material's isotopic composition (add 0.0001 to U235 atom/weight fraction), run, then restore
perturber.perturb("u1.U235", 0.0001, ptype="isotopic")
result = runner.run("u1.U235_+0.0001")
perturber.restore("u1.U235")
```

## License

MIT — see [LICENSE](LICENSE) for details.

## Contributing

Solo portfolio project — not actively seeking contributions, but feel free to open an issue if something looks broken or you have suggestions.

# openmc_uq

Brute-force systematic uncertainty propagation for OpenMC, inspired by benchmark evaluation methods using mcnp_pstudy.

`nuclear-engineering` `monte-carlo` `openmc` `uncertainty-quantification` `python`

## The Problem

OpenMC has no equivalent to `mcnp_pstudy`. Its Python API is powerful enough to do everything `pstudy` does — parameter sweeps, batch submission, result aggregation — and more. But that flexibility means there's no standard tool for it: everyone doing perturbation-based uncertainty studies in OpenMC ends up writing, debugging, and maintaining their own one-off scripts from scratch.

**openmc_uq** is meant to be a reusable tool. It takes an OpenMC model and a JSON uncertainty specification (for densities, isotopics, and geometry parameters), perturbs each parameter directly in memory (no input-file proliferation — OpenMC models are just Python objects), runs the perturbation study, applies the sandwich rule to combine sensitivities into a total uncertainty, flags non-linear or asymmetric responses, and outputs an HDF5 + JSON report.

**Status:** Early development. Core functionality for perturbing and restoring an OpenMC model in memory is implemented and unit-tested. The perturbation loop, sandwich-rule uncertainty calculation, and HDF5/JSON reporting are still in progress.

## Install

Requires an existing [OpenMC](https://docs.openmc.org/en/stable/quickinstall.html) installation with cross-section data configured. `openmc_uq` does not install OpenMC for you.

```bash
git clone https://github.com/jennifer-arthur/openmc_uq.git
cd openmc_uq
pip install -e .
```

## Usage

Currently, only in-memory perturb/restore of model parameters is implemented.

```python
import openmc
from openmc_uq import ModelPerturber

# Build your OpenMC model as usual, naming any surface/material you want to perturb
# ... define geometry, materials, settings ...
# e.g. a sphere surface named "sph10", a material named "u1"
model = openmc.Model()

perturber = ModelPerturber(model)

# Perturb a geometry parameter (surface radius) by +0.01 cm
perturber.perturb("sph10.r", {"r": 0.01}, ptype="geometry")
# ... run model, record k-eff ...
# Restore to nominal before the next perturbation
perturber.restore("sph10.r", ptype="geometry")

# Perturb a material's density by +0.001 g/cc
perturber.perturb("u1.density", {"density": 0.001}, ptype="density")
# ... run model, record k-eff ...
perturber.restore("u1.density", ptype="density")

# Perturb a material's isotopic composition (add 0.0001 to U235 atom/weight fraction)
perturber.perturb("u1.delta", {"U235": 0.0001}, ptype="isotopic")
# ... run model, record k-eff ...
perturber.restore("u1.delta", ptype="isotopic")
```

## License

MIT — see [LICENSE](LICENSE) for details.

## Contributing

Solo portfolio project — not actively seeking contributions, but feel free to open an issue if something looks broken or you have suggestions.

# openmc_uq

Systematic uncertainty propagation tool for OpenMC.

Takes an OpenMC model and a structured uncertainty input file, propagates
parameter uncertainties through Monte Carlo transport via the sandwich rule,
and reports a total systematic uncertainty on keff.

## Status

Early development. Currently implemented: `ModelPerturber` (in-memory
model perturbation) and its unit tests.

## Installation

```bash
pip install -e .
```

## See Also

- [API Reference](reference.md)

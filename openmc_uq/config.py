from dataclasses import dataclass, field
import numpy as np
import json
from openmc_uq.perturber import ModelPerturber


@dataclass
class Parameter:
    """A single uncertain parameter."""
    name: str          # dotted "target.attr", e.g. "sph10.r"
    ptype: str         # 'geometry' | 'density' | 'isotopic'
    sigma: float        # 1-sigma uncertainty, absolute units


class UncertaintyConfig:
    """Holds the parameter list and covariance matrix for a UQ run.

    Attributes
    ----------
    parameters : list[Parameter]
        Parsed parameter entries, in JSON declaration order.
    index : dict[str, int]
        Maps parameter name -> its row/column in `covariance`.
    covariance : np.ndarray
        N x N covariance matrix, diagonal by default (variances = sigma^2).
    """

    def __init__(self, parameters):
        self.parameters = parameters
        self.index = {}
        self.covariance = None
        self._build_covariance()

    def _build_covariance(self):
        """Build the name->index map and diagonal covariance matrix.

        Populates `self.index` (name -> row/column) and
        `self.covariance` (N x N array, variances on the diagonal).

        Raises
        ------
        ValueError
            If two parameters share the same name.
        """
        n = len(self.parameters)
        cov = np.zeros((n, n))
        for i, p in enumerate(self.parameters):
            if p.name in self.index:
                raise ValueError(
                    f"Duplicate parameter name '{p.name}' — names must be "
                    f"unique within an UncertaintyConfig."
                )
            self.index[p.name] = i
            cov[i, i] = p.sigma ** 2
        self.covariance = cov

    @classmethod
    def from_json(cls, path):
        """Build an UncertaintyConfig from a JSON parameter file.

        Parameters
        ----------
        path : str
            Path to a JSON file with a top-level "parameters" list,
            each entry having "name", "type", and "sigma" keys.

        Returns
        -------
        UncertaintyConfig

        Raises
        ------
        ValueError
            If a parameter entry is missing a required field, has an
            unrecognized "type", or a non-positive "sigma".
        """
        with open(path) as f:
            data = json.load(f)

        required = {'name', 'type', 'sigma'}
        valid_types = {'geometry', 'density', 'isotopic'}
        parameters = []
        for entry in data['parameters']:
            missing = required - entry.keys()
            if missing:
                raise ValueError(
                    f"Parameter entry {entry} missing required field(s): "
                    f"{sorted(missing)}."
                )
            if entry['type'] not in valid_types:
                raise ValueError(
                    f"Parameter '{entry['name']}' has invalid type "
                    f"'{entry['type']}' — expected one of {sorted(valid_types)}."
                )
            if entry['sigma'] <= 0:
                raise ValueError(
                    f"Parameter '{entry['name']}' has non-positive sigma "
                    f"({entry['sigma']}) — sigma must be > 0."
                )
            parameters.append(
                Parameter(name=entry['name'], ptype=entry['type'], sigma=entry['sigma'])
            )

        return cls(parameters)

    def validate(self, model):
        """Check that every parameter's target exists in the model.

        Instantiates a ModelPerturber against `model` and confirms
        each parameter's named surface/material is present, without
        applying any perturbation.

        Parameters
        ----------
        model : openmc.Model

        Raises
        ------
        ValueError
            If a parameter's `name` isn't valid "target.attr" format.
        KeyError
            If a parameter's target surface/material doesn't exist
            in the model (propagated from ModelPerturber).
        """
        perturber = ModelPerturber(model)
        for p in self.parameters:
            perturber.resolve(p.name, p.ptype)

    def to_dict(self):
        """Serialize this config back to a from_json-compatible dict.

        Returns
        -------
        dict
            ``{"parameters": [{"name", "type", "sigma"}, ...]}`` — the
            same structure `from_json` expects, in declaration order.
            Does not include `covariance` or `index`, since both are
            fully derivable from `parameters` (see `_build_covariance`).
        """
        return {
            "parameters": [
                {"name": p.name, "type": p.ptype, "sigma": p.sigma}
                for p in self.parameters
            ]
        }

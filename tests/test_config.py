import json
import pytest
from openmc_uq.config import UncertaintyConfig, Parameter

def test_from_json_valid(tmp_path):
    data = {
        "parameters": [
            {"name": "sph10.r", "type": "geometry", "sigma": 0.005},
            {"name": "HEU6.density", "type": "density", "sigma": 0.001},
            {"name": "HEU6.U235", "type": "isotopic", "sigma": 1e-4},
        ]
    }
    path = tmp_path / "params.json"
    path.write_text(json.dumps(data))

    config = UncertaintyConfig.from_json(path)

    assert len(config.parameters) == 3
    for expected, actual in zip(data["parameters"], config.parameters):
        assert actual.name == expected["name"]
        assert actual.ptype == expected["type"]
        assert actual.sigma == expected["sigma"]

@pytest.mark.parametrize("missing_field", ["name", "type", "sigma"])
def test_from_json_missing_field(tmp_path, missing_field):
    entry = {"name": "sph10.r", "type": "geometry", "sigma": 0.005}
    del entry[missing_field]
    data = {"parameters": [entry]}
    path = tmp_path / "params.json"
    path.write_text(json.dumps(data))

    with pytest.raises(ValueError):
        UncertaintyConfig.from_json(path)

def test_from_json_invalid_type(tmp_path):
    data = {"parameters": [
        {"name": "sph10.r", "type": "bogus", "sigma": 0.005}
    ]}
    path = tmp_path / "params.json"
    path.write_text(json.dumps(data))

    with pytest.raises(ValueError):
        UncertaintyConfig.from_json(path)

@pytest.mark.parametrize("sigma", [0, -0.001])
def test_from_json_nonpositive_sigma(tmp_path, sigma):
    data = {"parameters": [
        {"name": "sph10.r", "type": "geometry", "sigma": sigma}
    ]}
    path = tmp_path / "params.json"
    path.write_text(json.dumps(data))

    with pytest.raises(ValueError):
        UncertaintyConfig.from_json(path)

def test_build_covariance_diagonal():
    params = [
        Parameter(name="sph10.r", ptype="geometry", sigma=0.005),
        Parameter(name="HEU6.density", ptype="density", sigma=0.001),
        Parameter(name="HEU6.U235", ptype="isotopic", sigma=1e-4),
    ]
    config = UncertaintyConfig(params)

    n = len(params)
    for i in range(n):
        for j in range(n):
            if i == j:
                assert config.covariance[i, j] == params[i].sigma ** 2
            else:
                assert config.covariance[i, j] == 0

def test_index_maps_names_to_rows():
    params = [
        Parameter(name="sph10.r", ptype="geometry", sigma=0.005),
        Parameter(name="HEU6.density", ptype="density", sigma=0.001),
        Parameter(name="HEU6.U235", ptype="isotopic", sigma=1e-4),
    ]
    config = UncertaintyConfig(params)

    assert config.index == {"sph10.r": 0, "HEU6.density": 1, "HEU6.U235": 2}

def test_duplicate_parameter_name():
    params = [
        Parameter(name="sph10.r", ptype="geometry", sigma=0.005),
        Parameter(name="sph10.r", ptype="geometry", sigma=0.01),
    ]
    with pytest.raises(ValueError):
        UncertaintyConfig(params)

def test_validate_success(perturber):
    params = [
        Parameter(name="sph10.r", ptype="geometry", sigma=0.005),
        Parameter(name="HEU6.density", ptype="density", sigma=0.001),
        Parameter(name="HEU6.U235", ptype="isotopic", sigma=1e-4),
    ]
    config = UncertaintyConfig(params)

    config.validate(perturber.model)

def test_validate_missing_dot(perturber):
    params = [Parameter(name="sph10r", ptype="geometry", sigma=0.005)]
    config = UncertaintyConfig(params)

    with pytest.raises(ValueError):
        config.validate(perturber.model)

def test_validate_nonexistent_target(perturber):
    params = [Parameter(name="nonexistent.r", ptype="geometry", sigma=0.005)]
    config = UncertaintyConfig(params)

    with pytest.raises(KeyError):
        config.validate(perturber.model)

def test_to_dict_roundtrip(tmp_path):
    params = [
        Parameter(name="sph10.r", ptype="geometry", sigma=0.005),
        Parameter(name="HEU6.density", ptype="density", sigma=0.001),
        Parameter(name="HEU6.U235", ptype="isotopic", sigma=1e-4),
    ]
    config = UncertaintyConfig(params)

    path = tmp_path / "roundtrip.json"
    path.write_text(json.dumps(config.to_dict()))

    reloaded = UncertaintyConfig.from_json(path)

    assert len(reloaded.parameters) == len(params)
    for original, restored in zip(params, reloaded.parameters):
        assert restored.name == original.name
        assert restored.ptype == original.ptype
        assert restored.sigma == original.sigma



import pytest
from openmc_uq.perturber import ModelPerturber

"""
Unit tests for ModelPerturber.

Testing philosophy note: most tests here are black-box (only check
perturb()/restore() inputs and outputs). A few (e.g.
test_isotopic_restore_exact_float) inspect ModelPerturber._nominals
directly to catch aliasing/float-drift bugs that have no other
observable symptom until restore() is called. This creates light
coupling to internal implementation — acceptable since these are
internals we own and expect to co-evolve with the tests, but flagged
here so it's not mistaken for accidental scope creep.
"""

##### GENERAL #########################

@pytest.mark.parametrize("param, delta, ptype", [
    ("nonexistent.r", {"r": 0.01}, "geometry"),
    ("nonexistent.density", {"density": 0.01}, "density"),
    ("nonexistent.delta", {"nonexistent": 0.01}, "isotopic"),
])
def test_nonexistent_name(perturber, param, delta, ptype):
    with pytest.raises(KeyError):
        perturber.perturb(param, delta, ptype)


@pytest.mark.parametrize("param, delta, ptype", [
    ("sph10r", {"r": 0.01}, "geometry"),
    ("HEU6..density", {"density": 0.01}, "density"),
    ("HEU6...fraction", {"U235": 4e-4}, "isotopic"),
])
def test_missing_dot(perturber, param, delta, ptype):
    with pytest.raises(ValueError):
        perturber.perturb(param, delta, ptype)


def test_duplicate_surface_name(model_dup_surface):
    with pytest.raises(ValueError):
        ModelPerturber(model_dup_surface)


def test_duplicate_material_name(model_dup_material):
    with pytest.raises(ValueError):
        ModelPerturber(model_dup_material)


@pytest.mark.parametrize("param, delta, ptype", [
    ("HEU6.density", {"density": 0.001}, "density"),
    ("HEU6.delta", {"U235": 0.01e-4}, "isotopic"),
])
def test_double_perturb(perturber, param, delta, ptype):
    perturber.perturb(param, delta, ptype)
    with pytest.raises(RuntimeError):
        perturber.perturb(param, delta, ptype)


@pytest.mark.parametrize("param, ptype", [
    ("sph10.r", "geometry"),
    ("HEU6.fraction", "isotopic"),
])
def test_restore_before_perturb(perturber, param, ptype):
    with pytest.raises(RuntimeError):
        perturber.restore(param, ptype)


##### GEOMETRY #########################

@pytest.mark.parametrize("param, delta", [
    ("sph10.r", 0.01),
    ("sph10.r", -0.01),
    ("midplane.z0", 0.01),
    ("midplane.z0", -0.01),
])
def test_geometry_perturb(perturber, param, delta):
    name, attr = param.split('.')
    nominal_value = getattr(perturber.surfaces[name], attr)

    perturber.perturb(param, {attr: delta}, "geometry")
    perturbed_value = getattr(perturber.surfaces[name], attr)
    expected = nominal_value + delta
    assert perturbed_value == expected

    perturber.restore(param, "geometry")
    restored_value = getattr(perturber.surfaces[name], attr)
    assert restored_value == nominal_value


def test_geometry_typo_attribute(perturber):
    with pytest.raises(AttributeError):
        perturber.perturb("sph10.rr", {"rr": 0.01}, "geometry")


##### DENSITY #########################

@pytest.mark.parametrize("param, delta", [
    ("HEU6.density", 0.001),
    ("HEU6.density", -0.001),
])
def test_density_perturb(perturber, param, delta):
    name, attr = param.split('.')
    material = perturber.materials[name]
    nominal_value = material.density
    nominal_units = material.density_units

    perturber.perturb(param, {attr: delta}, "density")
    expected = nominal_value + delta
    assert material.density == expected
    assert material.density_units == nominal_units

    perturber.restore(param, "density")
    assert material.density == nominal_value


def test_density_typo_attribute(perturber):
    with pytest.raises(ValueError):
        perturber.perturb("HEU6.foo", {"foo": 0.001}, "density")


##### ISOTOPICS #########################

@pytest.mark.parametrize("delta", [
    {"U235": 0.1e-2},
    {"U235": -0.1e-2},
    {"U235": 0.1e-2, "U238": -0.1e-3},
    {"U235": 0.1e-2, "U238": -0.1e-3, "U234": -0.1e-4},
])
def test_isotopic_delta(perturber, delta):
    param = "HEU6.delta"
    name, mode = param.split('.')
    material = perturber.materials[name]
    nominal = {n.name: n.percent for n in material.nuclides}
    nominal_total = sum(nominal.values())

    perturber.perturb(param, delta, "isotopic")
    perturbed = {n.name: n.percent for n in material.nuclides}

    for iso, d in delta.items():
        assert perturbed[iso] == nominal[iso] + d
    for iso in nominal:
        if iso not in delta:
            assert perturbed[iso] == nominal[iso]

    expected_total = nominal_total + sum(delta.values())
    assert abs(sum(perturbed.values()) - expected_total) < 1e-12

    perturber.restore(param, "isotopic")
    restored = {n.name: n.percent for n in material.nuclides}
    assert restored == nominal


@pytest.mark.parametrize("target", [
    {"U235": 4.4936e-2},
    {"U235": 4.4936e-2, "U238": 2.7213e-3},
    {"U235": 4.4936e-2, "U238": 2.7213e-3, "U234": 4.9357e-4},
])
def test_isotopic_fraction(perturber, target):
    param = "HEU6.fraction"
    name, mode = param.split('.')
    material = perturber.materials[name]
    nominal = {n.name: n.percent for n in material.nuclides}
    nominal_total = sum(nominal.values())

    perturber.perturb(param, target, "isotopic")
    perturbed = {n.name: n.percent for n in material.nuclides}

    for iso, t in target.items():
        assert perturbed[iso] == t
    for iso in nominal:
        if iso not in target:
            assert perturbed[iso] == nominal[iso]

    total_delta = sum(target[iso] - nominal[iso] for iso in target)
    expected_total = nominal_total + total_delta
    assert abs(sum(perturbed.values()) - expected_total) < 1e-12

    perturber.restore(param, "isotopic")
    restored = {n.name: n.percent for n in material.nuclides}
    assert restored == nominal


@pytest.mark.parametrize("param, delta_or_frac, mode", [
    ("HEU6.delta", {"U235": 0.1e-2, "U238": -0.1e-3}, "delta"),
    ("HEU6.fraction", {"U235": 4.4936e-2, "U238": 2.7213e-3}, "fraction"),
])
def test_isotopic_restore_fraction_type(perturber, param, delta_or_frac, mode):
    name, _ = param.split('.')
    material = perturber.materials[name]
    nominal_type = perturber._get_fraction_type(material)

    perturber.perturb(param, delta_or_frac, "isotopic")
    assert perturber._get_fraction_type(material) == nominal_type

    perturber.restore(param, "isotopic")
    assert perturber._get_fraction_type(material) == nominal_type


@pytest.mark.parametrize("param, delta_or_frac, mode", [
    ("HEU6.delta", {"U235": 0.1e-2, "U238": -0.1e-3}, "delta"),
    ("HEU6.fraction", {"U235": 4.4936e-2, "U238": 2.7213e-3}, "fraction"),
])
def test_isotopic_restore_order(perturber, param, delta_or_frac, mode):
    name, _ = param.split('.')
    material = perturber.materials[name]
    nominal_order = [n.name for n in material.nuclides]

    perturber.perturb(param, delta_or_frac, "isotopic")
    perturber.restore(param, "isotopic")
    restored_order = [n.name for n in material.nuclides]

    assert restored_order == nominal_order


@pytest.mark.parametrize("param, delta_or_frac, mode", [
    ("HEU6.delta", {"U235": 0.1e-2, "U238": -0.1e-3}, "delta"),
    ("HEU6.fraction", {"U235": 4.4936e-2, "U238": 2.7213e-3}, "fraction"),
])
def test_isotopic_restore_exact_float(perturber, param, delta_or_frac, mode):
    # Note: this test reaches into perturber._nominals (a private attribute)
    # to check for aliasing. That's a minor coupling to implementation
    # details, but it's the most direct way to catch this specific bug class.
    name, _ = param.split('.')
    material = perturber.materials[name]
    nominal = {n.name: n.percent for n in material.nuclides}

    perturber.perturb(param, delta_or_frac, "isotopic")

    stored_nominal = dict(perturber._nominals[param])
    assert stored_nominal == nominal

    perturber.restore(param, "isotopic")
    restored = {n.name: n.percent for n in material.nuclides}

    for iso in nominal:
        assert restored[iso] == nominal[iso]


def test_isotopic_locality(perturber):
    param_a, delta_a = "HEU6.delta", {"U235": 0.1e-3}
    param_b, delta_b = "HEU5.fraction", {"U235": 4.4e-2}
    name_a, _ = param_a.split('.')
    name_b, _ = param_b.split('.')
    mat_a = perturber.materials[name_a]
    mat_b = perturber.materials[name_b]

    nominal_a = {n.name: n.percent for n in mat_a.nuclides}
    nominal_b = {n.name: n.percent for n in mat_b.nuclides}

    perturber.perturb(param_a, delta_a, "isotopic")
    state_a_after_a = {n.name: n.percent for n in mat_a.nuclides}

    perturber.perturb(param_b, delta_b, "isotopic")
    state_a_after_b = {n.name: n.percent for n in mat_a.nuclides}
    assert state_a_after_b == state_a_after_a

    perturber.restore(param_b, "isotopic")
    state_a_after_restore_b = {n.name: n.percent for n in mat_a.nuclides}
    assert state_a_after_restore_b == state_a_after_a

    perturber.restore(param_a, "isotopic")
    assert {n.name: n.percent for n in mat_a.nuclides} == nominal_a
    assert {n.name: n.percent for n in mat_b.nuclides} == nominal_b

@pytest.mark.parametrize("param, delta", [
    ("HEU6.delat", {"U235": 0.1e-2, "U238": -0.1e-3}),
])
def test_isotopic_invalid_mode(perturber, param, delta):
    name, mode = param.split('.')
    material = perturber.materials[name]
    nominal = {n.name: n.percent for n in material.nuclides}

    with pytest.raises(ValueError):
        perturber.perturb(param, delta, "isotopic")

    current = {n.name: n.percent for n in material.nuclides}
    assert current == nominal


@pytest.mark.parametrize("param, delta", [
    ("HEU6.delta", {"U235": 0.1e-2, "U239": -0.1e-3}),
    ("HEU6.fraction", {"U235": 4.4936e-2, "U239": 2.7213e-3}),
])
def test_isotopic_unknown_isotope(perturber, param, delta):
    name, mode = param.split('.')
    material = perturber.materials[name]
    nominal = {n.name: n.percent for n in material.nuclides}

    with pytest.raises(KeyError):
        perturber.perturb(param, delta, "isotopic")

    current = {n.name: n.percent for n in material.nuclides}
    assert current == nominal


@pytest.mark.parametrize("param, delta", [
    ("HEU1.delta", {"U235": 0.1e-2, "U238": -0.1e-3}),
])
def test_isotopic_mixed_fraction_type(perturber, param, delta):
    name, mode = param.split('.')
    material = perturber.materials[name]
    nominal = {n.name: n.percent for n in material.nuclides}

    with pytest.raises(ValueError):
        perturber.perturb(param, delta, "isotopic")

    current = {n.name: n.percent for n in material.nuclides}
    assert current == nominal

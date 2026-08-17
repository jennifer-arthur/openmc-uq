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

@pytest.mark.parametrize("param, value, ptype, isotope", [
    ("nonexistent.r", 0.01, "geometry", None),
    ("nonexistent.density", 0.01, "density", None),
    ("nonexistent.delta", 0.01, "isotopic", "nonexistent"),
])
def test_nonexistent_name(perturber, param, value, ptype, isotope):
    with pytest.raises(KeyError):
        perturber.perturb(param, value, ptype, isotope=isotope)


@pytest.mark.parametrize("param, value, ptype, isotope", [
    ("sph10r", 0.01, "geometry", None),
    ("HEU6..density", 0.01, "density", None),
    ("HEU6...fraction", 4e-4, "isotopic", "U235"),
])
def test_missing_dot(perturber, param, value, ptype, isotope):
    with pytest.raises(ValueError):
        perturber.perturb(param, value, ptype, isotope=isotope)


def test_duplicate_surface_name(model_dup_surface):
    with pytest.raises(ValueError):
        ModelPerturber(model_dup_surface)


def test_duplicate_material_name(model_dup_material):
    with pytest.raises(ValueError):
        ModelPerturber(model_dup_material)


@pytest.mark.parametrize("param, value, ptype, isotope", [
    ("HEU6.density", 0.001, "density", None),
    ("HEU6.delta", 0.01e-4, "isotopic", "U235"),
])
def test_double_perturb(perturber, param, value, ptype, isotope):
    perturber.perturb(param, value, ptype, isotope=isotope)
    with pytest.raises(RuntimeError):
        perturber.perturb(param, value, ptype, isotope=isotope)


@pytest.mark.parametrize("param", [
    "sph10.r",
    "HEU6.fraction",
])
def test_restore_before_perturb(perturber, param):
    with pytest.raises(RuntimeError):
        perturber.restore(param)


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

    perturber.perturb(param, delta, "geometry")
    perturbed_value = getattr(perturber.surfaces[name], attr)
    expected = nominal_value + delta
    assert perturbed_value == expected

    perturber.restore(param)
    restored_value = getattr(perturber.surfaces[name], attr)
    assert restored_value == nominal_value


def test_geometry_typo_attribute(perturber):
    with pytest.raises(AttributeError):
        perturber.perturb("sph10.rr", 0.01, "geometry")


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

    perturber.perturb(param, delta, "density")
    expected = nominal_value + delta
    assert material.density == expected
    assert material.density_units == nominal_units

    perturber.restore(param)
    assert material.density == nominal_value


def test_density_typo_attribute(perturber):
    with pytest.raises(ValueError):
        perturber.perturb("HEU6.foo", 0.001, "density")


##### ISOTOPICS #########################

@pytest.mark.parametrize("isotope, delta", [
    ("U235", 0.1e-2),
    ("U235", -0.1e-2),
])
def test_isotopic_delta(perturber, isotope, delta):
    param = "HEU6.delta"
    name, mode = param.split('.')
    material = perturber.materials[name]
    nominal = {n.name: n.percent for n in material.nuclides}
    nominal_total = sum(nominal.values())

    perturber.perturb(param, delta, "isotopic", isotope=isotope)
    perturbed = {n.name: n.percent for n in material.nuclides}

    assert perturbed[isotope] == nominal[isotope] + delta
    for iso in nominal:
        if iso != isotope:
            assert perturbed[iso] == nominal[iso]

    expected_total = nominal_total + delta
    assert abs(sum(perturbed.values()) - expected_total) < 1e-12

    perturber.restore(param)
    restored = {n.name: n.percent for n in material.nuclides}
    assert restored == nominal


@pytest.mark.parametrize("isotope, target", [
    ("U235", 4.4936e-2),
])
def test_isotopic_fraction(perturber, isotope, target):
    param = "HEU6.fraction"
    name, mode = param.split('.')
    material = perturber.materials[name]
    nominal = {n.name: n.percent for n in material.nuclides}
    nominal_total = sum(nominal.values())

    perturber.perturb(param, target, "isotopic", isotope=isotope)
    perturbed = {n.name: n.percent for n in material.nuclides}

    assert perturbed[isotope] == target
    for iso in nominal:
        if iso != isotope:
            assert perturbed[iso] == nominal[iso]

    total_delta = target - nominal[isotope]
    expected_total = nominal_total + total_delta
    assert abs(sum(perturbed.values()) - expected_total) < 1e-12

    perturber.restore(param)
    restored = {n.name: n.percent for n in material.nuclides}
    assert restored == nominal


@pytest.mark.parametrize("param, value, isotope", [
    ("HEU6.delta", 0.1e-2, "U235"),
    ("HEU6.fraction", 4.4936e-2, "U235"),
])
def test_isotopic_restore_fraction_type(perturber, param, value, isotope):
    name, _ = param.split('.')
    material = perturber.materials[name]
    nominal_type = perturber._get_fraction_type(material)

    perturber.perturb(param, value, "isotopic", isotope=isotope)
    assert perturber._get_fraction_type(material) == nominal_type

    perturber.restore(param)
    assert perturber._get_fraction_type(material) == nominal_type


@pytest.mark.parametrize("param, value, isotope", [
    ("HEU6.delta", 0.1e-2, "U235"),
    ("HEU6.fraction", 4.4936e-2, "U235"),
])
def test_isotopic_restore_order(perturber, param, value, isotope):
    name, _ = param.split('.')
    material = perturber.materials[name]
    nominal_order = [n.name for n in material.nuclides]

    perturber.perturb(param, value, "isotopic", isotope=isotope)
    perturber.restore(param)
    restored_order = [n.name for n in material.nuclides]

    assert restored_order == nominal_order


@pytest.mark.parametrize("param, value, isotope", [
    ("HEU6.delta", 0.1e-2, "U235"),
    ("HEU6.fraction", 4.4936e-2, "U235"),
])
def test_isotopic_restore_exact_float(perturber, param, value, isotope):
    # Note: this test reaches into perturber._nominals (a private attribute)
    # to check for aliasing. That's a minor coupling to implementation
    # details, but it's the most direct way to catch this specific bug class.
    name, _ = param.split('.')
    material = perturber.materials[name]
    nominal = {n.name: n.percent for n in material.nuclides}

    perturber.perturb(param, value, "isotopic", isotope=isotope)

    stored_nominal = perturber._nominals[param]
    assert stored_nominal['value'] == nominal[isotope]

    perturber.restore(param)
    restored = {n.name: n.percent for n in material.nuclides}

    assert restored[isotope] == nominal[isotope]


def test_isotopic_locality(perturber):
    param_a, isotope_a, delta_a = "HEU6.delta", "U235", 0.1e-3
    param_b, isotope_b, delta_b = "HEU5.fraction", "U235", 4.4e-2
    name_a, _ = param_a.split('.')
    name_b, _ = param_b.split('.')
    mat_a = perturber.materials[name_a]
    mat_b = perturber.materials[name_b]

    nominal_a = {n.name: n.percent for n in mat_a.nuclides}
    nominal_b = {n.name: n.percent for n in mat_b.nuclides}

    perturber.perturb(param_a, delta_a, "isotopic", isotope=isotope_a)
    state_a_after_a = {n.name: n.percent for n in mat_a.nuclides}

    perturber.perturb(param_b, delta_b, "isotopic", isotope=isotope_b)
    state_a_after_b = {n.name: n.percent for n in mat_a.nuclides}
    assert state_a_after_b == state_a_after_a

    perturber.restore(param_b)
    state_a_after_restore_b = {n.name: n.percent for n in mat_a.nuclides}
    assert state_a_after_restore_b == state_a_after_a

    perturber.restore(param_a)
    assert {n.name: n.percent for n in mat_a.nuclides} == nominal_a
    assert {n.name: n.percent for n in mat_b.nuclides} == nominal_b
    

@pytest.mark.parametrize("param, isotope, delta", [
    ("HEU6.delat", "U235", 0.1e-2),
])
def test_isotopic_invalid_mode(perturber, param, isotope, delta):
    name, mode = param.split('.')
    material = perturber.materials[name]
    nominal = {n.name: n.percent for n in material.nuclides}

    with pytest.raises(ValueError):
        perturber.perturb(param, delta, "isotopic", isotope=isotope)

    current = {n.name: n.percent for n in material.nuclides}
    assert current == nominal


@pytest.mark.parametrize("param, isotope, delta", [
    ("HEU6.delta", "U239", 0.1e-2),
    ("HEU6.fraction", "U239", 4.4936e-2),
])
def test_isotopic_unknown_isotope(perturber, param, isotope, delta):
    name, mode = param.split('.')
    material = perturber.materials[name]
    nominal = {n.name: n.percent for n in material.nuclides}

    with pytest.raises(KeyError):
        perturber.perturb(param, delta, "isotopic", isotope=isotope)

    current = {n.name: n.percent for n in material.nuclides}
    assert current == nominal


@pytest.mark.parametrize("param, isotope, delta", [
    ("HEU1.delta", "U235", 0.1e-2),
])
def test_isotopic_mixed_fraction_type(perturber, param, isotope, delta):
    name, mode = param.split('.')
    material = perturber.materials[name]
    nominal = {n.name: n.percent for n in material.nuclides}

    with pytest.raises(ValueError):
        perturber.perturb(param, delta, "isotopic", isotope=isotope)

    current = {n.name: n.percent for n in material.nuclides}
    assert current == nominal


@pytest.mark.parametrize("param, value, ptype, isotope", [
    ("HEU6.delta", 0.1e-2, "isotopic", None),
    ("sph10.r", 0.01, "geometry", "U235"),
    ("HEU6.density", 0.001, "density", "U235"),
])
def test_isotope_argument_consistency(perturber, param, value, ptype, isotope):
    with pytest.raises(ValueError):
        perturber.perturb(param, value, ptype, isotope=isotope)

from perturber import ModelPerturber

##### GENERAL #########################
def test_nonexistent_name(perturber, param, delta, ptype):
    # Sad path: material/surface name not in model -> friendly KeyError from _get_object
    try:
        perturber.perturb(param, delta, ptype)
        assert False, f"[{param}] Expected KeyError, but perturb succeeded"
    except KeyError as e:
        print(f"PASS: {param} raised KeyError as expected")
        print(e)

def test_missing_dot(perturber, param, delta, ptype):
    # Sad path: param has no '.' -> ValueError from unpacking, caught and re-raised with clearer message
    try:
        perturber.perturb(param, delta, ptype)
        assert False, f"[{param}] Expected ValueError, but perturb succeeded"
    except ValueError as e:
        print(f"PASS: {param} raised ValueError as expected")
        print(e)
        
def test_duplicate_name(model, kind):
    # Sad path: two objects (surfaces or materials) share the same name -> ValueError from _build_named_dict
    try:
        perturber = ModelPerturber(model)
        assert False, f"Expected ValueError for duplicate {kind} name, but construction succeeded"
    except ValueError as e:
        print(f"PASS: duplicate {kind} name raised ValueError as expected")
        print(e)

def test_double_perturb(perturber, param, delta, ptype):
    # Sad path: perturb() called twice without restore() in between ->
    # RuntimeError from the _nominals guard, prevents silent overwrite of true nominal
    perturber.perturb(param, delta, ptype)
    try:
        perturber.perturb(param, delta, ptype)
        assert False, f"[{param}] Expected RuntimeError, but second perturb succeeded"
    except RuntimeError as e:
        print(f"PASS: {param} raised RuntimeError as expected")
        print(e)
    finally:
        perturber.restore(param, ptype)  # cleanup so test doesn't leak state

def test_restore_before_perturb(perturber, param, ptype):
    # Sad path: restore() called before perturb() (or after an already-restored
    # param) -> RuntimeError from the _nominals guard
    try:
        perturber.restore(param, ptype)
        assert False, f"[{param}] Expected RuntimeError, but restore succeeded"
    except RuntimeError as e:
        print(f"PASS: {param} raised RuntimeError as expected")
        print(e)

##### GEOMETRY #########################
def test_geometry_perturb(perturber, param, delta):
    # Happy path: perturb by delta (+ or -) and confirm exact restore.
    
    name, attr = param.split('.')
    nominal_value = getattr(perturber.surfaces[name], attr)
    print(nominal_value)

    # Perturb
    perturber.perturb(param, {attr: delta}, "geometry")
    perturbed_value = getattr(perturber.surfaces[name], attr)
    print(perturbed_value)

    expected = nominal_value + delta
    assert perturbed_value == expected, (
        f"[{param}] Expected {expected}, got {perturbed_value}"
    )

    # Restore
    perturber.restore(param, "geometry")
    restored_value = getattr(perturber.surfaces[name], attr)
    print(restored_value)

    assert restored_value == nominal_value, (
        f"[{param}] Restore failed: expected {nominal_value}, got {restored_value}"
    )

    print(f"PASS: {param} perturb/restore with delta={delta}")
        
def test_geometry_typo_attribute(perturber, param, delta):
    # Sad path: attribute doesn't exist on surface -> AttributeError from setattr (__slots__)
    try:
        perturber.perturb(param, delta, "geometry")
        assert False, f"[{param}] Expected AttributeError, but perturb succeeded"
    except AttributeError as e:
        print(f"PASS: {param} raised AttributeError as expected")
        print(e)

# Edge cases: unphysical attribute values or overlapping goemetries - allow OpenMC to catch this when run

##### DENSITY #########################

def test_density_perturb(perturber, param, delta):
    # Happy path: perturb density by delta (+ or -) and confirm exact restore.

    name, attr = param.split('.')
    material = perturber.materials[name]
    nominal_value = material.density
    nominal_units = material.density_units
    print(nominal_value, nominal_units)

    # Perturb
    perturber.perturb(param, {attr: delta}, "density")
    perturbed_value = material.density
    print(perturbed_value)
    expected = nominal_value + delta
    assert perturbed_value == expected, (
        f"[{param}] Expected {expected}, got {perturbed_value}"
    )
    assert material.density_units == nominal_units, (
        f"[{param}] Units changed unexpectedly: {material.density_units}"
    )

    # Restore
    perturber.restore(param, "density")
    restored_value = material.density
    print(restored_value)
    assert restored_value == nominal_value, (
        f"[{param}] Restore failed: expected {nominal_value}, got {restored_value}"
    )
    print(f"PASS: {param} perturb/restore with delta={delta}")

def test_density_typo_attribute(perturber, param, delta):
    # Sad path: attr isn't 'density' -> ValueError from explicit check
    try:
        perturber.perturb(param, delta, "density")
        assert False, f"[{param}] Expected ValueError, but perturb succeeded"
    except ValueError as e:
        print(f"PASS: {param} raised ValueError as expected")
        print(e)

# No mismatched units path - density delta is interpreted in the units of the material as defined in the model
# Negative density - allow OpenMC to catch this when run as it's user's responsibility to understand their model

##### ISOTOPICS #########################

def test_isotopic_delta(perturber, param, delta):
    # Happy path: delta mode, one or more isotopes, +/- delta.
    # Confirms each specified isotope moves by its delta; unspecified
    # isotopes are untouched. Sum shifts by exactly total_delta
    # (no renormalization — OpenMC normalizes at run time).

    name, mode = param.split('.')
    material = perturber.materials[name]
    nominal = {n.name: n.percent for n in material.nuclides}
    nominal_total = sum(nominal.values())
    print(nominal)

    # Perturb
    perturber.perturb(param, delta, "isotopic")
    perturbed = {n.name: n.percent for n in material.nuclides}
    print(perturbed)

    for iso, d in delta.items():
        expected_iso = nominal[iso] + d
        assert perturbed[iso] == expected_iso, (
            f"[{param}] Expected {iso}={expected_iso}, got {perturbed[iso]}"
        )
    for iso in nominal:
        if iso not in delta:
            assert perturbed[iso] == nominal[iso], (
                f"[{param}] Unspecified isotope {iso} changed: "
                f"expected {nominal[iso]}, got {perturbed[iso]}"
            )

    total_delta = sum(delta.values())
    expected_total = nominal_total + total_delta
    assert abs(sum(perturbed.values()) - expected_total) < 1e-12, (
        f"[{param}] Expected total {expected_total}, got {sum(perturbed.values())}"
    )

    # Restore
    perturber.restore(param, "isotopic")
    restored = {n.name: n.percent for n in material.nuclides}
    print(restored)

    assert restored == nominal, (
        f"[{param}] Restore failed: expected {nominal}, got {restored}"
    )

    print(f"PASS: {param} delta-mode perturb/restore, isotopes={list(delta.keys())}")

def test_isotopic_fraction(perturber, param, target):
    # Happy path: fraction mode, one or more isotopes.
    # `target` maps isotope -> target fraction (not a delta).
    # Confirms each specified isotope lands exactly on its target;
    # unspecified isotopes are untouched. Sum reflects the net shift
    # from specified isotopes only (no renormalization — OpenMC
    # normalizes at run time).

    name, mode = param.split('.')
    material = perturber.materials[name]
    nominal = {n.name: n.percent for n in material.nuclides}
    nominal_total = sum(nominal.values())
    print(nominal)

    # Perturb
    perturber.perturb(param, target, "isotopic")
    perturbed = {n.name: n.percent for n in material.nuclides}
    print(perturbed)

    for iso, t in target.items():
        assert perturbed[iso] == t, (
            f"[{param}] Expected {iso}={t}, got {perturbed[iso]}"
        )
    for iso in nominal:
        if iso not in target:
            assert perturbed[iso] == nominal[iso], (
                f"[{param}] Unspecified isotope {iso} changed: "
                f"expected {nominal[iso]}, got {perturbed[iso]}"
            )

    total_delta = sum(target[iso] - nominal[iso] for iso in target)
    expected_total = nominal_total + total_delta
    assert abs(sum(perturbed.values()) - expected_total) < 1e-12, (
        f"[{param}] Expected total {expected_total}, got {sum(perturbed.values())}"
    )

    # Restore
    perturber.restore(param, "isotopic")
    restored = {n.name: n.percent for n in material.nuclides}
    print(restored)

    assert restored == nominal, (
        f"[{param}] Restore failed: expected {nominal}, got {restored}"
    )

    print(f"PASS: {param} fraction-mode perturb/restore, isotopes={list(target.keys())}")

def test_isotopic_restore_fraction_type(perturber, param, delta_or_frac, mode):
    # Happy path: confirm restore() reconstructs nuclides with the same
    # percent_type ('ao'/'wo') as the pre-perturbation state.
    # mode: 'delta' or 'fraction'.

    name, ptype_attr = param.split('.')
    material = perturber.materials[name]
    nominal_type = perturber._get_fraction_type(material)
    print(f"nominal fraction_type: {nominal_type}")

    # Perturb
    perturber.perturb(param, delta_or_frac, "isotopic")
    perturbed_type = perturber._get_fraction_type(material)
    print(f"perturbed fraction_type: {perturbed_type}")
    assert perturbed_type == nominal_type, (
        f"[{param}] fraction_type changed during perturb: "
        f"expected {nominal_type}, got {perturbed_type}"
    )

    # Restore
    perturber.restore(param, "isotopic")
    restored_type = perturber._get_fraction_type(material)
    print(f"restored fraction_type: {restored_type}")
    assert restored_type == nominal_type, (
        f"[{param}] fraction_type changed after restore: "
        f"expected {nominal_type}, got {restored_type}"
    )

    print(f"PASS: {param} ({mode}) preserved fraction_type={nominal_type} through perturb/restore")


def test_isotopic_restore_order(perturber, param, delta_or_frac, mode):
    # Happy path: confirm restore() reconstructs nuclides in the same
    # order as the pre-perturbation state. mode: 'delta' or 'fraction'.

    name, ptype_attr = param.split('.')
    material = perturber.materials[name]
    nominal_order = [n.name for n in material.nuclides]
    print(f"nominal order: {nominal_order}")

    # Perturb
    perturber.perturb(param, delta_or_frac, "isotopic")
    perturbed_order = [n.name for n in material.nuclides]
    print(f"perturbed order: {perturbed_order}")

    # Restore
    perturber.restore(param, "isotopic")
    restored_order = [n.name for n in material.nuclides]
    print(f"restored order: {restored_order}")

    assert restored_order == nominal_order, (
        f"[{param}] Order changed after restore: "
        f"expected {nominal_order}, got {restored_order}"
    )

    print(f"PASS: {param} ({mode}) preserved nuclide order through perturb/restore")


def test_isotopic_restore_exact_float(perturber, param, delta_or_frac, mode):
    # Happy path: confirm restore() produces exact float equality with
    # nominal, not just closeness. Covers two concerns:
    #  (1) aliasing: mutating the perturbed material must not retroactively
    #      change the stored nominal snapshot in perturber._nominals
    #  (2) float drift: the add_nuclide/percent round-trip through
    #      perturb->restore must not introduce rounding error
    # mode: 'delta' or 'fraction'.

    name, ptype_attr = param.split('.')
    material = perturber.materials[name]
    nominal = {n.name: n.percent for n in material.nuclides}
    print(f"nominal: {nominal}")

    # Perturb
    perturber.perturb(param, delta_or_frac, "isotopic")

    # Aliasing check: stored nominal snapshot must be untouched by the
    # perturbed material's current state
    stored_nominal = dict(perturber._nominals[param])
    assert stored_nominal == nominal, (
        f"[{param}] Stored nominal snapshot diverged from true nominal "
        f"after perturb (possible aliasing): {stored_nominal} vs {nominal}"
    )

    # Restore
    perturber.restore(param, "isotopic")
    restored = {n.name: n.percent for n in material.nuclides}
    print(f"restored: {restored}")

    for iso in nominal:
        assert restored[iso] == nominal[iso], (
            f"[{param}] Float drift on restore for {iso}: "
            f"expected exactly {nominal[iso]!r}, got {restored[iso]!r} "
            f"(diff={restored[iso]-nominal[iso]!r})"
        )

    print(f"PASS: {param} ({mode}) exact float restore, no aliasing detected")

def test_isotopic_locality(perturber, param_a, delta_a, param_b, delta_b):
    # Happy path: perturbing/restoring one material while a second
    # material is also perturbed must not cross-contaminate either
    # material's live state or its stored nominal.

    name_a, mode_a = param_a.split('.')
    name_b, mode_b = param_b.split('.')
    mat_a = perturber.materials[name_a]
    mat_b = perturber.materials[name_b]

    nominal_a = {n.name: n.percent for n in mat_a.nuclides}
    nominal_b = {n.name: n.percent for n in mat_b.nuclides}

    # Perturb A, then B, while A is still perturbed
    perturber.perturb(param_a, delta_a, "isotopic")
    state_a_after_a = {n.name: n.percent for n in mat_a.nuclides}

    perturber.perturb(param_b, delta_b, "isotopic")
    state_a_after_b = {n.name: n.percent for n in mat_a.nuclides}

    assert state_a_after_b == state_a_after_a, (
        f"[{param_a}] Perturbing '{name_b}' altered already-perturbed "
        f"'{name_a}': {state_a_after_b} vs {state_a_after_a}"
    )

    # Restore B, confirm A (still perturbed) is untouched
    perturber.restore(param_b, "isotopic")
    state_a_after_restore_b = {n.name: n.percent for n in mat_a.nuclides}
    assert state_a_after_restore_b == state_a_after_a, (
        f"[{param_a}] Restoring '{name_b}' altered still-perturbed "
        f"'{name_a}': {state_a_after_restore_b} vs {state_a_after_a}"
    )

    # Restore A, confirm both are back to true nominal
    perturber.restore(param_a, "isotopic")
    restored_a = {n.name: n.percent for n in mat_a.nuclides}
    restored_b = {n.name: n.percent for n in mat_b.nuclides}
    assert restored_a == nominal_a, (
        f"[{param_a}] Restore failed: expected {nominal_a}, got {restored_a}"
    )
    assert restored_b == nominal_b, (
        f"[{param_b}] Restore failed: expected {nominal_b}, got {restored_b}"
    )

    print(f"PASS: {param_a} and {param_b} did not cross-contaminate through overlapping perturb/restore")

def test_isotopic_invalid_mode(perturber, param, delta):
    # Sad path: mode isn't 'delta' or 'fraction' -> ValueError, raised
    # before any mutation happens (material left untouched).
    name, mode = param.split('.')
    material = perturber.materials[name]
    nominal = {n.name: n.percent for n in material.nuclides}

    try:
        perturber.perturb(param, delta, "isotopic")
        assert False, f"[{param}] Expected ValueError, but perturb succeeded"
    except ValueError as e:
        print(f"PASS: {param} raised ValueError as expected")
        print(e)

    # Confirm no mutation occurred
    current = {n.name: n.percent for n in material.nuclides}
    assert current == nominal, (
        f"[{param}] Material was mutated despite invalid mode: "
        f"expected {nominal}, got {current}"
    )

def test_isotopic_unknown_isotope(perturber, param, delta):
    # Sad path: isotope name in delta/target dict isn't in the material
    # -> KeyError, raised before any mutation happens (material left
    # untouched). Applies to both 'delta' and 'fraction' modes.
    name, mode = param.split('.')
    material = perturber.materials[name]
    nominal = {n.name: n.percent for n in material.nuclides}

    try:
        perturber.perturb(param, delta, "isotopic")
        assert False, f"[{param}] Expected KeyError, but perturb succeeded"
    except KeyError as e:
        print(f"PASS: {param} raised KeyError as expected")
        print(e)

    # Confirm no mutation occurred
    current = {n.name: n.percent for n in material.nuclides}
    assert current == nominal, (
        f"[{param}] Material was mutated despite unknown isotope: "
        f"expected {nominal}, got {current}"
    )

def test_isotopic_mixed_fraction_type(perturber, param, delta):
    # Sad path: material has nuclides with mixed percent_type ('ao' and
    # 'wo') -> ValueError from _get_fraction_type, raised before any
    # mutation happens (material left untouched).
    name, mode = param.split('.')
    material = perturber.materials[name]
    nominal = {n.name: n.percent for n in material.nuclides}

    try:
        perturber.perturb(param, delta, "isotopic")
        assert False, f"[{param}] Expected ValueError, but perturb succeeded"
    except ValueError as e:
        print(f"PASS: {param} raised ValueError as expected")
        print(e)

    # Confirm no mutation occurred
    current = {n.name: n.percent for n in material.nuclides}
    assert current == nominal, (
        f"[{param}] Material was mutated despite mixed fraction type: "
        f"expected {nominal}, got {current}"
    )

#Edge case: Isotope fraction pushed negative by unphysical delta - user responsibility, let OpenMC catch it


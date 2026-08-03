class ModelPerturber:
    """Applies parameter perturbations to OpenMC model objects in memory.
    Perturbations are pure in-memory mutations (no XML export) — that
    responsibility belongs to SimulationRunner, right before it calls
    model.run().
    """

    def __init__(self, model):
        self.model = model
        self.surfaces = self._build_named_dict(
            model.geometry.get_all_surfaces().values(), 'surface'
        )
        self.materials = self._build_named_dict(model.materials, 'material')
        self._nominals = {}

    def _build_named_dict(self, objects, kind):
        named = {}
        for obj in objects:
            if not obj.name:
                continue  # unnamed objects just aren't referenceable — fine
            if obj.name in named:
                raise ValueError(
                    f"Duplicate {kind} name '{obj.name}' (IDs {named[obj.name].id} "
                    f"and {obj.id}) — names must be unique within {kind}s."
                )
            named[obj.name] = obj
        return named

    def _get_object(self, name, ptype):
        registry = self.materials if ptype in ('density', 'isotopic') else self.surfaces
        try:
            return registry[name]
        except KeyError:
            kind = 'material' if ptype in ('density', 'isotopic') else 'surface'
            available = sorted(registry.keys())
            hint = " Did you forget to name the surface using name='surf_name'?" if kind == 'surface' else ""
        raise KeyError(
            f"No {kind} named '{name}' found in model (param type '{ptype}'). "
            f"Available {kind}s: {available}.{hint}"
        )

    # Helper function for isotopics perturbations
    def _get_fraction_type(self, material):
        types = {n.percent_type for n in material.nuclides}
        if len(types) > 1:
            raise ValueError(
                f"Material '{material.name}' has mixed fraction types {types} — "
                f"expected all nuclides to use the same percent_type."
            )
        return types.pop()

    def perturb(self, param, delta, ptype):
        """Perturb a model parameter in memory.
        Args:
            param: Dotted name string. For 'geometry': "surfacename.attr".
                For 'density': "materialname.density". For 'isotopic':
                "materialname.mode", where mode is 'delta' or 'fraction'.
            delta: dict mapping keys to perturbation values.
                For 'geometry'/'density': single-entry dict, e.g.
                {"r": 0.01} or {"density": 0.001} (key is unused, only
                the value matters).
                For 'isotopic': {isotope_name: value, ...} for one or
                more isotopes; value is interpreted as a delta or a
                target fraction depending on mode. Unspecified isotopes
                are renormalized.
            ptype: 'geometry', 'density', or 'isotopic'.
        """
        try:
            name, attr = param.split('.')
        except ValueError:
            raise ValueError(
                f"Invalid param string '{param}' — expected format 'name.attr' "
                f"(e.g. 'sph10.r'), got {param.count('.')} dot(s) instead of 1."
            )
        if param in self._nominals:
            raise RuntimeError(
                f"'{param}' is already perturbed — call restore('{param}', '{ptype}') "
                f"before perturbing it again."
            )
        obj = self._get_object(name, ptype)
        if ptype == 'geometry':
            value = delta[attr]
            self._nominals[param] = getattr(obj, attr)
            setattr(obj, attr, self._nominals[param] + value)
        elif ptype == 'density':
            if attr != 'density':
                raise ValueError(
                    f"Invalid attribute '{attr}' for density perturbation of "
                    f"'{name}' — expected 'density' (e.g. '{name}.density')."
                )
            value = delta[attr]
            self._nominals[param] = (obj.density, obj.density_units)
            new_density = obj.density + value
            obj.set_density(obj.density_units, new_density)
        elif ptype == 'isotopic':
            mode = attr  # 'delta' or 'fraction'
            if mode not in ('delta', 'fraction'):
                raise ValueError(
                    f"Invalid isotopic mode '{mode}' for '{name}' — expected "
                    f"'delta' or 'fraction' (e.g. '{name}.delta' or '{name}.fraction')."
                )
            fraction_type = self._get_fraction_type(obj)
            current = {n.name: n.percent for n in obj.nuclides}
            unknown = set(delta.keys()) - set(current.keys())
            if unknown:
                raise KeyError(
                    f"Isotope(s) {sorted(unknown)} not found in material '{name}'. "
                    f"Available isotopes: {sorted(current.keys())}."
                )
            self._nominals[param] = current
            new_fractions = dict(current)
            for iso, value in delta.items():
                new_fractions[iso] = value if mode == 'fraction' else current[iso] + value
            for iso in list(current.keys()):
                obj.remove_nuclide(iso)
            for iso, frac in new_fractions.items():
                obj.add_nuclide(iso, frac, fraction_type)
        else:
            raise ValueError(f"Unknown parameter type '{ptype}' for param '{param}'")

    def restore(self, param, ptype):
        if param not in self._nominals:
            raise RuntimeError(
                f"Cannot restore '{param}' — it hasn't been perturbed "
                f"(or was already restored)."
            )
        name, attr = param.split('.')
        obj = self._get_object(name, ptype)
        if ptype == 'geometry':
            setattr(obj, attr, self._nominals[param])
        elif ptype == 'density':
            value, units = self._nominals[param]
            obj.set_density(units, value)
        elif ptype == 'isotopic':
            fraction_type = self._get_fraction_type(obj)
            for iso in list(self._nominals[param].keys()):
                obj.remove_nuclide(iso)
            for iso, frac in self._nominals[param].items():
                obj.add_nuclide(iso, frac, fraction_type)
        else:
            raise ValueError(f"Unknown parameter type '{ptype}' for param '{param}'")
        del self._nominals[param]

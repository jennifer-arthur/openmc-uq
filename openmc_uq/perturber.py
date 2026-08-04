class ModelPerturber:
    """Apply parameter perturbations to an OpenMC model in memory.

    Perturbations are pure in-memory mutations of the model's materials
    and surfaces — no XML is written. Writing the perturbed state to
    disk is SimulationRunner's responsibility, right before it calls
    ``model.run()``.

    Parameters
    ----------
    model : openmc.Model
        The OpenMC model to perturb. Materials and surfaces must be
        named (via ``name=``) to be addressable by this class.

    Attributes
    ----------
    model : openmc.Model
        The wrapped model, mutated in place by `perturb`.
    surfaces : dict[str, openmc.Surface]
        Named surfaces in the model geometry, keyed by name.
    materials : dict[str, openmc.Material]
        Named materials in the model, keyed by name.
    """

    def __init__(self, model):
        self.model = model
        self.surfaces = self._build_named_dict(
            model.geometry.get_all_surfaces().values(), 'surface'
        )
        self.materials = self._build_named_dict(model.materials, 'material')
        self._nominals = {}

    def _build_named_dict(self, objects, kind):
        """Build a name-keyed lookup dict from a collection of model objects.

        Skips unnamed objects (they simply aren't addressable by `perturb`).

        Parameters
        ----------
        objects : iterable
            Surfaces or materials to index.
        kind : str
            ``'surface'`` or ``'material'`` — used only for error messages.

        Returns
        -------
        dict[str, object]
            Mapping of object name to object.

        Raises
        ------
        ValueError
            If two objects share the same name.
        """
        named = {}
        for obj in objects:
            if not obj.name:
                continue
            if obj.name in named:
                raise ValueError(
                    f"Duplicate {kind} name '{obj.name}' (IDs {named[obj.name].id} "
                    f"and {obj.id}) — names must be unique within {kind}s."
                )
            named[obj.name] = obj
        return named

    def _get_object(self, name, ptype):
        """Look up a named material or surface by parameter type.

        Parameters
        ----------
        name : str
            Object name, as used in a dotted `param` string.
        ptype : {'geometry', 'density', 'isotopic'}
            Determines whether `name` is looked up in `materials` or
            `surfaces`.

        Returns
        -------
        openmc.Material or openmc.Surface

        Raises
        ------
        KeyError
            If no object with `name` exists in the relevant registry.
    """
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
        """Get a material's nuclide percent type, asserting it's uniform.

        Parameters
        ----------
        material : openmc.Material

        Returns
        -------
        str
            ``'ao'`` (atom fraction) or ``'wo'`` (weight fraction).

        Raises
        ------
        ValueError
            If the material's nuclides mix atom and weight fractions.
        """
        types = {n.percent_type for n in material.nuclides}
        if len(types) > 1:
            raise ValueError(
                f"Material '{material.name}' has mixed fraction types {types} — "
                f"expected all nuclides to use the same percent_type."
            )
        return types.pop()

    def perturb(self, param, delta, ptype):
        """Perturb a model parameter in memory.

        Parameters
        ----------
        param : str
            Dotted name identifying the target and attribute. Format
            depends on `ptype`:

            - ``'geometry'`` : ``"surfacename.attr"``, e.g. ``"sph10.r"``.
            - ``'density'`` : ``"materialname.density"``.
            - ``'isotopic'`` : ``"materialname.mode"``, where mode is
              ``'delta'`` or ``'fraction'``.
        delta : dict
            Perturbation values. Shape depends on `ptype`:

            - ``'geometry'`` : single-entry dict whose key must match the
              attribute name in `param`, e.g. ``{"r": 0.01}`` for
              ``param="sph10.r"``.
            - ``'density'`` : single-entry dict with key ``"density"``,
              e.g. ``{"density": 0.001}``.
            - ``'isotopic'`` : ``{isotope_name: value, ...}`` for one or
              more isotopes. `value` is added to the current fraction if
              mode is ``'delta'``, or sets the fraction directly if mode
              is ``'fraction'``. Isotopes not listed keep their current
              fraction unchanged (no renormalization is performed).
        ptype : {'geometry', 'density', 'isotopic'}
            Which kind of perturbation to apply.

        Raises
        ------
        ValueError
            If `param` isn't in ``"name.attr"`` format, if `attr` is
            invalid for the given `ptype` (e.g. not ``'density'`` for a
            density perturbation, or not ``'delta'``/``'fraction'`` for
            an isotopic one), or if `ptype` is unrecognized.
        RuntimeError
            If `param` is already perturbed (call `restore` first).
        KeyError
            If the named surface/material doesn't exist, or an isotope
            in `delta` isn't present in the target material.

        Notes
            -----
            Fractions are not renormalized to sum to 1 after a perturbation;
            OpenMC normalizes nuclide fractions internally at run time, so
            this is safe to leave as-is.
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
        """Reset a previously perturbed parameter back to its nominal value.

        Parameters
        ----------
        param : str
            The same dotted name string passed to the corresponding
            `perturb` call, e.g. ``"sph10.r"``.
        ptype : {'geometry', 'density', 'isotopic'}
            The same `ptype` passed to the corresponding `perturb` call.

        Raises
        ------
        RuntimeError
            If `param` hasn't been perturbed (or was already restored).
        KeyError
            If the named surface/material no longer exists in the model.
        ValueError
            If `ptype` is unrecognized.

        Notes
        -----
        `param` and `ptype` must match the values used in the `perturb`
        call being undone — mismatches will look up the wrong object or
        hit the "unrecognized ptype" branch rather than erroring clearly.
        """
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

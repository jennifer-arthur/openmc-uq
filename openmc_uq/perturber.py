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

    def perturb(self, param, value, ptype, isotope=None):
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
        value : float
            The perturbation magnitude. Added to the current value if
            `ptype` is ``'geometry'``, ``'density'``, or isotopic with
            mode ``'delta'``; sets the value directly if isotopic with
            mode ``'fraction'``.
        ptype : {'geometry', 'density', 'isotopic'}
            Which kind of perturbation to apply.
        isotope : str, optional
            Isotope name (e.g. ``'U235'``), required if and only if
            `ptype` is ``'isotopic'``.

        Raises
        ------
        ValueError
            If `param` isn't in ``"name.attr"`` format, if `attr` is
            invalid for the given `ptype`, if `ptype` is unrecognized,
            or if `isotope` is missing/provided inconsistently with `ptype`.
        RuntimeError
            If `param` is already perturbed (call `restore` first).
        KeyError
            If the named surface/material doesn't exist, or `isotope`
            isn't present in the target material.
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
                f"'{param}' is already perturbed — call restore('{param}') "
                f"before perturbing it again."
            )
        if ptype == 'isotopic' and isotope is None:
            raise ValueError(
                f"ptype='isotopic' requires an 'isotope' argument (e.g. isotope='U235')."
            )
        if ptype != 'isotopic' and isotope is not None:
            raise ValueError(
                f"isotope='{isotope}' was given but ptype='{ptype}' — 'isotope' is "
                f"only valid when ptype='isotopic'."
            )
        obj = self._get_object(name, ptype)
        if ptype == 'geometry':
            nominal_value = getattr(obj, attr)
            self._nominals[param] = {
                'ptype': ptype,
                'isotope': None,
                'value': nominal_value,
                'nuclide_order': None,
            }
            setattr(obj, attr, nominal_value + value)
        elif ptype == 'density':
            if attr != 'density':
                raise ValueError(
                    f"Invalid attribute '{attr}' for density perturbation of "
                    f"'{name}' — expected 'density' (e.g. '{name}.density')."
                )
            nominal_value = (obj.density, obj.density_units)
            self._nominals[param] = {
                'ptype': ptype,
                'isotope': None,
                'value': nominal_value,
                'nuclide_order': None,
            }
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
            if isotope not in current:
                raise KeyError(
                    f"Isotope '{isotope}' not found in material '{name}'. "
                    f"Available isotopes: {sorted(current.keys())}."
                )
            nuclide_order = [n.name for n in obj.nuclides]
            self._nominals[param] = {
                'ptype': ptype,
                'isotope': isotope,
                'value': current[isotope],
                'nuclide_order': nuclide_order,
            }
            new_fraction = value if mode == 'fraction' else current[isotope] + value
            obj.remove_nuclide(isotope)
            obj.add_nuclide(isotope, new_fraction, fraction_type)
        else:
            raise ValueError(f"Unknown parameter type '{ptype}' for param '{param}'")

    def restore(self, param):
            """Reset a previously perturbed parameter back to its nominal value.

            Parameters
            ----------
            param : str
                The same dotted name string passed to the corresponding
                `perturb` call, e.g. ``"sph10.r"``.

            Raises
            ------
            RuntimeError
                If `param` hasn't been perturbed (or was already restored).
            KeyError
                If the named surface/material no longer exists in the model.
            ValueError
                If the stored `ptype` is unrecognized (should not occur
                in normal use).
            """
            if param not in self._nominals:
                raise RuntimeError(
                    f"Cannot restore '{param}' — it hasn't been perturbed "
                    f"(or was already restored)."
                )
            record = self._nominals[param]
            ptype = record['ptype']
            isotope = record['isotope']
            name, attr = param.split('.')
            obj = self._get_object(name, ptype)
            if ptype == 'geometry':
                setattr(obj, attr, record['value'])
            elif ptype == 'density':
                value, units = record['value']
                obj.set_density(units, value)
            elif ptype == 'isotopic':
                fraction_type = self._get_fraction_type(obj)
                current = {n.name: n.percent for n in obj.nuclides}
                current[isotope] = record['value']
                for n in list(obj.nuclides):
                    obj.remove_nuclide(n.name)
                for n_name in record['nuclide_order']:
                    obj.add_nuclide(n_name, current[n_name], fraction_type)
            else:
                raise ValueError(f"Unknown parameter type '{ptype}' for param '{param}'")
            del self._nominals[param]

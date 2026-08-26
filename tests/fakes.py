class FakeRunner:
    """Stand-in for SimulationRunner that returns pre-scripted results.

    Used in analysis.py tests so sensitivity calculations can be
    verified without running real OpenMC. Records every label passed
    to `run()`, in call order, so tests can also assert on call
    order/arguments (e.g. +1sigma requested before -1sigma).

    Parameters
    ----------
    results : dict[str, RunResult]
        Maps a run label to the RunResult that should be returned
        when `run()` is called with that label.
    raises_on : dict[str, Exception], optional
        Maps a run label to an exception *instance* that should be
        raised (instead of returning a result) when `run()` is called
        with that label. Used to test restore-on-failure behavior.
        Default: no labels raise.

    Attributes
    ----------
    results : dict[str, RunResult]
    raises_on : dict[str, Exception]
    calls : list[str]
        Labels passed to `run()`, in the order they were received —
        recorded even for labels that raise.
    """

    def __init__(self, results, raises_on=None):
        self.results = results
        self.raises_on = raises_on or {}
        self.calls = []

    def run(self, label):
        """Record the call, then raise or return the scripted outcome.

        Parameters
        ----------
        label : str

        Returns
        -------
        RunResult

        Raises
        ------
        Exception
            The exact exception instance registered for `label` in
            `raises_on`, if present.
        KeyError
            If `label` is in neither `results` nor `raises_on` —
            signals the caller requested a run we didn't expect,
            which usually means a label-formatting bug.
        """
        self.calls.append(label)
        if label in self.raises_on:
            raise self.raises_on[label]
        try:
            return self.results[label]
        except KeyError:
            raise KeyError(
                f"FakeRunner received unexpected label '{label}' — "
                f"not in scripted results {sorted(self.results.keys())} "
                f"or raises_on {sorted(self.raises_on.keys())}."
            )

class FakePerturber:
    """Stand-in for ModelPerturber that records calls instead of mutating a model.

    Used in analysis.py tests so sensitivity calculations can be
    verified without a real openmc.Model. Records every perturb/restore
    call, in order, so tests can assert on call order and arguments
    (e.g. restore happens even after a failed run).

    Parameters
    ----------
    raises_on_perturb : dict[str, Exception], optional
        Maps a param name to an exception instance that `perturb()`
        should raise when called with that name, instead of recording
        the call normally. Default: no params raise.
    raises_on_restore : dict[str, Exception], optional
        Same, but for `restore()`. Default: no params raise.

    Attributes
    ----------
    perturb_calls : list[tuple[str, float, str]]
        (param_name, value, ptype) for every `perturb()` call received,
        in order — including calls that went on to raise.
    restore_calls : list[str]
        param_name for every `restore()` call received, in order —
        including calls that went on to raise.
    """

    def __init__(self, raises_on_perturb=None, raises_on_restore=None):
        self.raises_on_perturb = raises_on_perturb or {}
        self.raises_on_restore = raises_on_restore or {}
        self.perturb_calls = []
        self.restore_calls = []

    def perturb(self, param, value, ptype):
        """Record the call, then raise if `param` is registered to fail.

        Parameters
        ----------
        param : str
        value : float
        ptype : str

        Raises
        ------
        Exception
            The exact exception instance registered for `param` in
            `raises_on_perturb`, if present.
        """
        self.perturb_calls.append((param, value, ptype))
        if param in self.raises_on_perturb:
            raise self.raises_on_perturb[param]

    def restore(self, param):
        """Record the call, then raise if `param` is registered to fail.

        Parameters
        ----------
        param : str

        Raises
        ------
        Exception
            The exact exception instance registered for `param` in
            `raises_on_restore`, if present.
        """
        self.restore_calls.append(param)
        if param in self.raises_on_restore:
            raise self.raises_on_restore[param]

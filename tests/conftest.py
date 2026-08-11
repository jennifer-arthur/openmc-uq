import pytest
import openmc
from openmc_uq.perturber import ModelPerturber
from openmc_uq.runner import SimulationRunner

"""
Pytest fixtures for ModelPerturber tests.

Fixtures:
- perturber: ModelPerturber built on the full Godiva benchmark model
  (6 HEU shells + air gaps). Used for most tests, and required for
  any isotopic test referencing 'HEU5'/'HEU6' specifically.
- perturber_simple: ModelPerturber built on a single-sphere, single-
  material model. Use when a test only needs to prove general
  mechanics (e.g. geometry perturb/restore) without Godiva's full
  complexity.
- runner: SimulationRunner built on the simple single-sphere model
  (via _build_simple_model()). Runs real OpenMC simulations in a
  pytest tmp_path directory, so no cross-section-heavy Godiva runs
  and no pollution of the real project output directory.
- model_dup_surface / model_dup_material: raw openmc.Model instances
  (not yet wrapped in ModelPerturber) with intentionally duplicated
  surface/material names, for testing the _build_named_dict()
  ValueError guard in ModelPerturber's constructor.
"""

@pytest.fixture
def perturber():
    # --- Materials ---
    u1 = openmc.Material(name='HEU1')
    u1.add_nuclide('U234', 4.9357e-4, 'ao')
    u1.add_nuclide('U235', 4.4936e-2, 'wo')
    u1.add_nuclide('U238', 2.7213e-3, 'ao')
    u1.set_density('atom/b-cm', 0.04815087)

    u2 = openmc.Material(name='HEU2')
    u2.add_nuclide('U234', 4.9357e-4, 'ao')
    u2.add_nuclide('U235', 4.5244e-2, 'ao')
    u2.add_nuclide('U238', 2.4168e-3, 'ao')
    u2.set_density('atom/b-cm', 0.04815437)

    u3 = openmc.Material(name='HEU3')
    u3.add_nuclide('U234', 4.9357e-4, 'ao')
    u3.add_nuclide('U235', 4.5268e-2, 'ao')
    u3.add_nuclide('U238', 2.3930e-3, 'ao')
    u3.set_density('atom/b-cm', 0.04815457)

    u4 = openmc.Material(name='HEU4')
    u4.add_nuclide('U234', 4.9357e-4, 'ao')
    u4.add_nuclide('U235', 4.5090e-2, 'ao')
    u4.add_nuclide('U238', 2.5690e-3, 'ao')
    u4.set_density('atom/b-cm', 0.04815257)

    u5 = openmc.Material(name='HEU5')
    u5.add_nuclide('U234', 4.9357e-4, 'ao')
    u5.add_nuclide('U235', 4.5239e-2, 'ao')
    u5.add_nuclide('U238', 2.4215e-3, 'ao')
    u5.set_density('atom/b-cm', 0.04815407)

    u6 = openmc.Material(name='HEU6')
    u6.add_nuclide('U234', 4.8974e-4, 'ao')
    u6.add_nuclide('U235', 4.4874e-2, 'ao')
    u6.add_nuclide('U238', 2.4169e-3, 'ao')
    u6.set_density('atom/b-cm', 0.04778447)

    air = openmc.Material(name='air')
    air.add_nuclide('N14', 3.5214e-5, 'ao')
    air.add_nuclide('O16', 1.5092e-5, 'ao')
    air.set_density('atom/b-cm', 5.0306e-5)

    materials = openmc.Materials([u1, u2, u3, u4, u5, u6, air])

    # --- Geometry ---
    sph1 = openmc.Sphere(r=1.0216)
    sph2 = openmc.Sphere(r=1.0541)
    sph3 = openmc.Sphere(r=6.2809)
    sph4 = openmc.Sphere(r=6.2937)
    sph5 = openmc.Sphere(r=7.7525)
    sph6 = openmc.Sphere(r=7.7620)
    sph7 = openmc.Sphere(r=8.2527)
    sph8 = openmc.Sphere(r=8.2610)
    sph9 = openmc.Sphere(r=8.7062)
    sph10 = openmc.Sphere(r=8.7499, boundary_type='vacuum', name="sph10")
    p1 = openmc.ZPlane(z0=0, name='midplane')

    ball = openmc.Cell(fill=u1, region=-sph1)
    gap1 = openmc.Cell(fill=air, region=+sph1 & -sph2)
    shell1 = openmc.Cell(fill=u2, region=+sph2 & -sph3)
    gap2 = openmc.Cell(fill=air, region=+sph3 & -sph4)
    shell2 = openmc.Cell(fill=u3, region=+sph4 & -sph5)
    gap3 = openmc.Cell(fill=air, region=+sph5 & -sph6)
    shell3 = openmc.Cell(fill=u4, region=+sph6 & -sph7)
    gap4 = openmc.Cell(fill=air, region=+sph7 & -sph8)
    shell4 = openmc.Cell(fill=u5, region=+sph8 & -sph9)
    hemishell1 = openmc.Cell(fill=u6, region=+sph9 & -sph10 & -p1)
    hemishell2 = openmc.Cell(fill=u6, region=+sph9 & -sph10 & +p1)

    universe = openmc.Universe(cells=[
        ball, gap1, gap2, gap3, gap4,
        shell1, shell2, shell3, shell4,
        hemishell1, hemishell2
    ])
    geometry = openmc.Geometry(universe)

    # --- Settings ---
    settings = openmc.Settings()
    settings.batches = 300
    settings.inactive = 20
    settings.particles = 10000
    settings.source = openmc.IndependentSource(
        space=openmc.stats.Point((0, 0, 0))
    )

    model = openmc.Model(geometry=geometry, materials=materials, settings=settings)
    return ModelPerturber(model)


def _build_simple_model():
    u235 = openmc.Material(name='u1')
    u235.add_nuclide('U234', 4.9184e-4, 'ao')
    u235.add_nuclide('U235', 4.4994e-2, 'ao')
    u235.add_nuclide('U238', 2.4984e-3, 'ao')
    u235.set_density('atom/b-cm', 0.04798424)
    materials = openmc.Materials([u235])

    sphere = openmc.Sphere(r=8.7407, boundary_type='vacuum', name='sph10')
    cell = openmc.Cell(fill=u235, region=-sphere)
    universe = openmc.Universe(cells=[cell])
    geometry = openmc.Geometry(universe)

    settings = openmc.Settings()
    settings.batches = 300
    settings.inactive = 20
    settings.particles = 10000
    settings.source = openmc.IndependentSource(
        space=openmc.stats.Point((0, 0, 0))
    )

    return openmc.Model(geometry=geometry, materials=materials, settings=settings)


@pytest.fixture
def perturber_simple():
    return ModelPerturber(_build_simple_model())

@pytest.fixture
def runner(tmp_path):
    return SimulationRunner(_build_simple_model(), output_dir=tmp_path)

def _build_dup_surface_model():
    mat = openmc.Material(name='mat')
    mat.add_nuclide('U235', 1.0, 'ao')
    mat.set_density('atom/b-cm', 0.04798424)
    materials = openmc.Materials([mat])

    sph_a = openmc.Sphere(r=5.0, name='dup')
    sph_b = openmc.Sphere(r=8.0, boundary_type='vacuum', name='dup')
    inner = openmc.Cell(fill=mat, region=-sph_a)
    outer = openmc.Cell(fill=mat, region=+sph_a & -sph_b)
    universe = openmc.Universe(cells=[inner, outer])
    geometry = openmc.Geometry(universe)

    return openmc.Model(geometry=geometry, materials=materials)


def _build_dup_material_model():
    mat_a = openmc.Material(name='dup')
    mat_a.add_nuclide('U235', 1.0, 'ao')
    mat_a.set_density('atom/b-cm', 0.04798424)
    mat_b = openmc.Material(name='dup')
    mat_b.add_nuclide('U238', 1.0, 'ao')
    mat_b.set_density('atom/b-cm', 0.04798424)
    materials = openmc.Materials([mat_a, mat_b])

    sphere = openmc.Sphere(r=8.0, boundary_type='vacuum', name='sph')
    cell = openmc.Cell(fill=mat_a, region=-sphere)
    universe = openmc.Universe(cells=[cell])
    geometry = openmc.Geometry(universe)

    return openmc.Model(geometry=geometry, materials=materials)


@pytest.fixture
def model_dup_surface():
    return _build_dup_surface_model()


@pytest.fixture
def model_dup_material():
    return _build_dup_material_model()

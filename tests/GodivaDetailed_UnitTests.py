from perturber import ModelPerturber
from UnitTests import *
import openmc
openmc.config['cross_sections'] = '../openmc_data/endf-b8.0-hdf5/endfb-viii.0-hdf5/cross_sections.xml'

# --- Materials ---
# HEU
u1 = openmc.Material(name='HEU1')
u1.add_nuclide('U234', 4.9357e-4, 'ao')
u1.add_nuclide('U235', 4.4936e-2, 'wo')
u1.add_nuclide('U238', 2.7213e-3, 'ao')
u1.set_density('atom/b-cm', 0.04815087)
# u1.set_density('sum')
u2 = openmc.Material(name='HEU2')
u2.add_nuclide('U234', 4.9357e-4, 'ao')
u2.add_nuclide('U235', 4.5244e-2, 'ao')
u2.add_nuclide('U238', 2.4168e-3, 'ao')
u2.set_density('atom/b-cm', 0.04815437)
# u2.set_density('sum')
u3 = openmc.Material(name='HEU3')
u3.add_nuclide('U234', 4.9357e-4, 'ao')
u3.add_nuclide('U235', 4.5268e-2, 'ao')
u3.add_nuclide('U238', 2.3930e-3, 'ao')
u3.set_density('atom/b-cm', 0.04815457)
# u3.set_density('sum')
u4 = openmc.Material(name='HEU4')
u4.add_nuclide('U234', 4.9357e-4, 'ao')
u4.add_nuclide('U235', 4.5090e-2, 'ao')
u4.add_nuclide('U238', 2.5690e-3, 'ao')
u4.set_density('atom/b-cm', 0.04815257)
# u4.set_density('sum')
u5 = openmc.Material(name='HEU5')
u5.add_nuclide('U234', 4.9357e-4, 'ao')
u5.add_nuclide('U235', 4.5239e-2, 'ao')
u5.add_nuclide('U238', 2.4215e-3, 'ao')
u5.set_density('atom/b-cm', 0.04815407)
# u5.set_density('sum')
u6 = openmc.Material(name='HEU6')
u6.add_nuclide('U234', 4.8974e-4, 'ao')
u6.add_nuclide('U235', 4.4874e-2, 'ao')
u6.add_nuclide('U238', 2.4169e-3, 'ao')
u6.set_density('atom/b-cm', 0.04778447)
# u6.set_density('sum')
# Air
air = openmc.Material(name='air')
#air = openmc.Material(name='HEU6') # duplicate material names for testing
air.add_nuclide('N14',3.5214e-5, 'ao')
air.add_nuclide('O16',1.5092e-5, 'ao')
air.set_density('atom/b-cm', 5.0306e-5)

# Compile
materials = openmc.Materials([u1, u2, u3, u4, u5, u6, air])

# --- Geometry ---
# Spheres
sph1 = openmc.Sphere(r=1.0216)
sph2 = openmc.Sphere(r=1.0541)
sph3 = openmc.Sphere(r=6.2809)
sph4 = openmc.Sphere(r=6.2937)
sph5 = openmc.Sphere(r=7.7525)
sph6 = openmc.Sphere(r=7.7620)
sph7 = openmc.Sphere(r=8.2527)
sph8 = openmc.Sphere(r=8.2610)
sph9 = openmc.Sphere(r=8.7062)
#sph9 = openmc.Sphere(r=8.7062, name="sph10") # duplicate surface names for testing 
sph10 = openmc.Sphere(r=8.7499, boundary_type='vacuum', name="sph10")
# Midplane added for geometry perturbation testing purposes
p1 = openmc.ZPlane(z0=0, name='midplane')

# Cells
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

# Universe
universe = openmc.Universe(cells=[ball,gap1,gap2,gap3,gap4,shell1,shell2,shell3,shell4,hemishell1,hemishell2])
geometry = openmc.Geometry(universe)

# --- Settings ---
settings = openmc.Settings()
settings.batches = 300 # 3,000 in actual benchmark
settings.inactive = 20
settings.particles = 10000
settings.source = openmc.IndependentSource(
    space=openmc.stats.Point((0, 0, 0))
)

# --- Tests ---
model = openmc.Model(
    geometry=geometry, 
    materials=materials, 
    settings=settings
)
perturber = ModelPerturber(model)
# General ####
# Sad paths
# Surface/material name not in model
##test_nonexistent_name(perturber, "nonexistent.r", {"r": 0.01},'geometry')
##test_nonexistent_name(perturber, "nonexistent.density", {"density": 0.01},'density')
#est_nonexistent_name(perturber, "nonexistent.delta", {"nonexistent": 0.01},'isotopic')
# Missing or duplicate '.'
##test_missing_dot(perturber, "sph10r", {"r": 0.01},'geometry')
##test_missing_dot(perturber, "HEU6..density", {"density": 0.01},'density')
#test_missing_dot(perturber, "HEU6...fraction", {"U235": 4E-4},'isotopic')
# Two objects share the same name
#test_duplicate_name(model, "surface")
#test_duplicate_name(model, "material")
# Double perturb() call
##test_double_perturb(perturber, "HEU6.density", {"density": 0.001}, "density")
#test_double_perturb(perturber, "HEU6.delta", {"U235": 0.01E-4}, "isotopic")
# Restore() called twice or before perturb()
##test_restore_before_perturb(perturber, "sph10.r", "geometry")
#test_restore_before_perturb(perturber, "HEU6.fraction", "isotopic")

# Geometry ####
# Happy paths
##test_geometry_perturb(perturber, "sph10.r", 0.01)   # positive delta
##test_geometry_perturb(perturber, "sph10.r", -0.01)  # negative delta
##test_geometry_perturb(perturber, "midplane.z0", 0.01)
##test_geometry_perturb(perturber, "midplane.z0", -0.01)
# Sad paths
# Attribute doesn't exist on surface
##test_geometry_typo_attribute(perturber, "sph10.rr", {"rr": 0.01})

# Density ####
# Happy paths
##test_density_perturb(perturber, "HEU6.density", 0.001)   # positive delta
##test_density_perturb(perturber, "HEU6.density", -0.001)  # negative delta
# Sad paths
# Density attribute typo
##test_density_typo_attribute(perturber, "HEU6.foo", {"foo": 0.001})

# Isotopics ####
### single isotope, +/-delta
##test_isotopic_delta(perturber, "HEU6.delta", {"U235": 0.1E-2})
##test_isotopic_delta(perturber, "HEU6.delta", {"U235": -0.1E-2})
### 2 isotopes, +/- delta
##test_isotopic_delta(perturber, "HEU6.delta", {"U235": 0.1E-2, "U238": -0.1E-3})
### all isotopes
##test_isotopic_delta(perturber, "HEU6.delta", {"U235": 0.1E-2, "U238": -0.1E-3, "U234": -0.1E-4})
### fraction mode, single isotope
##test_isotopic_fraction(perturber, "HEU6.fraction", {"U235": 4.4936e-2})
### fraction mode, 2 isotopes
##test_isotopic_fraction(perturber, "HEU6.fraction", {"U235": 4.4936e-2, "U238": 2.7213e-3})
### fraction mode, all isotopes
##test_isotopic_fraction(perturber, "HEU6.fraction", {"U235": 4.4936e-2, "U238": 2.7213e-3, "U234": 4.9357e-4})
### restore() uses correct fraction type (ao/wo)
##test_isotopic_restore_fraction_type(perturber, "HEU6.delta", {"U235": 0.1E-2, "U238": -0.1E-3}, "delta")
##test_isotopic_restore_fraction_type(perturber, "HEU6.delta", {"U235": 4.4936e-2, "U238": 2.7213e-3}, "fraction")
### restore() uses correct order of isotopes 
##test_isotopic_restore_order(perturber, "HEU6.delta", {"U235": 0.1E-2, "U238": -0.1E-3}, "delta")
##test_isotopic_restore_order(perturber, "HEU6.delta", {"U235": 4.4936e-2, "U238": 2.7213e-3}, "fraction")
### Exact float values are restored - no aliasing or rounding errors
##test_isotopic_restore_exact_float(perturber, "HEU6.delta", {"U235": 0.1E-2, "U238": -0.1E-3}, "delta")
##test_isotopic_restore_exact_float(perturber, "HEU6.delta", {"U235": 4.4936e-2, "U238": 2.7213e-3}, "fraction")
### Perturbing 2 isotopics at once causes no issues
##test_isotopic_locality(perturber, "HEU6.delta", {"U235": 0.1e-3}, "HEU5.fraction", {"U235": 4.4e-2})
# Sad paths
#test_isotopic_invalid_mode(perturber, 'HEU6.delat', {"U235": 0.1E-2, "U238": -0.1E-3})
#test_isotopic_unknown_isotope(perturber, 'HEU6.delta', {"U235": 0.1E-2, "U239": -0.1E-3})
#test_isotopic_unknown_isotope(perturber, 'HEU6.fraction', {"U235": 4.4936e-2, "U239": 2.7213e-3})
test_isotopic_mixed_fraction_type(perturber, 'HEU1.delta', {"U235": 0.1E-2, "U238": -0.1E-3})

# --- Run ---
#model.run()

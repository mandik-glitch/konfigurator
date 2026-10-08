# Mutacni kontrola: rozbije modul a overi, ze testy selzou.
# Spusteni: api/venv/bin/python3 scripts/2026-10-02_v3d_testy/_mutace.py   (vypise radek na mutaci; "!!!" = testy chybu nechytily)
import sys, os, unittest, io, re, copy
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(HERE)), 'api'))
import v3d_glb, test_sanitize as T


def run(names):
    suite = unittest.TestSuite()
    for n in names:
        suite.addTest(unittest.defaultTestLoader.loadTestsFromName(n, T))
    r = unittest.TextTestRunner(stream=io.StringIO(), verbosity=0).run(suite)
    return len(r.failures) + len(r.errors)


def mutate(name, attrs, tests):
    """attrs = {jmeno_atributu_modulu: nova_hodnota}; po behu vse vrati."""
    saved = {k: getattr(v3d_glb, k) for k in attrs}
    try:
        for k, v in attrs.items():
            setattr(v3d_glb, k, v)
        cases.append((name, run(tests)))
    finally:
        for k, v in saved.items():
            setattr(v3d_glb, k, v)


class Vse:
    def __contains__(self, _x):
        return True


cases = []
orig_mul = v3d_glb._mat_mul
orig_aabb = v3d_glb._model_aabb
# 1) obracene poradi skladani matic pri slucovani
mutate("poradi matic", {"_mat_mul": lambda a, b: orig_mul(b, a)},
       ["TestNative.test_collapse", "TestSynthetic.test_full", "TestVandr.test_4910_guard_off_collapse"])
# 2) bez kontroly zkosu
mutate("bez kontroly zkosu", {"_decomposable": lambda m, tol=1e-6: True},
       ["TestSynthetic.test_shear_not_collapsed"])
# 3) strazce vypnuty
mutate("strazce vypnuty", {"_GUARD_RE": re.compile(r"(?!)")},
       ["TestVandr.test_raw_catalog_guard", "TestForbidden.test_guard_logo_subtree"])
# 4) final_check nic nedela
mutate("final_check prazdny", {"final_check": lambda g: None},
       ["TestForbidden.test_text_hidden_in_allowed_extension", "TestForbidden.test_final_check_direct"])
# 5) jmena/extras se pri prestavbe kopiruji (drive _strip_names_extras)
mutate("jmena/extras se nemazou", {"_REBUILD_SKIP": frozenset()},
       ["TestNative.test_collapse", "TestSynthetic.test_full"])
# 6) prestavba z whitelistu vypnuta (objekty se kopiruji cele)
mutate("whitelist prestavba vypnuta", {"_rebuild": lambda o, kind, where, rep=None: copy.deepcopy(o)},
       ["TestAttacks.test_attacks", "TestWhitelist.test_attributes_and_extensions_filtered"])
# 7) final_check bez whitelistu (jen zakazany regex jako drive)
mutate("final_check bez whitelistu", {"_schema_errors": lambda *a, **k: None,
                                      "_str_ok": lambda s: True, "_ALL_KEYS": Vse()},
       ["TestForbidden.test_final_check_direct", "TestForbidden.test_text_hidden_in_allowed_extension"])
# 8) atributy primitiv bez filtru (JOINTS/WEIGHTS/_vlastni zustanou)
mutate("atributy bez filtru", {"_ATTR_RE": re.compile(r".*")},
       ["TestAttacks.test_attacks", "TestWhitelist.test_attributes_and_extensions_filtered"])
# 9) textury se neodmitaji
mutate("textury povolene", {"_REJECT_ARRAYS": ("skins",)},
       ["TestSynthetic.test_textures_rejected", "TestAttacks.test_attacks"])
# 10) nepokryte bajty bufferView se nenuluji
mutate("bez nulovani bufferView", {"_and_mask": lambda data, mask: data},
       ["TestAttacks.test_attacks", "TestBinCoverage.test_interleaved_gap_zeroed",
        "TestBinCoverage.test_orphan_accessor_in_shared_view_zeroed"])
# 11) check_bin nic nedela
mutate("check_bin prazdny", {"check_bin": lambda g, b: None},
       ["TestBinCoverage.test_check_bin_direct"])
# 12) spec.box jen varovani (jako drive)
mutate("spec.box jen varovani", {"_BOX_TOL_MM": 1e12},
       ["TestSpecBox.test_model_bigger_than_box_rejected", "TestSpecBox.test_extra_geometry_without_minmax_detected"])
# 13) AABB z rohu min/max misto vrcholu
mutate("AABB z rohu", {"_model_aabb": lambda g, b=None, exact=False: orig_aabb(g, b, False)},
       ["TestSpecBox.test_exact_aabb_from_vertices"])
# 14) whitelist hodnot: vycet typu accessoru povoli i MAT2..MAT4
sch = copy.deepcopy(v3d_glb._SCHEMA)
sch["accessor"]["type"] = ("enum", tuple(v3d_glb._TYPE_COMPS))
mutate("accessor MAT povolen", {"_SCHEMA": sch}, ["TestWhitelist.test_rejected_values"])

# 15-17) motions[].sub (Robert 2026-10-02)
SB = ["TestSub.test_sub_invalid", "TestSub.test_sub_in_final_check", "TestSub.test_sub_in_native_branch"]
mutate("sub: vycet otevreny", {"_SUBS": Vse()}, SB)
mutate("sub: hodnoty chybi v globalnim whitelistu retezcu", {"_STR_OK": frozenset(v3d_glb._STR_OK - set(v3d_glb._SUBS))},
       ["TestSub.test_sub_valid", "TestSub.test_sub_in_native_branch"])
mutate("final_check bez whitelistu (sub)", {"_schema_errors": lambda *a, **k: None, "_str_ok": lambda s: True, "_ALL_KEYS": Vse()},
       ["TestSub.test_sub_in_final_check"])

bad = 0
for name, fails in cases:
    print("%-30s selhanych testu: %d  %s" % (name, fails, "OK (test chybu chyti)" if fails else "!!! TEST CHYBU NECHYTIL"))
    bad += not fails
sys.exit(1 if bad else 0)

#!/usr/bin/env python3
"""Mutacni kontrola Node harnessu importu FBX (2026-09-30_universal_import_harness.js).

Harness, ktery by nechytil rozbity kod, je k nicemu - tohle ho proveruje:
do TEMP kopie universal-import.js zavede postupne 10 umyslnych chyb (kazdou
zvlast) a pro kazdou musi harness selhat (exit != 0). Repo se nemeni.

    python3 scripts/2026-09-30_universal_import_harness_mutace.py

Vystup: radek na mutaci (CHYCENO / !!! NECHYCENO), exit 0 = vsech 10 chyceno
a nezmutovany zdroj projde. Kdyz vzor mutace uz v kodu neni (kod se zmenil),
mutace se PRESKOCI a exit je 1 - vzor je pak potreba upravit tady.

Spust po KAZDE zmene universal-import.js nebo harnessu (+ samotny harness:
node scripts/2026-09-30_universal_import_harness.js -> "18 testu proslo").
"""
import os
import shutil
import subprocess
import sys
import tempfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(REPO, "webapp", "js", "scene", "universal-import.js")
HARNESS = os.path.join(REPO, "scripts", "2026-09-30_universal_import_harness.js")

MUT = {
    "M1 clearAll pred vlozenim": (
        "      await insertCustomShape(shape, { inPlace: true });",
        "      if (typeof clearAll === 'function') clearAll();\n      await insertCustomShape(shape, { inPlace: true });"),
    "M2 bez posunu vedle obsahu": ("        applyAutoPlacementOffset(startIdx, []);\n", ""),
    "M3 bez sceneUndoRestoring": (
        "      sceneUndoRestoring = true; // vlozeni = jeden krok zpet, ne mezistavy\n", ""),
    "M4 bez obnovy currentAssemblyMeta": ("        currentAssemblyMeta = savedMeta;\n", ""),
    "M5 bez serializace fronty": (
        "    const run = sceneOpQueue.then(fn);", "    const run = Promise.resolve().then(fn);"),
    "M6 J/join bere i realne dily": (
        "      if (isTmpEntry(e)) ids.add(parseInt(String(e.part.id).slice(TMP_PREFIX.length), 10));",
        "      ids.add(parseInt(String(e.part.id).slice(TMP_PREFIX.length), 10));"),
    "M7 bez obnovy F5 klice": (
        "          if (savedKey == null) localStorage.removeItem(SCENE_LAST_LOADED_KEY);\n"
        "          else localStorage.setItem(SCENE_LAST_LOADED_KEY, savedKey);\n", ""),
    "M8 bez basePos": (
        "        added.forEach(e => { e.object3d.userData.basePos = e.object3d.position.clone(); }); // rozlozeny pohled\n", ""),
    "M9 isTmpEntry vzdy true": (
        "function isTmpEntry(e) { return !!(e && e.part && String(e.part.id).startsWith(TMP_PREFIX)); }",
        "function isTmpEntry(e) { return !!(e && e.part); }"),
    "M10 bez releaseBrokenProfileJoints": (
        "        added.forEach(e => { if (typeof releaseBrokenProfileJoints === \"function\") releaseBrokenProfileJoints(e); });\n", ""),
}


def main():
    tmp = tempfile.mkdtemp(prefix="uimp_mut_")
    try:
        dst_js = os.path.join(tmp, "webapp", "js", "scene", "universal-import.js")
        dst_h = os.path.join(tmp, "scripts", "harness.js")
        os.makedirs(os.path.dirname(dst_js))
        os.makedirs(os.path.dirname(dst_h))
        shutil.copy(HARNESS, dst_h)
        orig = open(SRC, encoding="utf-8").read()

        def run(text):
            with open(dst_js, "w", encoding="utf-8") as fh:
                fh.write(text)
            p = subprocess.run(["node", dst_h], capture_output=True, text=True)
            fails = [ln for ln in (p.stdout + p.stderr).splitlines() if ln.startswith("FAIL")]
            return p.returncode, fails

        rc, fails = run(orig)
        print("ZDROJ BEZ MUTACE: exit %s (ocekavano 0) %s" % (rc, fails[:2]))
        bad = 0 if rc == 0 else 1
        for name, (a, b) in MUT.items():
            n = orig.count(a)
            if n != 1:
                print("PRESKOCENO (vzor nalezen %dx): %s" % (n, name))
                bad += 1
                continue
            rc, fails = run(orig.replace(a, b))
            if rc == 0:
                bad += 1
            print("%-38s %s  exit=%s  %s" % (name, "CHYCENO" if rc != 0 else "!!! NECHYCENO", rc,
                                            fails[0][:80] if fails else ""))
        print("VSECH %d MUTACI CHYCENO" % len(MUT) if not bad else "PROBLEM: %d" % bad)
        return 1 if bad else 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())

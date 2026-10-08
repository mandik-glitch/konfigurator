"""Odolny ukazatel na soubor na Sdilenem disku (bot9, 2026-09-11, pres bot8).

PROBLEM, ktery resi: nastaveni typu `render_template_file_id` drzelo natvrdo
`id` radku v `shared_drive_files`. Robert pri kazde uprave sablony soubor
SMAZE a nahraje novy, takze dostane nove `id` a ukazatel visi do prazdna.
Renderovalo se pak s vestavenymi vychozimi hodnotami - a hlavne TISE, nikde
se to nenahlasilo. Behem jednoho vecera 2026-09-10 se to stalo DVAKRAT
(`1784` -> `2058` -> `2064`) a pokazde to musel nekdo najit a prepnout rucne.

RESENI: k nastaveni se uklada i NAZEV souboru. Kdyz je `id` mrtve, dohleda se
nejnovejsi radek s tymz nazvem - a ukazatel se rovnou uzdravi, aby priste
sedel. Kdyz se nenajde ani podle nazvu, vraci se stav `NENALEZENO`, na ktery
MUSI volajici zareagovat hlasite; tiche spadnuti na vychozi hodnoty je horsi
nez chyba.

⚠ NIKDY NE PODLE ADRESARE. Odvozeny strom `private-files/shared-drive-named/`
je prokazatelne nespolehlivy: 2026-09-10 v nem lezel rozbity symlink
`X30-1.blend` (cil zmizel) i `canary_wharf_4k.exr` na neexistujici blob, a
naopak `docklands_01_4k.hdr` / `crossfit_gym_2k.exr` jsou tam jen jako rucni
kopie, ktere v tabulce nejsou vubec. Podle nazvu v tom stromu to vypada jako
Robertuv soubor, a pritom neni. ZDROJ PRAVDY JE TABULKA.

Modul zamerne NEIMPORTUJE Flask ani `app` - aby se dal pouzit i ze
samostatnych skriptu (`scripts/2026-09-09_turntable_render.py`), ktere bezi
mimo webovou aplikaci.
"""
import os

# Stavy, ktere vraci najdi_soubor(). Volajici je MUSI rozlisovat - hlavne
# NENASTAVENO (legitimni, nic nevybrano) vs. NENALEZENO (vybrano, ale
# nedohledatelne = chyba, ktera se ma ozvat).
NENASTAVENO = "nenastaveno"
OK = "ok"
UZDRAVENO = "uzdraveno"
NENALEZENO = "nenalezeno"


def _nastaveni(cur, klic):
    cur.execute("SELECT setting_value FROM app_settings WHERE setting_key=%s", (klic,))
    row = cur.fetchone()
    if not row:
        return None
    hodnota = row["setting_value"] if isinstance(row, dict) else row[0]
    return hodnota or None


def _zapis_nastaveni(cur, klic, hodnota):
    cur.execute(
        "INSERT INTO app_settings (setting_key, setting_value) VALUES (%s,%s) "
        "ON DUPLICATE KEY UPDATE setting_value=VALUES(setting_value)",
        (klic, hodnota),
    )


def _radek(cur, sql, args):
    cur.execute(sql, args)
    return cur.fetchone()


def _cesta_k_souboru(drive_dir, stored_filename):
    """Absolutni cesta uvnitr uloziste, nebo None.

    Pojistka proti vyskoceni z uloziste je stejny vzor jako u .blend renderu
    v blender_render.py - stored_filename jde z DB, ale radeji se overi."""
    if not stored_filename:
        return None
    cesta = os.path.realpath(os.path.join(drive_dir, stored_filename))
    if not cesta.startswith(os.path.realpath(drive_dir)):
        return None
    return cesta if os.path.exists(cesta) else None


def uloz_ukazatel(cur, klic_id, klic_nazev, file_id, filename):
    """Ulozi ukazatel VCETNE nazvu. Prazdne file_id = "nic nevybrano"."""
    if file_id in (None, "", 0):
        _zapis_nastaveni(cur, klic_id, "")
        _zapis_nastaveni(cur, klic_nazev, "")
        return
    _zapis_nastaveni(cur, klic_id, str(file_id))
    _zapis_nastaveni(cur, klic_nazev, filename or "")


def najdi_soubor(cur, klic_id, klic_nazev, drive_dir, uzdravit=True):
    """Dohleda vybrany soubor. Vraci (stav, cesta, popis).

    `popis` je veta pro cloveka - patri do stavu ulohy/logu, at je videt,
    jestli se ukazatel uzdravil, nebo proc se nenaslo nic.
    """
    id_souboru = _nastaveni(cur, klic_id)
    nazev = _nastaveni(cur, klic_nazev)

    if not id_souboru:
        return NENASTAVENO, None, "nic nevybrano"

    # 1) Primo podle id - bezny pripad
    try:
        radek = _radek(cur, "SELECT id, filename, stored_filename FROM shared_drive_files WHERE id=%s",
                       (int(id_souboru),))
    except (TypeError, ValueError):
        radek = None
    if radek:
        cesta = _cesta_k_souboru(drive_dir, radek["stored_filename"])
        if cesta:
            return OK, cesta, radek["filename"]
        # Radek v tabulce je, ale blob na disku chybi - zkusi se jeste nazev
        nazev = nazev or radek["filename"]

    # 2) Podle NAZVU - nejnovejsi radek, jehoz soubor na disku opravdu je.
    #    Prochazi se od nejnovejsiho, protoze Robert nahrava opravenou verzi
    #    pod tymz nazvem a chce tu posledni.
    if nazev:
        cur.execute(
            "SELECT id, filename, stored_filename FROM shared_drive_files "
            "WHERE filename=%s ORDER BY id DESC", (nazev,))
        for kandidat in cur.fetchall():
            cesta = _cesta_k_souboru(drive_dir, kandidat["stored_filename"])
            if not cesta:
                continue
            if uzdravit and str(kandidat["id"]) != str(id_souboru):
                _zapis_nastaveni(cur, klic_id, str(kandidat["id"]))
                _zapis_nastaveni(cur, klic_nazev, kandidat["filename"])
                return (UZDRAVENO, cesta,
                        "%s - ukazatel byl mrtvy (id=%s), dohledano podle nazvu "
                        "a opraveno na id=%s" % (kandidat["filename"], id_souboru, kandidat["id"]))
            return OK, cesta, kandidat["filename"]

    return (NENALEZENO, None,
            "vybrany soubor id=%s%s uz na Sdilenem disku NENI a nejde dohledat "
            "ani podle nazvu" % (id_souboru, " (%s)" % nazev if nazev else ""))

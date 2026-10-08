"""Zabrani prace pro watchdog automat - viz sql/2026-09-11j_production_work_claims.sql
pro schema a princip. NENI TO DEPLOY_LOCK (ten resi git commit do
webapp/*|api/*.py, tenhle modul resi "kdo prave pocita cenu sestavy 334").

Pouziti (automat):
    from production_work_claims import claim, renew, release, fail_count_of, blokovano

    if blokovano(cur, "assembly", 334, "bom_backfill", 3):
        continue  # po 3 selhanich pocka (30 min, 1 h, 2 h ... max 24 h) a zkusi znovu - NE navzdy
    # (puvodni tvar `fail_count_of(...) >= 3` vzdava navzdy - jen pro zpetnou kompatibilitu)
    if not claim(cur, "assembly", 334, "bom_backfill", "automat:bom_backfill"):
        continue  # drzi to nekdo jiny prave ted
    try:
        ... udelej krok ...
        release(cur, "assembly", 334, "bom_backfill", "automat:bom_backfill", "hotovo")
    except Exception as e:
        release(cur, "assembly", 334, "bom_backfill", "automat:bom_backfill", "chyba", str(e)[:290])

`cur` musi byt kurzor s otevrenou transakci, na ktere se hned potom zavola
commit() - `claim()`/`release()`/`renew()` samy o sobe COMMIT nedelaji.
"""
import datetime

_RECLAIMOVATELNY = (
    "(result IS NOT NULL OR released_at IS NOT NULL OR expires_at < NOW())"
)


def claim(cur, target_type, target_id, step_key, held_by, lease_seconds=1200):
    """Pokusi se atomicky zabrat (target_type, target_id, step_key).

    Vraci True, kdyz `held_by` prave vyhral zabrani (vc. pripadu, kdy uz ho
    driv drzel a jen prodlouzil - idempotentni). Vraci False, kdyz to prave
    ted aktivne drzi nekdo jiny.

    Nekontroluje `fail_count` - to je na volajicim (viz `fail_count_of`) PRED
    volanim claim(), aby se rozliseni "nemuzu zabrat" (soubeh) od "nemam
    zabirat" (opakovane selhava) nemíchalo v jedne navratove hodnote.
    """
    cur.execute(
        f"""
        INSERT INTO production_work_claims
            (target_type, target_id, step_key, held_by, held_at, expires_at, fail_count)
        VALUES (%s, %s, %s, %s, NOW(), NOW() + INTERVAL %s SECOND, 0)
        ON DUPLICATE KEY UPDATE
            held_by     = IF({_RECLAIMOVATELNY}, VALUES(held_by), held_by),
            held_at     = IF({_RECLAIMOVATELNY}, VALUES(held_at), held_at),
            expires_at  = IF({_RECLAIMOVATELNY}, VALUES(expires_at), expires_at),
            released_at = IF({_RECLAIMOVATELNY}, NULL, released_at),
            result      = IF({_RECLAIMOVATELNY}, NULL, result),
            result_note = IF({_RECLAIMOVATELNY}, NULL, result_note)
        """,
        (target_type, target_id, step_key, held_by, lease_seconds),
    )
    cur.execute(
        "SELECT held_by FROM production_work_claims "
        "WHERE target_type=%s AND target_id=%s AND step_key=%s",
        (target_type, target_id, step_key),
    )
    row = cur.fetchone()
    return bool(row) and row["held_by"] == held_by


def renew(cur, target_type, target_id, step_key, held_by, lease_seconds=1200):
    """Prodlouzi lhutu prave probihajici prace (heartbeat) - volatelne
    kdykoli behem zpracovani, ne jen na zacatku. Vraci True, kdyz prodlouzeni
    doopravdy zabralo (porad drzime my a jeste nebylo uvolneno).

    Nalezeno bot4 (overeni pred zapnutim, 2026-09-11): PyMySQL bez
    CLIENT_FOUND_ROWS pocita ZMENENE radky, ne NALEZENE - kdyz vyjde
    `expires_at` na stejnou hodnotu (renew() zavolan dvakrat rychle po
    sobe), zadny bajt se nezmeni a `cur.rowcount` je 0, i kdyz drzeni je
    porad nase. Uspech se proto overuje CERSTVYM SELECTem stavu po UPDATE,
    ne poctem zmenenych radku."""
    cur.execute(
        "UPDATE production_work_claims "
        "SET expires_at = NOW() + INTERVAL %s SECOND "
        "WHERE target_type=%s AND target_id=%s AND step_key=%s "
        "AND held_by=%s AND released_at IS NULL AND result IS NULL",
        (lease_seconds, target_type, target_id, step_key, held_by),
    )
    cur.execute(
        "SELECT 1 FROM production_work_claims "
        "WHERE target_type=%s AND target_id=%s AND step_key=%s "
        "AND held_by=%s AND released_at IS NULL AND result IS NULL",
        (target_type, target_id, step_key, held_by),
    )
    return cur.fetchone() is not None


def release(cur, target_type, target_id, step_key, held_by, result, result_note=None):
    """Uvolni zabrani a zapise vysledek. Jen DRZITEL smi uvolnit (AND held_by=%s).

    `result`: 'hotovo' (fail_count se resetuje na 0), 'chyba' (fail_count
    +1), 'vzdano' (fail_count beze zmeny - napr. kandidat prestal platit
    mezi zabranim a zpracovanim, neni to selhani kroku)."""
    assert result in ("hotovo", "chyba", "vzdano"), "neznamy result: %r" % result
    if result_note is not None and len(result_note) > 300:
        result_note = result_note[:300]
    prirustek = "fail_count + 1" if result == "chyba" else ("0" if result == "hotovo" else "fail_count")
    cur.execute(
        f"""
        UPDATE production_work_claims
        SET released_at=NOW(), result=%s, result_note=%s, fail_count={prirustek}
        WHERE target_type=%s AND target_id=%s AND step_key=%s
          AND held_by=%s AND released_at IS NULL
        """,
        (result, result_note, target_type, target_id, step_key, held_by),
    )
    return cur.rowcount > 0


def fail_count_of(cur, target_type, target_id, step_key):
    """Kolikrat po sobe tenhle cil na tomhle kroku selhal. 0, kdyz zadny
    zaznam neexistuje (jeste nikdy se nezkousel) nebo kdyz posledni pokus
    skoncil 'hotovo' (viz release() - resetuje na 0)."""
    cur.execute(
        "SELECT fail_count FROM production_work_claims "
        "WHERE target_type=%s AND target_id=%s AND step_key=%s",
        (target_type, target_id, step_key),
    )
    row = cur.fetchone()
    return row["fail_count"] if row else 0


ODSTUP_ZAKLAD_S = 1800            # po max_fail selhanich pocka 30 min, pak 1 h, 2 h, 4 h ...
ODSTUP_MAX_S = 24 * 3600          # ... nejvyse den (mezera "vzdat navzdy", bot4 2026-09-30)


def blokovano(cur, target_type, target_id, step_key, max_fail=3):
    """Ma se cil TED preskocit, protoze po sobe selhal aspon `max_fail`-krat? Na rozdil od `fail_count_of(...) >= N`
    NEVZDAVA NAVZDY: po dosazeni max_fail se pockat odstup od POSLEDNIHO pokusu (30 min * 2^(fail_count-max_fail),
    strop 24 h) a pak se zkusi znovu; selze-li i dal, fail_count roste a odstup se prodluzuje.

    Proc (STAV.md "MAX_FAIL mezera", nalez 2026-09-29/30): pevne "vzdat po 3x" tiše a NAVZDY vyradi polozku, i kdyz
    pricina byla docasna (pauza renderu RENDER_POZASTAVEN.json, vypadek DB, neplatny panel, ktery uz Robert opravil) -
    automat pak nic nerenderuje a nikdo to nevidi. Tady se po odstupu zkusi znovu sam.
    Radek bez released_at (prave zabrany/rozpracovany) se tady NEBLOKUJE - rozhoduje `claim()` (lease)."""
    cur.execute(
        "SELECT fail_count, TIMESTAMPDIFF(SECOND, released_at, NOW()) AS stari_s FROM production_work_claims "
        "WHERE target_type=%s AND target_id=%s AND step_key=%s",
        (target_type, target_id, step_key),
    )
    row = cur.fetchone()
    if not row or row["fail_count"] < max_fail or row["stari_s"] is None:
        return False
    odstup = min(ODSTUP_MAX_S, ODSTUP_ZAKLAD_S * (2 ** (row["fail_count"] - max_fail)))
    return row["stari_s"] < odstup


def abandoned(cur, limit=200):
    """Radky, kde bot/automat spadl uprostred prace (vyprsely, nedokoncene,
    zadny vysledek) - pro badge v /api/admin/vyroba-sestav/prehled. Nemeni
    nic, jen cte."""
    cur.execute(
        "SELECT target_type, target_id, step_key, held_by, held_at, expires_at "
        "FROM production_work_claims "
        "WHERE expires_at < NOW() AND released_at IS NULL AND result IS NULL "
        "ORDER BY expires_at DESC LIMIT %s",
        (limit,),
    )
    return cur.fetchall()

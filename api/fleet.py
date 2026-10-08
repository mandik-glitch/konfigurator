"""
Kniha jizd (Robert 2026-08-05: "mala kniha jizd, mame 3 firemni auta,
vytvor DB ja to doplnim VIN SPZ Nazev, sledovat budeme pozici GPS
mobilniho telefonu pres nasi fotoapku, uzivatel z administrace (co
ma roli) ma apku v mobilu, tam vznikne nove tlacitko Jizda a nasledne
si vybere auto kterym jede, tabulka bude sledovat kdo jede cim jede a
hlavne pocitat km, snimani pozice GPS automaticky kazde 2 kilometry").

Dve casti:
- Admin sprava vozidel + prehled jizd (@require_permission("kniha_jizd", ...),
  stejny vzor jako ostatni admin sekce - viz api/app.py PERMISSION_SECTIONS).
- Mobilni endpointy pro fotoapku (webapp/capture.html) - start/pridani
  GPS bodu/ukonceni jizdy. Pristup rizen pevnym seznamem roli FLEET_ROLES,
  stejny vzor jako INBOX_ROLES v gallery_items.py (kazdy prihlaseny
  "personal" ucet, ne jen ti, komu admin v Role a opravneni neco
  zaskrtl - mobilni fotoapka takhle funguje uz pro foceni).

Vzdalenost (distance_km) pocital puvodne (2026-08-05/06) mobilni
klient sam - watchPosition v capture.html bezel jen dokud byla
appka/PWA otevrena na popredi, takze se sledovani zastavilo pri
zavreni appky nebo uspani na pozadi (browser limitace, ne bug). Robert
2026-08-07 ("Vzít si prostě GPS z jiné apky na mobilu"): misto
vlastniho reseni se pouziva existujici nativni appka (napr. Traccar
Client), ktera na pozadi bezet umi a pinguje /api/fleet/gps-ping
(OsmAnd protokol, autentizace pres gps_device_token na app_users, ne
session - appka nema cookie). Vzdalenost ted pocita server (haversine
mezi po sobe jdoucimi ulozenymi body, _haversine_km nize) - stale bez
serverove validace proti podvrzeni (jen ignoruje jednotlive skoky
vetsi nez MAX_PING_JUMP_KM jako pravdepodobnou chybu GPS fixu), stejny
duveryhodnostni model jako zbytek fotoapky. Jizdu porad zahajuje/
ukoncuje ridic rucne tlacitkem v capture.html - gps-ping jen doplnuje
body k prave aktivni jizde.

Aktivace: `import fleet` na konec app.py (jako ostatni moduly).
"""
import math
import os
import secrets

from flask import request, jsonify

from app import (
    app, get_conn, current_user, require_permission,
    log_audit, get_setting,
)
from quotes import safe_stored_filename
from drive import DRIVE_FILES_DIR

FLEET_ROLES = ("admin", "manager", "skladnik", "ucetni", "monter", "sklad")
STOP_TYPES = ("fuel", "customer")
# Robert 2026-08-05: "pokud se stane to že nesedí počet ujetých km se
# zadaným stavem km na konci jízdy pošli email o tomto stavu".
FLEET_CONTINUITY_ALERT_EMAIL = "mandik@logiman.cz"
# Robert 2026-08-06: "z knihy jízd se musí posílat automaticky doklady
# o tankování na email, určí se v Knize jízd, email tam zadá admin" -
# na rozdil od FLEET_CONTINUITY_ALERT_EMAIL vyse (pevny, ne pro tohle)
# je tahle adresa editovatelna v adminu (viz fleet_settings_get/set
# nize), ulozena v app_settings pod timhle klicem.
FLEET_FUEL_RECEIPT_EMAIL_SETTING_KEY = "fleet_fuel_receipt_email"
# Robert 2026-08-06 ("dej na knihu jízd nastavení adresáře pro
# ukládání dokladů o tankování"): cesta na Sdilenem disku (slozky
# oddelene "/", zakladaji se/hledaji stejnym zpusobem jako predtim
# pevne "Kniha jízd"/"Tankování") - pod poslednim segmentem se porad
# automaticky zaklada podslozka s nazvem vozidla, at zustane doklad
# roztrideny podle auta i pri vlastni ceste.
FLEET_FUEL_RECEIPT_FOLDER_PATH_SETTING_KEY = "fleet_fuel_receipt_folder_path"
FLEET_FUEL_RECEIPT_FOLDER_PATH_DEFAULT = "Kniha jízd/Tankování"
# Robert 2026-08-07 ("Vzít si prostě GPS z jiné apky na mobilu"): vlastni
# sledovani polohy v capture.html (navigator.geolocation.watchPosition)
# bezi jen dokud je stranka/PWA otevrena na popredi - zavrena apka =
# zadna GPS (viz AGENTS_LOG.md, "Kniha jizd" zaznamy). Reseni: rezidr
# GPS trackovani se prenecha existujici nativni appce (napr. Traccar
# Client - zdarma, Android i iOS, umi bezet na pozadi a posilat polohu
# OsmAnd protokolem), ktera pinguje /api/fleet/gps-ping. Ten endpoint
# NEMA session (headless appka, ne prohlizec s cookie) - autentizace
# je pres gps_device_token misto prihlaseni, stejny princip jako
# magic_token_hash pro jine "bez hesla" pristupy v projektu.
MAX_PING_JUMP_KM = 5.0  # ignoruj jednotlive GPS skoky vetsi nez tohle (chyba fixu, ne skutecny pohyb)


def _haversine_km(lat1, lng1, lat2, lng2):
    """Vzdalenost dvou GPS bodu v km - stejny vzorec jako haversineKm()
    v capture.html (drive pocitano na klientovi, ted server-side, kdyz
    body chodi z externi GPS appky bez vlastniho vypoctu vzdalenosti)."""
    r = 6371.0
    to_rad = math.pi / 180
    d_lat = (lat2 - lat1) * to_rad
    d_lng = (lng2 - lng1) * to_rad
    a = math.sin(d_lat / 2) ** 2 + math.cos(lat1 * to_rad) * math.cos(lat2 * to_rad) * math.sin(d_lng / 2) ** 2
    return r * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _require_fleet_mobile_access():
    """Vraci (user, error_response|None) - pristup k mobilnim jizda
    endpointum, stejny vzor jako _require_owner_permission v
    gallery_items.py pro owner_type='inbox'."""
    user = current_user()
    if not user or not user["active"]:
        return None, (jsonify({"error": "Nepřihlášeno.", "code": "unauthorized"}), 401)
    if user["role"] not in FLEET_ROLES:
        return None, (jsonify({"error": "Nemáte oprávnění k této akci.", "code": "forbidden"}), 403)
    return user, None


def _serialize_vehicle(r):
    return {
        "id": r["id"], "name": r["name"], "spz": r["spz"], "vin": r["vin"],
        "active": bool(r["active"]),
        "created_at": r["created_at"].isoformat() if r["created_at"] else None,
    }


def _serialize_trip(r):
    return {
        "id": r["id"], "vehicle_id": r["vehicle_id"], "trip_number": r["trip_number"], "user_id": r["user_id"],
        "vehicle_name": r.get("vehicle_name"), "vehicle_spz": r.get("vehicle_spz"),
        "user_name": r.get("user_name"),
        "status": r["status"],
        "started_at": r["started_at"].isoformat() if r["started_at"] else None,
        "ended_at": r["ended_at"].isoformat() if r["ended_at"] else None,
        "start_lat": float(r["start_lat"]) if r["start_lat"] is not None else None,
        "start_lng": float(r["start_lng"]) if r["start_lng"] is not None else None,
        "end_lat": float(r["end_lat"]) if r["end_lat"] is not None else None,
        "end_lng": float(r["end_lng"]) if r["end_lng"] is not None else None,
        "distance_km": float(r["distance_km"]),
        "odometer_km": r.get("odometer_km"),
    }


def _serialize_stop(r):
    return {
        "id": r["id"], "trip_id": r["trip_id"], "stop_type": r["stop_type"],
        "recorded_at": r["recorded_at"].isoformat() if r["recorded_at"] else None,
        "lat": float(r["lat"]) if r["lat"] is not None else None,
        "lng": float(r["lng"]) if r["lng"] is not None else None,
        "drive_file_id": r["drive_file_id"],
        "drive_filename": r.get("drive_filename"),
        "company_name": r["company_name"],
        "city": r["city"],
    }


def _ensure_drive_folder(cur, parent_id, name, user_id):
    """Najde/zalozi podslozku `name` pod `parent_id` (None = koren) ve
    Sdilenem disku - stejny SELECT-pak-INSERT vzor jako
    drive_admin_folder_create() v drive.py, jen bez HTTP vrstvy (volano
    programove pri ukladani dokladu o tankovani, ne uzivatelem)."""
    if parent_id is None:
        cur.execute("SELECT id FROM shared_drive_folders WHERE parent_folder_id IS NULL AND name=%s", (name,))
    else:
        cur.execute("SELECT id FROM shared_drive_folders WHERE parent_folder_id=%s AND name=%s", (parent_id, name))
    row = cur.fetchone()
    if row:
        return row["id"]
    cur.execute(
        "INSERT INTO shared_drive_folders (parent_folder_id, name, created_by) VALUES (%s,%s,%s)",
        (parent_id, name, user_id),
    )
    return cur.lastrowid


def _ensure_drive_folder_path(cur, path_str, user_id):
    """Projde cestu oddelenou "/" (napr. "Kniha jízd/Tankování") a
    zalozi/najde kazdou uroven pres _ensure_drive_folder - vraci id
    posledni (nejhlubsi) slozky. Prazdne segmenty (dvojite lomitko,
    lomitko na zacatku/konci) se preskakuji. Prazdny/whitespace-only
    retezec padne zpet na FLEET_FUEL_RECEIPT_FOLDER_PATH_DEFAULT, aby
    doklad mel vzdy kam padnout, i kdyz admin nastaveni cesty vynuluje."""
    segments = [s.strip() for s in (path_str or "").split("/") if s.strip()]
    if not segments:
        segments = [s.strip() for s in FLEET_FUEL_RECEIPT_FOLDER_PATH_DEFAULT.split("/") if s.strip()]
    folder_id = None
    for segment in segments:
        folder_id = _ensure_drive_folder(cur, folder_id, segment, user_id)
    return folder_id


def _get_active_trip_for_user(cur, trip_id, user_id):
    cur.execute(
        "SELECT t.*, v.name AS vehicle_name, v.spz AS vehicle_spz FROM fleet_trips t "
        "JOIN fleet_vehicles v ON v.id = t.vehicle_id "
        "WHERE t.id=%s AND t.user_id=%s AND t.status='active'",
        (trip_id, user_id),
    )
    return cur.fetchone()


# ==================== Admin: vozidla ====================

@app.get("/api/admin/fleet/vehicles")
@require_permission("kniha_jizd", "zobrazit")
def fleet_vehicles_list():
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM fleet_vehicles ORDER BY active DESC, name")
            rows = cur.fetchall()
    finally:
        conn.close()
    return jsonify({"vehicles": [_serialize_vehicle(r) for r in rows]})


@app.post("/api/admin/fleet/vehicles")
@require_permission("kniha_jizd", "vytvorit")
def fleet_vehicles_create():
    body = request.get_json(silent=True) or {}
    name = (body.get("name") or "").strip()
    spz = (body.get("spz") or "").strip()
    vin = (body.get("vin") or "").strip() or None
    if not name or not spz:
        return jsonify({"error": "Název a SPZ jsou povinné."}), 400
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO fleet_vehicles (name, spz, vin) VALUES (%s,%s,%s)",
                (name, spz, vin),
            )
            vehicle_id = cur.lastrowid
        conn.commit()
    finally:
        conn.close()
    log_audit(current_user()["id"], "create", "fleet_vehicle", vehicle_id, f"{name} ({spz})")
    return jsonify({"id": vehicle_id}), 201


@app.put("/api/admin/fleet/vehicles/<int:vehicle_id>")
@require_permission("kniha_jizd", "upravit")
def fleet_vehicles_update(vehicle_id):
    body = request.get_json(silent=True) or {}
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM fleet_vehicles WHERE id=%s", (vehicle_id,))
            if not cur.fetchone():
                return jsonify({"error": "Vozidlo nenalezeno."}), 404
            fields, params = [], []
            if "name" in body:
                name = (body.get("name") or "").strip()
                if not name:
                    return jsonify({"error": "Název nesmí být prázdný."}), 400
                fields.append("name=%s"); params.append(name)
            if "spz" in body:
                spz = (body.get("spz") or "").strip()
                if not spz:
                    return jsonify({"error": "SPZ nesmí být prázdná."}), 400
                fields.append("spz=%s"); params.append(spz)
            if "vin" in body:
                fields.append("vin=%s"); params.append((body.get("vin") or "").strip() or None)
            if "active" in body:
                fields.append("active=%s"); params.append(1 if body.get("active") else 0)
            if fields:
                params.append(vehicle_id)
                cur.execute(f"UPDATE fleet_vehicles SET {', '.join(fields)} WHERE id=%s", params)
        conn.commit()
    finally:
        conn.close()
    log_audit(current_user()["id"], "update", "fleet_vehicle", vehicle_id, None)
    return jsonify({"ok": True})


@app.delete("/api/admin/fleet/vehicles/<int:vehicle_id>")
@require_permission("kniha_jizd", "smazat")
def fleet_vehicles_delete(vehicle_id):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM fleet_trips WHERE vehicle_id=%s LIMIT 1", (vehicle_id,))
            if cur.fetchone():
                # Vozidlo uz ma jizdy v knize - kvuli historii se nemaze,
                # jen deaktivuje (zmizi z vyberu v mobilni fotoapce).
                cur.execute("UPDATE fleet_vehicles SET active=0 WHERE id=%s", (vehicle_id,))
                conn.commit()
                log_audit(current_user()["id"], "deactivate", "fleet_vehicle", vehicle_id, "ma jizdy v historii, jen deaktivovano")
                return jsonify({"ok": True, "deactivated": True})
            cur.execute("DELETE FROM fleet_vehicles WHERE id=%s", (vehicle_id,))
        conn.commit()
    finally:
        conn.close()
    log_audit(current_user()["id"], "delete", "fleet_vehicle", vehicle_id, None)
    return jsonify({"ok": True, "deactivated": False})


# ==================== Admin: prehled jizd ====================

@app.get("/api/admin/fleet/trips")
@require_permission("kniha_jizd", "zobrazit")
def fleet_trips_list():
    # Robert 2026-08-05 ("bude potreba to tedy filtrovat vsechno podle
    # auta"): server-side filtr, ne jen klientske skryvani radku - az
    # pribudou dalsi vozidla/mesice jizd, at se filtruje uz v SQL.
    vehicle_id = request.args.get("vehicle_id", type=int)
    where_sql, params = "", []
    if vehicle_id:
        where_sql = " WHERE t.vehicle_id=%s"
        params.append(vehicle_id)
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT t.*, v.name AS vehicle_name, v.spz AS vehicle_spz, u.name AS user_name "
                "FROM fleet_trips t "
                "JOIN fleet_vehicles v ON v.id = t.vehicle_id "
                # bot4, 2026-08-09: LEFT JOIN (ne JOIN) - user_id ted muze byt
                # NULL (ON DELETE SET NULL, viz sql/2026-08-09_fleet_trips_
                # user_delete_set_null.sql), INNER JOIN by takove jizdy tise
                # zmizely z vypisu misto zobrazeni s prazdnym user_name.
                "LEFT JOIN app_users u ON u.id = t.user_id" + where_sql +
                " ORDER BY t.started_at DESC LIMIT 500",
                params,
            )
            rows = cur.fetchall()
    finally:
        conn.close()
    return jsonify({"trips": [_serialize_trip(r) for r in rows]})


@app.get("/api/admin/fleet/trips/<int:trip_id>/points")
@require_permission("kniha_jizd", "zobrazit")
def fleet_trip_points_list(trip_id):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, lat, lng, distance_km, recorded_at FROM fleet_trip_points "
                "WHERE trip_id=%s ORDER BY recorded_at", (trip_id,)
            )
            rows = cur.fetchall()
    finally:
        conn.close()
    return jsonify({"points": [
        {
            "id": r["id"], "lat": float(r["lat"]), "lng": float(r["lng"]),
            "distance_km": float(r["distance_km"]),
            "recorded_at": r["recorded_at"].isoformat() if r["recorded_at"] else None,
        } for r in rows
    ]})


@app.get("/api/admin/fleet/trips/<int:trip_id>/stops")
@require_permission("kniha_jizd", "zobrazit")
def fleet_trip_stops_list(trip_id):
    """Zastavky jizdy (tankovani + cilove destinace) v jedne casove
    ose - viz sql/2026-08-05_fleet_trip_stops.sql. Doklad o tankovani
    se stahuje pres stavajici GET /api/admin/drive/files/<id>/download
    (vyzaduje navic pravo "sdileny_disk"/"zobrazit" - Sdileny disk ma
    vlastni permission sekci, kniha_jizd ji nenahrazuje)."""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT s.*, df.filename AS drive_filename "
                "FROM fleet_trip_stops s "
                "LEFT JOIN shared_drive_files df ON df.id = s.drive_file_id "
                "WHERE s.trip_id=%s ORDER BY s.recorded_at", (trip_id,)
            )
            rows = cur.fetchall()
    finally:
        conn.close()
    return jsonify({"stops": [_serialize_stop(r) for r in rows]})


# ==================== Admin: nastaveni (email pro doklady o tankovani) ====================

@app.get("/api/admin/fleet/settings")
@require_permission("kniha_jizd", "zobrazit")
def fleet_settings_get():
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            email = get_setting(cur, FLEET_FUEL_RECEIPT_EMAIL_SETTING_KEY, "")
            folder_path = get_setting(cur, FLEET_FUEL_RECEIPT_FOLDER_PATH_SETTING_KEY, "") or FLEET_FUEL_RECEIPT_FOLDER_PATH_DEFAULT
    finally:
        conn.close()
    return jsonify({"fuel_receipt_email": email or "", "fuel_receipt_folder_path": folder_path})


@app.put("/api/admin/fleet/settings")
@require_permission("kniha_jizd", "upravit")
def fleet_settings_set():
    body = request.get_json(silent=True) or {}
    if "fuel_receipt_email" not in body and "fuel_receipt_folder_path" not in body:
        return jsonify({"error": "Chybí fuel_receipt_email nebo fuel_receipt_folder_path."}), 400
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            if "fuel_receipt_email" in body:
                email = (body.get("fuel_receipt_email") or "").strip()
                if email and ("@" not in email or not email.isascii()):
                    return jsonify({"error": "Zadejte platnou e-mailovou adresu (bez diakritiky)."}), 400
                cur.execute(
                    "INSERT INTO app_settings (setting_key, setting_value) VALUES (%s,%s) "
                    "ON DUPLICATE KEY UPDATE setting_value=%s",
                    (FLEET_FUEL_RECEIPT_EMAIL_SETTING_KEY, email, email),
                )
            if "fuel_receipt_folder_path" in body:
                folder_path = (body.get("fuel_receipt_folder_path") or "").strip().strip("/")
                if not folder_path:
                    folder_path = FLEET_FUEL_RECEIPT_FOLDER_PATH_DEFAULT
                cur.execute(
                    "INSERT INTO app_settings (setting_key, setting_value) VALUES (%s,%s) "
                    "ON DUPLICATE KEY UPDATE setting_value=%s",
                    (FLEET_FUEL_RECEIPT_FOLDER_PATH_SETTING_KEY, folder_path, folder_path),
                )
        conn.commit()
    finally:
        conn.close()
    log_audit(current_user()["id"], "update", "fleet_settings", None,
              f"fuel_receipt_email={body.get('fuel_receipt_email', '(nezmeneno)')}, "
              f"fuel_receipt_folder_path={body.get('fuel_receipt_folder_path', '(nezmeneno)')}")
    return jsonify({"ok": True})


# ==================== Mobilni fotoapka: aktivni vozidla + jizda ====================

@app.get("/api/fleet/vehicles/active")
def fleet_mobile_vehicles_active():
    user, err = _require_fleet_mobile_access()
    if err:
        return err
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, name, spz FROM fleet_vehicles WHERE active=1 ORDER BY name")
            rows = cur.fetchall()
    finally:
        conn.close()
    return jsonify({"vehicles": rows})


@app.get("/api/fleet/gps-token")
def fleet_mobile_gps_token_get():
    """Vrati (a pri prvnim volani vytvori) gps_device_token prihlaseneho
    ridice - zobrazuje se v capture.html jako navod pro nastaveni
    externi GPS appky (Traccar Client)."""
    user, err = _require_fleet_mobile_access()
    if err:
        return err
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT gps_device_token FROM app_users WHERE id=%s", (user["id"],))
            token = cur.fetchone()["gps_device_token"]
            if not token:
                token = secrets.token_urlsafe(24)
                cur.execute("UPDATE app_users SET gps_device_token=%s WHERE id=%s", (token, user["id"]))
                conn.commit()
    finally:
        conn.close()
    return jsonify({"token": token})


@app.post("/api/fleet/gps-token/regenerate")
def fleet_mobile_gps_token_regenerate():
    """Novy token (napr. po ztrate/vymene telefonu) - stary prestane
    fungovat, appku je nutne prenastavit."""
    user, err = _require_fleet_mobile_access()
    if err:
        return err
    token = secrets.token_urlsafe(24)
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE app_users SET gps_device_token=%s WHERE id=%s", (token, user["id"]))
        conn.commit()
    finally:
        conn.close()
    return jsonify({"token": token})


@app.get("/api/fleet/gps-ping")
def fleet_gps_ping():
    """Prijem polohy z externi GPS appky (Traccar Client, OsmAnd
    protokol) - BEZ session, autentizace jen pres gps_device_token v
    parametru "id" (appka nema cookie, je to headless klient). Pripoji
    bod k aktualne aktivni jizde daneho ridice (jizdu porad zahajuje/
    ukoncuje rucne tlacitkem v capture.html, tenhle endpoint jen
    prubezne doplnuje body misto puvodniho watchPosition na klientovi).
    Bez aktivni jizdy se ping tise zahodi (200 OK, at appka nezkousi
    dokola relogovat/hlasit chybu) - normalni stav mimo jizdu."""
    token = request.args.get("id")
    if not token:
        return jsonify({"error": "Chybí id (token)."}), 400
    try:
        lat = float(request.args.get("lat"))
        lng = float(request.args.get("lon"))
    except (TypeError, ValueError):
        return jsonify({"error": "Chybí nebo neplatné lat/lon."}), 400

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, role, active FROM app_users WHERE gps_device_token=%s", (token,))
            user = cur.fetchone()
            if not user or not user["active"] or user["role"] not in FLEET_ROLES:
                return jsonify({"error": "Neplatný token."}), 403

            cur.execute(
                "SELECT id, distance_km FROM fleet_trips WHERE user_id=%s AND status='active' "
                "ORDER BY started_at DESC LIMIT 1",
                (user["id"],),
            )
            trip = cur.fetchone()
            if not trip:
                return jsonify({"ok": True, "note": "no active trip"})

            cur.execute(
                "SELECT lat, lng FROM fleet_trip_points WHERE trip_id=%s ORDER BY id DESC LIMIT 1",
                (trip["id"],),
            )
            last = cur.fetchone()
            increment = _haversine_km(float(last["lat"]), float(last["lng"]), lat, lng) if last else 0.0
            if increment > MAX_PING_JUMP_KM:
                increment = 0.0  # pravdepodobne chybny GPS fix, ne skutecny skok
            new_distance = round(float(trip["distance_km"]) + increment, 2)

            cur.execute(
                "INSERT INTO fleet_trip_points (trip_id, lat, lng, distance_km) VALUES (%s,%s,%s,%s)",
                (trip["id"], lat, lng, new_distance),
            )
            cur.execute("UPDATE fleet_trips SET distance_km=%s WHERE id=%s", (new_distance, trip["id"]))
        conn.commit()
    finally:
        conn.close()
    return jsonify({"ok": True})


@app.get("/api/fleet/trips/current")
def fleet_mobile_trip_current():
    user, err = _require_fleet_mobile_access()
    if err:
        return err
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT t.*, v.name AS vehicle_name, v.spz AS vehicle_spz "
                "FROM fleet_trips t JOIN fleet_vehicles v ON v.id = t.vehicle_id "
                "WHERE t.user_id=%s AND t.status='active' ORDER BY t.started_at DESC LIMIT 1",
                (user["id"],),
            )
            row = cur.fetchone()
    finally:
        conn.close()
    return jsonify({"trip": _serialize_trip(row) if row else None})


@app.post("/api/fleet/trips/start")
def fleet_mobile_trip_start():
    user, err = _require_fleet_mobile_access()
    if err:
        return err
    body = request.get_json(silent=True) or {}
    vehicle_id = body.get("vehicle_id")
    lat, lng = body.get("lat"), body.get("lng")
    if not vehicle_id:
        return jsonify({"error": "Vyberte vozidlo."}), 400
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM fleet_trips WHERE user_id=%s AND status='active'", (user["id"],))
            if cur.fetchone():
                return jsonify({"error": "Už máte rozjetou jízdu - nejdřív ji ukončete.", "code": "trip_in_progress"}), 409
            # bot23 2026-08-18: FOR UPDATE na radek vozidla - serializuje
            # soubezne pokusy o zahajeni jizdy STEJNYM vozidlem (bez
            # tohodle by dva pozadavky ve stejnem okamziku mohly oba projit
            # nasledujici kontrolou "zadna aktivni jizda" driv, nez kterykoli
            # stihl INSERT, a vytvorit 2 soubezne aktivni jizdy na jednom
            # aute). Druhy pozadavek pockA na commit prvniho, pak uvidi
            # jeho novou aktivni jizdu spravne.
            cur.execute("SELECT id, active FROM fleet_vehicles WHERE id=%s FOR UPDATE", (vehicle_id,))
            vehicle = cur.fetchone()
            if not vehicle or not vehicle["active"]:
                return jsonify({"error": "Vozidlo nenalezeno nebo neaktivní."}), 404
            # bot23 2026-08-18: TAKY FOR UPDATE, ne jen radek vozidla vyse -
            # MySQL REPEATABLE READ (vychozi izolace) znamena, ze obycejny
            # (nezamykajici) SELECT v jiz otevrene transakci muze cist
            # STARY snapshot i PO odblokovani z cekani na zamek vyse (zamek
            # serializuje CASOVANI, ale nezajistuje sam o sobe cerstvost
            # dat obycejneho SELECTu). Bez FOR UPDATE i zde by druhy
            # pozadavek po odblokovani porad videl "zadna aktivni jizda" a
            # presel by do INSERTu - presne overeno zivym testem (2 vlakna
            # soubezne), kde bez tehle druhe FOR UPDATE prvni fix sam o
            # sobe nestacil.
            cur.execute("SELECT id FROM fleet_trips WHERE vehicle_id=%s AND status='active' FOR UPDATE", (vehicle_id,))
            if cur.fetchone():
                return jsonify({"error": "Tímto vozidlem už právě někdo jede.", "code": "vehicle_in_use"}), 409
            # Robert 2026-08-05 ("jízdy číslujme"): vlastni sekvence na
            # vozidlo, stejny princip jako papirova kniha jizd (kazde
            # auto vlastni sesit/cislovani).
            cur.execute("SELECT COALESCE(MAX(trip_number),0)+1 AS n FROM fleet_trips WHERE vehicle_id=%s", (vehicle_id,))
            trip_number = cur.fetchone()["n"]
            cur.execute(
                "INSERT INTO fleet_trips (vehicle_id, trip_number, user_id, status, start_lat, start_lng) "
                "VALUES (%s,%s,%s,'active',%s,%s)",
                (vehicle_id, trip_number, user["id"], lat, lng),
            )
            trip_id = cur.lastrowid
        conn.commit()
    finally:
        conn.close()
    log_audit(user["id"], "create", "fleet_trip", trip_id, f"vehicle_id={vehicle_id}, jizda c. {trip_number}")
    return jsonify({"id": trip_id, "trip_number": trip_number}), 201


@app.post("/api/fleet/trips/<int:trip_id>/end")
def fleet_mobile_trip_end(trip_id):
    user, err = _require_fleet_mobile_access()
    if err:
        return err
    body = request.get_json(silent=True) or {}
    lat, lng, distance_km = body.get("lat"), body.get("lng"), body.get("distance_km")
    odometer_km = body.get("odometer_km")
    if odometer_km is None:
        return jsonify({"error": "Zadejte stav kilometrů na tachometru."}), 400
    try:
        odometer_km = int(odometer_km)
    except (TypeError, ValueError):
        return jsonify({"error": "Stav kilometrů musí být celé číslo."}), 400
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, vehicle_id, trip_number, distance_km FROM fleet_trips "
                "WHERE id=%s AND user_id=%s AND status='active'",
                (trip_id, user["id"]),
            )
            trip = cur.fetchone()
            if not trip:
                return jsonify({"error": "Jízda nenalezena nebo už není aktivní."}), 404
            final_distance = distance_km if distance_km is not None else float(trip["distance_km"])
            cur.execute(
                "UPDATE fleet_trips SET status='finished', ended_at=NOW(), end_lat=%s, end_lng=%s, "
                "distance_km=%s, odometer_km=%s WHERE id=%s",
                (lat, lng, final_distance, odometer_km, trip_id),
            )
            # Robert 2026-08-05 ("u knihy jízd je potřeba držet
            # kontinuitu km... pokud nesedí počet ujetých km se zadaným
            # stavem km na konci jízdy pošli email"): porovnej rozdil
            # tachometru vuci PREDCHOZI jizde STEJNEHO vozidla s GPS
            # vzdalenosti teto jizdy. Tolerance kvuli GPS nepresnosti
            # (checkpointy jen kazde ~2 km, ne presna trasa) - vlastni
            # odhad, Robert presne cislo nezadal: max(5 km, 15 % z GPS
            # vzdalenosti).
            cur.execute(
                "SELECT odometer_km FROM fleet_trips WHERE vehicle_id=%s AND trip_number<%s "
                "AND odometer_km IS NOT NULL ORDER BY trip_number DESC LIMIT 1",
                (trip["vehicle_id"], trip["trip_number"]),
            )
            prev = cur.fetchone()
            continuity_alert = None
            if prev is not None:
                delta = odometer_km - prev["odometer_km"]
                tolerance = max(5, final_distance * 0.15)
                if delta < 0 or abs(delta - final_distance) > tolerance:
                    cur.execute(
                        "SELECT v.name AS vehicle_name, v.spz AS vehicle_spz FROM fleet_vehicles v WHERE v.id=%s",
                        (trip["vehicle_id"],),
                    )
                    vehicle = cur.fetchone()
                    continuity_alert = {
                        "vehicle_name": vehicle["vehicle_name"], "vehicle_spz": vehicle["vehicle_spz"],
                        "prev_odometer": prev["odometer_km"], "delta": delta,
                    }
        conn.commit()
    finally:
        conn.close()
    log_audit(user["id"], "update", "fleet_trip", trip_id, f"ukonceno, {final_distance} km, tachometr {odometer_km} km")
    if continuity_alert:
        diff = continuity_alert["delta"] - final_distance
        body_text = (
            f"Vozidlo: {continuity_alert['vehicle_name']} ({continuity_alert['vehicle_spz']})\n"
            f"Řidič: {user['name'] or user['email']}\n"
            f"Jízda č. {trip['trip_number']} (id {trip_id})\n\n"
            f"Předchozí stav tachometru: {continuity_alert['prev_odometer']} km\n"
            f"Nově zadaný stav tachometru: {odometer_km} km\n"
            f"Nájezd podle tachometru: {continuity_alert['delta']} km\n"
            f"Vzdálenost podle GPS: {final_distance:.1f} km\n"
            f"Rozdíl km: {diff:+.1f} km\n\n"
            f"Zkontrolujte prosím zadaný stav kilometrů v Knize jízd."
        )
        # OPRAVA (bot10, 2026-08-26, schvaleno bot3) - primy send_email()
        # obchazel e-mailovou schvalovaci frontu (WORKFLOW.md bod 16).
        # emails.send_and_log(auto=True) misto rovnou odeslani, stejny
        # vzor jako crm.py::crm_admin_lead_reply.
        try:
            import emails
            emails.send_and_log(
                None, template_key="custom", recipient=FLEET_CONTINUITY_ALERT_EMAIL,
                subject=f"Kniha jízd – nesedí návaznost km ({continuity_alert['vehicle_name']}, jízda č. {trip['trip_number']})",
                body=body_text, auto=True,
            )
        except Exception as e:
            log_audit(user["id"], "error", "fleet_trip", trip_id, f"email o nesouladu km se nepodarilo zaradit do fronty: {e}")
    return jsonify({"ok": True, "distance_km": final_distance, "odometer_km": odometer_km})


# ==================== Mobilni fotoapka: zastavky (tankovani, zakaznik/partner) ====================

@app.post("/api/fleet/trips/<int:trip_id>/customer-stop")
def fleet_mobile_trip_customer_stop(trip_id):
    """Cilova destinace jizdy (Robert 2026-08-05: "zastavka muze byt
    take nejaky zakaznik, nebo obchodni partner, takze se v takove
    zastavce vyzada Nazev firmy a Mesto") - proto ciste volny text,
    ZADNE propojeni na kartoteku shop_customers (obchodni partner v ni
    nemusi vubec byt)."""
    user, err = _require_fleet_mobile_access()
    if err:
        return err
    body = request.get_json(silent=True) or {}
    company_name = (body.get("company_name") or "").strip()
    city = (body.get("city") or "").strip()
    lat, lng = body.get("lat"), body.get("lng")
    if not company_name or not city:
        return jsonify({"error": "Zadejte název firmy i město."}), 400
    if lat is None or lng is None:
        return jsonify({"error": "Chybí GPS poloha."}), 400
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            trip = _get_active_trip_for_user(cur, trip_id, user["id"])
            if not trip:
                return jsonify({"error": "Jízda nenalezena nebo už není aktivní."}), 404
            cur.execute(
                "INSERT INTO fleet_trip_stops (trip_id, stop_type, lat, lng, company_name, city) "
                "VALUES (%s,'customer',%s,%s,%s,%s)",
                (trip_id, lat, lng, company_name, city),
            )
            stop_id = cur.lastrowid
        conn.commit()
    finally:
        conn.close()
    return jsonify({"id": stop_id}), 201


@app.post("/api/fleet/trips/<int:trip_id>/fuel-stop")
def fleet_mobile_trip_fuel_stop(trip_id):
    """Doklad o tankovani (Robert 2026-08-05: "doklad se naskenuje ve
    fotoapce, vlozi se do spravne slozky disku a zaroven se nacte do
    knihy jizd, tzn bude to vzdy jako zastavka v prehledu jizd").
    Zamerne ZADNA castka/litry (Robert: "jen fotka dokladu") - jen
    soubor, ulozeny rovnou do Sdileneho disku (slozka podle
    fuel_receipt_folder_path nastaveni, vychozi "Kniha jízd/
    Tankování", + vzdy podslozka s nazvem vozidla, viz
    _ensure_drive_folder_path - zalozena automaticky pri prvnim
    pouziti), zadny mezikrok pres osobni kos jako u bezneho foceni.

    Robert 2026-08-06 ("z knihy jízd se musí posílat automaticky
    doklady o tankování na email, určí se v Knize jízd, email tam
    zadá admin a automaticky se uloží na sdíleném disku ve složce
    Kniha jizd" + pozdeji "dej na knihu jízd nastavení adresáře pro
    ukládání dokladů o tankování"): po ulozeni na disk se doklad navic
    posle emailem na adresu z fleet_settings_get/set (app_settings
    klic FLEET_FUEL_RECEIPT_EMAIL_SETTING_KEY) - pokud neni adresa
    nastavena, email se jen preskoci (stejne jako u continuity alertu
    vyse, disk-ulozeni je hlavni cesta, email je navic). Cilova slozka
    na disku je editovatelna stejnym zpusobem
    (FLEET_FUEL_RECEIPT_FOLDER_PATH_SETTING_KEY)."""
    user, err = _require_fleet_mobile_access()
    if err:
        return err
    media = request.files.get("media")
    if not media or not media.filename:
        return jsonify({"error": "Chybí fotka dokladu."}), 400
    lat = request.form.get("lat", type=float)
    lng = request.form.get("lng", type=float)
    if lat is None or lng is None:
        return jsonify({"error": "Chybí GPS poloha."}), 400
    data = media.read()
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            trip = _get_active_trip_for_user(cur, trip_id, user["id"])
            if not trip:
                return jsonify({"error": "Jízda nenalezena nebo už není aktivní."}), 404
            folder_path = get_setting(cur, FLEET_FUEL_RECEIPT_FOLDER_PATH_SETTING_KEY, "")
            base_folder_id = _ensure_drive_folder_path(cur, folder_path, user["id"])
            vehicle_folder_id = _ensure_drive_folder(cur, base_folder_id, trip["vehicle_name"], user["id"])
            stored_filename = safe_stored_filename(media.filename or "tankovani.jpg")
            display_name = f"tankovani_{trip_id}_{stored_filename}"
            with open(os.path.join(DRIVE_FILES_DIR, stored_filename), "wb") as fh:
                fh.write(data)
            cur.execute(
                "INSERT INTO shared_drive_files (folder_id, filename, stored_filename, content_type, size_bytes, uploaded_by) "
                "VALUES (%s,%s,%s,%s,%s,%s)",
                (vehicle_folder_id, display_name, stored_filename, media.mimetype, len(data), user["id"]),
            )
            drive_file_id = cur.lastrowid
            cur.execute(
                "INSERT INTO fleet_trip_stops (trip_id, stop_type, lat, lng, drive_file_id) VALUES (%s,'fuel',%s,%s,%s)",
                (trip_id, lat, lng, drive_file_id),
            )
            stop_id = cur.lastrowid
            fuel_receipt_email = get_setting(cur, FLEET_FUEL_RECEIPT_EMAIL_SETTING_KEY, "")
        conn.commit()
    finally:
        conn.close()
    log_audit(user["id"], "create", "fleet_trip_stop", stop_id, f"tankovani, trip_id={trip_id}")
    if fuel_receipt_email:
        effective_folder_path = folder_path.strip("/") if folder_path else FLEET_FUEL_RECEIPT_FOLDER_PATH_DEFAULT
        body_text = (
            f"Vozidlo: {trip['vehicle_name']} ({trip['vehicle_spz']})\n"
            f"Řidič: {user['name'] or user['email']}\n"
            f"Jízda č. {trip['trip_number']} (id {trip_id})\n"
            f"GPS poloha: {lat}, {lng}\n\n"
            f"Doklad je uložen na Sdíleném disku › {effective_folder_path.replace('/', ' › ')} › {trip['vehicle_name']}."
        )
        # OPRAVA (bot10, 2026-08-26, schvaleno bot3) - primy send_email()
        # obchazel e-mailovou schvalovaci frontu (WORKFLOW.md bod 16).
        # emails.send_and_log(auto=True) nema oporu pro libovolnou binarni
        # prilohu (jen PDF dogenerovane z document_id) - priloha se proto
        # VYPOUSTI, doklad uz je ulozeny na Sdilenem disku a text e-mailu
        # (nize) na jeho umisteni odkazuje, takze schvalujici admin i tak
        # vidi, kde foto najit.
        try:
            import emails
            emails.send_and_log(
                None, template_key="custom", recipient=fuel_receipt_email,
                subject=f"Kniha jízd – doklad o tankování ({trip['vehicle_name']}, jízda č. {trip['trip_number']})",
                body=body_text, auto=True,
            )
        except Exception as e:
            log_audit(user["id"], "error", "fleet_trip_stop", stop_id, f"email s dokladem o tankovani se nepodarilo zaradit do fronty: {e}")
    return jsonify({"id": stop_id, "drive_file_id": drive_file_id}), 201

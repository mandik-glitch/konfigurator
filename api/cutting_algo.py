"""
Rezne plany - cisty optimalizacni jadro (bot4, "optimizer", 2026-07-25).

ZAMERNE bez zavislosti na Flask/DB (na rozdil od orders.py/cart.py) - viz
NAVRH_REZNE_PLANY.md, sekce 3. Duvod: tenhle soubor resi jen matematiku
(1D/2D bin-packing), musi jit snadno a rychle testovat izolovane (Node.js
harness ekvivalent u ostatnich bot v projektu - tady python primo, staci
`python3 -c "..."` nebo unit testy, zadny Flask app kontext potreba).
DB/HTTP vrstva (nacteni polozek objednavky, ulozeni vysledku, admin
endpoint) pribude v samostatnem `cutting.py` (stejny vzor jako
orders.py vs. cart.py) az po potvrzeni navrhu Robertem - VIZ
NAVRH_REZNE_PLANY.md bod 5 (otevrene otazky), NENASAZENO.

Verejne funkce:
  pack_1d(pieces, stock_options, kerf_mm) -> dict
  pack_2d(pieces, stock_options, kerf_mm) -> dict

Obe pracuji vyhradne s plain dict/list vstupy a vraci plain dict vystup
(JSON-serializovatelne primo), aby je bylo mozne 1:1 zavolat z Flask
endpointu i z testu bez uprav.
"""


# ---------------------------------------------------------------------------
# 1D - profily / tyce
# ---------------------------------------------------------------------------

def pack_1d(pieces, stock_options, kerf_mm=3.0):
    """
    pieces: [{"id":..., "label":..., "length_mm": float, "qty": int}, ...]
    stock_options: [{"id":..., "label":..., "length_mm": float,
                      "qty": int|None (None = neomezeno), "price_czk": float}, ...]

    Vraci:
    {
      "bars": [{"stock_id":, "stock_label":, "stock_length_mm":,
                 "pieces": [{"piece_id":, "label":, "length_mm":, "position_mm":}],
                 "used_mm":, "waste_mm":, "cuts": int}],
      "unplaced": [{"piece_id":, "label":, "length_mm":, "qty":}],
      "stats": {"bars_used": int, "total_stock_mm":, "total_used_mm":,
                 "total_waste_mm":, "total_cuts": int, "total_price_czk": float}
    }

    Algoritmus: kusy serazeny sestupne podle delky. Pro kazdy kus se
    zkusi "best fit" mezi jiz otevrenymi tycemi (tyc s nejmensim zbylym
    volnym mistem, do ktereho se kus i s kerfem jeste vejde). Pokud
    zadna otevrena tyc nesedi, otevre se nova - z dostupnych
    stock_options se vybere NEJMENSI varianta, do ktere se kus vejde
    (min. odpad predem, min. cena materialu). Pokud se kus nevejde do
    zadne skladove delky vubec, jde do "unplaced".
    """
    stock_sorted = sorted(stock_options, key=lambda s: s["length_mm"])
    remaining_stock_qty = {
        s["id"]: (None if s.get("qty") is None else int(s["qty"])) for s in stock_options
    }
    stock_by_id = {s["id"]: s for s in stock_options}

    units = []
    for p in pieces:
        for _ in range(int(p["qty"])):
            units.append({"piece_id": p["id"], "label": p.get("label", p["id"]), "length_mm": float(p["length_mm"])})
    units.sort(key=lambda u: -u["length_mm"])

    bars = []  # kazda: {stock_id,label,length_mm,pieces:[...],used_mm,free_mm}
    unplaced_counter = {}

    def _try_open_new_bar(need_mm):
        for s in stock_sorted:
            if s["length_mm"] + 1e-9 < need_mm:
                continue
            avail = remaining_stock_qty[s["id"]]
            if avail is not None and avail <= 0:
                continue
            if avail is not None:
                remaining_stock_qty[s["id"]] -= 1
            bars.append({
                "stock_id": s["id"], "stock_label": s.get("label", s["id"]),
                "stock_length_mm": s["length_mm"], "pieces": [], "used_mm": 0.0,
            })
            return bars[-1]
        return None

    for u in units:
        need = u["length_mm"]
        # najdi nejlepsi jiz otevrenou tyc (nejmensi zbyle misto, kam se kus vejde)
        best_bar, best_free = None, None
        for b in bars:
            free = b["stock_length_mm"] - b["used_mm"]
            # kerf pred novym kusem, pokud uz na tyci neco je
            required = need + (kerf_mm if b["pieces"] else 0.0)
            if free + 1e-9 >= required:
                if best_free is None or free < best_free:
                    best_bar, best_free = b, free
        if best_bar is None:
            # potreba nova tyc - musi pojmout aspon (need), kerf na prvnim kusu neni
            best_bar = _try_open_new_bar(need)
        if best_bar is None:
            unplaced_counter.setdefault(u["piece_id"], {"label": u["label"], "length_mm": need, "qty": 0})
            unplaced_counter[u["piece_id"]]["qty"] += 1
            continue

        pos = best_bar["used_mm"] + (kerf_mm if best_bar["pieces"] else 0.0)
        best_bar["pieces"].append({
            "piece_id": u["piece_id"], "label": u["label"], "length_mm": need, "position_mm": round(pos, 1),
        })
        best_bar["used_mm"] = pos + need

    total_stock_mm = total_used_mm = total_price = 0.0
    total_cuts = 0
    out_bars = []
    for b in bars:
        waste = b["stock_length_mm"] - b["used_mm"]
        # 1 rez na oddeleni kazdeho kusu od zbytku tyce, krome posledniho
        # kusu, pokud presne saha na konec tyce (zadny odpad k oddeleni).
        n = len(b["pieces"])
        cuts = n if waste > 0.5 else max(0, n - 1)
        out_bars.append({
            "stock_id": b["stock_id"], "stock_label": b["stock_label"],
            "stock_length_mm": b["stock_length_mm"], "pieces": b["pieces"],
            "used_mm": round(b["used_mm"], 1), "waste_mm": round(waste, 1),
            "utilization_percent": round(b["used_mm"] / b["stock_length_mm"] * 100, 1) if b["stock_length_mm"] else 0.0,
            "cuts": cuts,
        })
        total_stock_mm += b["stock_length_mm"]
        total_used_mm += b["used_mm"]
        total_cuts += cuts
        total_price += stock_by_id[b["stock_id"]].get("price_czk", 0.0)

    unplaced = list(unplaced_counter.values())

    return {
        "bars": out_bars,
        "unplaced": unplaced,
        "stats": {
            "bars_used": len(out_bars),
            "total_stock_mm": round(total_stock_mm, 1),
            "total_used_mm": round(total_used_mm, 1),
            "total_waste_mm": round(total_stock_mm - total_used_mm, 1),
            "total_cuts": total_cuts,
            "total_price_czk": round(total_price, 2),
        },
    }


# ---------------------------------------------------------------------------
# 2D - desky / panely (guillotine shelf packing)
# ---------------------------------------------------------------------------

def pack_2d(pieces, stock_options, kerf_mm=3.0):
    """
    pieces: [{"id":, "label":, "width_mm":, "height_mm":, "qty": int,
               "grain_locked": bool,
               "edge_bands": {"top":bool,"bottom":bool,"left":bool,"right":bool} (volitelne)}, ...]
    stock_options: [{"id":, "label":, "width_mm":, "height_mm":,
                       "qty": int|None, "price_czk": float}, ...]

    Vraci obdobnou strukturu jako pack_1d, jen "sheets" misto "bars" a
    kazdy umisteny kus ma navic "x_mm","y_mm","width_mm","height_mm",
    "rotated" (True = kus byl pro lepsi vyuziti otocen o 90 stupnu vuci
    deklarovane width_mm/height_mm - "edge_bands" NIZE zustava vzdy v
    PUVODNI (nerotovane) orientaci, volajici/UI si pri kresleni sam
    premapuje, ktera vizualni strana odpovida top/bottom/left/right po
    pripadne rotaci) a "edge_bands" (kopie ze vstupu, prazdny dict pokud
    nezadano - deska bez olepeni).

    Algoritmus: guillotine "shelf" packing (stejny princip jako pouzivaji
    realne formatovaci pily - vsechny rezy jdou od kraje ke kraji desky).
    Kusy serazene sestupne podle vysky. Na kazde desce se plni "police"
    (radky) zleva doprava; kdyz se kus nevejde do zadne existujici police
    sirkou, otevre se nova police pod tou posledni (pokud je na desce
    dost vysky). Kdyz se kus nevejde na zadnou existujici desku, otevre
    se nova (nejmensi skladova varianta, do ktere se kus vubec vejde v
    nejake orientaci).
    """
    stock_sorted = sorted(stock_options, key=lambda s: s["width_mm"] * s["height_mm"])
    remaining_stock_qty = {
        s["id"]: (None if s.get("qty") is None else int(s["qty"])) for s in stock_options
    }
    stock_by_id = {s["id"]: s for s in stock_options}

    units = []
    for p in pieces:
        for _ in range(int(p["qty"])):
            units.append({
                "piece_id": p["id"], "label": p.get("label", p["id"]),
                "width_mm": float(p["width_mm"]), "height_mm": float(p["height_mm"]),
                "grain_locked": bool(p.get("grain_locked", False)),
                # "edge_bands" je VZDY vzhledem k deklarovane (nerotovane)
                # orientaci width_mm x height_mm - viz "rotated" priznak
                # nize u kazdeho umisteneho kusu, ktery rika, jestli se
                # kus pro lepsi vyuziti otocil o 90 (pak si volajici sam
                # premapuje hrany na skutecnou vizualni stranu).
                "edge_bands": p.get("edge_bands") or {},
                "edge_banding_type": p.get("edge_banding_type"),
            })
    # razeni: vyssi kusy nejdriv (klasicky shelf heuristika), pri shode sirsi nejdriv
    units.sort(key=lambda u: (-max(u["height_mm"], u["width_mm"]) if not u["grain_locked"] else -u["height_mm"], -u["width_mm"]))

    def _fits(w, h, avail_w, avail_h, grain_locked):
        if w <= avail_w + 1e-9 and h <= avail_h + 1e-9:
            return (w, h)
        if not grain_locked and h <= avail_w + 1e-9 and w <= avail_h + 1e-9:
            return (h, w)
        return None

    sheets = []  # {stock_id,label,width_mm,height_mm,shelves:[{y,height,x_used}],placed:[...]}

    def _open_new_sheet(need_w, need_h, grain_locked):
        for s in stock_sorted:
            fit = _fits(need_w, need_h, s["width_mm"], s["height_mm"], grain_locked)
            if not fit:
                continue
            avail = remaining_stock_qty[s["id"]]
            if avail is not None and avail <= 0:
                continue
            if avail is not None:
                remaining_stock_qty[s["id"]] -= 1
            sheets.append({
                "stock_id": s["id"], "stock_label": s.get("label", s["id"]),
                "width_mm": s["width_mm"], "height_mm": s["height_mm"],
                "shelves": [], "placed": [],
            })
            return sheets[-1]
        return None

    unplaced_counter = {}

    for u in units:
        placed = False
        # zkus existujici police na existujicich deskach
        candidates = []
        for sheet in sheets:
            for shelf in sheet["shelves"]:
                # bot23 2026-08-18: kerf_mm se MUSI odecist tady, ne az pri
                # samotnem umisteni (radek ~242 pod timhle) - jinak kus s
                # width presne == avail_w projde kontrolou, ale umisti se
                # o kerf_mm ZA hranou desky (x = x_used + kerf + w >
                # sheet width_mm). pack_1d() i vetev "nova police" nize uz
                # kerf do kontroly pocitaly spravne, jen tahle chybela.
                pending_kerf = kerf_mm if shelf["x_used"] > 0 else 0.0
                avail_w = sheet["width_mm"] - shelf["x_used"] - pending_kerf
                fit = _fits(u["width_mm"], u["height_mm"], avail_w, shelf["height"], u["grain_locked"])
                if fit:
                    leftover_w = avail_w - fit[0]
                    candidates.append((leftover_w, sheet, shelf, fit))
        if candidates:
            candidates.sort(key=lambda c: c[0])
            _, sheet, shelf, (w, h) = candidates[0]
            x = shelf["x_used"] + (kerf_mm if shelf["x_used"] > 0 else 0.0)
            sheet["placed"].append({
                "piece_id": u["piece_id"], "label": u["label"],
                "x_mm": round(x, 1), "y_mm": round(shelf["y"], 1),
                "width_mm": w, "height_mm": h,
                "rotated": w != u["width_mm"], "edge_bands": u["edge_bands"],
                "edge_banding_type": u["edge_banding_type"],
            })
            shelf["x_used"] = x + w
            placed = True

        if not placed:
            # zkus novou polici na existujici desce (dost mista pod poslední policí)
            for sheet in sheets:
                y_used = sum(s["height"] + kerf_mm for s in sheet["shelves"]) if sheet["shelves"] else 0.0
                avail_h = sheet["height_mm"] - y_used
                fit = _fits(u["width_mm"], u["height_mm"], sheet["width_mm"], avail_h, u["grain_locked"])
                if fit:
                    w, h = fit
                    new_shelf = {"y": y_used, "height": h, "x_used": w}
                    sheet["shelves"].append(new_shelf)
                    sheet["placed"].append({
                        "piece_id": u["piece_id"], "label": u["label"],
                        "x_mm": 0.0, "y_mm": round(y_used, 1),
                        "width_mm": w, "height_mm": h,
                        "rotated": w != u["width_mm"], "edge_bands": u["edge_bands"],
                "edge_banding_type": u["edge_banding_type"],
                    })
                    placed = True
                    break

        if not placed:
            new_sheet = _open_new_sheet(u["width_mm"], u["height_mm"], u["grain_locked"])
            if new_sheet is None:
                unplaced_counter.setdefault(u["piece_id"], {
                    "label": u["label"], "width_mm": u["width_mm"], "height_mm": u["height_mm"], "qty": 0,
                })
                unplaced_counter[u["piece_id"]]["qty"] += 1
                continue
            fit = _fits(u["width_mm"], u["height_mm"], new_sheet["width_mm"], new_sheet["height_mm"], u["grain_locked"])
            w, h = fit
            shelf = {"y": 0.0, "height": h, "x_used": w}
            new_sheet["shelves"].append(shelf)
            new_sheet["placed"].append({
                "piece_id": u["piece_id"], "label": u["label"],
                "x_mm": 0.0, "y_mm": 0.0, "width_mm": w, "height_mm": h,
                "rotated": w != u["width_mm"], "edge_bands": u["edge_bands"],
                "edge_banding_type": u["edge_banding_type"],
            })

    total_stock_area = total_used_area = total_price = 0.0
    total_cuts = 0
    out_sheets = []
    for sheet in sheets:
        area = sheet["width_mm"] * sheet["height_mm"]
        used = sum(p["width_mm"] * p["height_mm"] for p in sheet["placed"])
        cuts = _guillotine_cuts_2d(sheet["width_mm"], sheet["height_mm"], sheet["shelves"], sheet["placed"])
        out_sheets.append({
            "stock_id": sheet["stock_id"], "stock_label": sheet["stock_label"],
            "width_mm": sheet["width_mm"], "height_mm": sheet["height_mm"],
            "pieces": sheet["placed"],
            "used_area_mm2": round(used, 1), "waste_area_mm2": round(area - used, 1),
            "utilization_percent": round(used / area * 100, 1) if area else 0.0,
            "cuts": cuts,
        })
        total_stock_area += area
        total_used_area += used
        total_price += stock_by_id[sheet["stock_id"]].get("price_czk", 0.0)
        total_cuts += cuts

    unplaced = list(unplaced_counter.values())

    return {
        "sheets": out_sheets,
        "unplaced": unplaced,
        "stats": {
            "sheets_used": len(out_sheets),
            "total_stock_area_mm2": round(total_stock_area, 1),
            "total_used_area_mm2": round(total_used_area, 1),
            "total_waste_area_mm2": round(total_stock_area - total_used_area, 1),
            "total_cuts": total_cuts,
            "total_price_czk": round(total_price, 2),
        },
    }


def _guillotine_cuts_2d(sheet_width_mm, sheet_height_mm, shelves, placed):
    """Přibližný počet gilotinových řezů potřebných k vyrobení téhle
    desky - vodorovné řezy oddělující jednotlivé "police" (shelf) +
    svislé řezy oddělující kusy uvnitř každé police. Jde o rozumný odhad
    pro dílnu (kolik řezů čekat), NE o 1:1 shodu s konkrétním CAM/
    optimalizačním softwarem - přesný postup řezání (pořadí, otočení
    desky) může být jiný.

    Pravidlo: pokud police/kus sahá přesně k okraji desky, poslední řez
    (oddělující od zbytkového odpadu) není potřeba - proto se pro
    poslední polici/poslední kus v polici odečítá 1, pokud nezůstává
    žádný zbytek."""
    if not shelves:
        return 0
    last_shelf = max(shelves, key=lambda s: s["y"])
    leftover_h = sheet_height_mm - (last_shelf["y"] + last_shelf["height"])
    horizontal_cuts = len(shelves) if leftover_h > 0.5 else max(0, len(shelves) - 1)

    vertical_cuts = 0
    for shelf in shelves:
        pieces_in_shelf = [p for p in placed if abs(p["y_mm"] - shelf["y"]) < 0.5]
        n = len(pieces_in_shelf)
        if n == 0:
            continue
        leftover_w = sheet_width_mm - shelf["x_used"]
        vertical_cuts += n if leftover_w > 0.5 else max(0, n - 1)

    return horizontal_cuts + vertical_cuts

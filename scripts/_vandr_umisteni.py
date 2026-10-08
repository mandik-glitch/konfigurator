# -*- coding: utf-8 -*-
"""Sdileny vypocet stitku umisteni (WORKFLOW.md pravidlo 51) pro Vandr
karty ze `vandrawee_work.stored_models`. Pouziva jak
`2026-09-22_vandr_fbx_watcher.py` (nova karta), tak
`2026-09-24_vandr_umisteni_backfill.py` (existujici karty) - JEDNA
definice mapovani, aby se nikdy nerozesly (viz pamet
feedback_check_duplicates_for_disagreeing_fields).

Zdroj pravdy: `stored_models.left_part_id` / `right_part_id` /
`bulkhead_part_id`. Overeno primo v DB 2026-09-24 (ne prevzato od
peera): z 324 radku ma 252 vyplneny jen left, 56 jen right, 17 jen
bulkhead, 1 ma left+right SOUCASNE (genuinne nejednoznacne), 0 radku ma
vsechny tri NULL.
"""

# regal_umisteni.id - overeno primo v DB 2026-09-24 (SELECT * FROM
# regal_umisteni), ne natvrdo odhadnuto.
RL_ID = 1   # regal_levy
RK_ID = 2   # kabina / za prepazkou
RP_ID = 7   # regal_pravy


def urcit_umisteni_id(stored_model_row):
    """stored_model_row = dict/Row s klici left_part_id/right_part_id/
    bulkhead_part_id (napr. primo radek `stored_models`). Vraci
    regal_umisteni.id, nebo None kdyz je stav nejednoznacny (0 nebo 2+
    z trech sloupcu vyplneno) - NIKDY tichy default."""
    vyplneno = [n for n in ("left_part_id", "right_part_id", "bulkhead_part_id")
                if stored_model_row.get(n) is not None]
    if vyplneno == ["left_part_id"]:
        return RL_ID
    if vyplneno == ["right_part_id"]:
        return RP_ID
    if vyplneno == ["bulkhead_part_id"]:
        return RK_ID
    return None

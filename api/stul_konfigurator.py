"""Konfigurator stolu (systemy 30 a 40) - RECEPT + generator dilu (bot8, 2026-10-02; system 40: bot10, 2026-10-04).

Robert 2026-10-02: pilotni stul = custom_shapes #577 "Stul system 30 SP002". Chce parametricky konfigurator:
sirka / hloubka desky a vyska pracovni desky, spodni police ano/ne, ostatni prislusenstvi zap/vyp; panel, supliky
a LED maji FIXNI velikost, profily se dopocitaji samy a vsechno musi zustat spravne napojene.
  * rozsah: sirka 500-3000, hloubka 400-1500, vyska pracovni desky 140-1200 (SYSTEM 45 = hluboky stul: hloubka 400-2500, nad 1500 mm stredni rada noh - viz SYSTEM_45 a blok 2c-45)
  * sirka nad 1500 mm: pridava se PREDNI i ZADNI STREDNI NOHA (jde posouvat k leve/prave noze)
  * hloubka nad 900 mm: do KAZDE bocnice se prida svisly profil doprostred, mezi horni a spodni pricku; deska KAZDE spodni police je pak po sirce o 62 mm uzsi (31 mm z kazde
    strany) a pod ni pribudou podperne profily v ose X mezi predni a zadni podelnik police (pocet = soucet ceil(rozpon / 800) - 1 pres rozpony mezi bocnimi pricky a pricky stredni
    nohy; 1-2 ks) - Robert 2026-10-03, pravidlo 800 mm je PREDPOKLAD
  * hloubka nad 900 mm: stejne podperne profily jako pod policí pribudou i pod PRACOVNI DESKU (Robert 2026-10-04) - mezi predni a zadni pricku pracovniho ramu, v ose X; rozpony se
    pocitaji po usecich mezi bocnimi prickami, prickou stredni nohy a prickami SUPLIKU (kdyz supliky jsou, drzi desku samy; kdyz nejsou, pricky zmizely a podpery se doplni)
  * panely a LED se pridavaji podle sirky (panel 1190 / 1481 / 1671 / 1975 mm podle parametru `panely_delka`, LED 1247 mm i s koncovkami)
  * DELKA PANELU (Robert 2026-10-07: dalsi velikosti perforovanych panelu; 1481 a 1671 mm upresnil, 1975 x 460 mm jsem dorobil): parametr `panely_delka` (1190 | 1481 | 1671 | 1975, vychozi 1190 = beze zmeny
    stavajicich konfiguraci i hashu) vybira dil katalogu (PANEL_TYPY); VSECHNY panely stolu maji stejnou delku. Rozmery panelu se berou z GLB (AABB), nic neni zadratovane. Zvolena delka, ktera se mezi
    zadni stojky nevejde, se SNIZI na nejdelsi mensi, ktera se vejde (`panely_info.delka`, hlasi to shop oznamenim); nevejde-li se ani 1190, plati puvodni problem `panel_nevejde`.

SYSTEMY (Robert 2026-10-04: "druhy generator stolu se systemem profilu 40x40, vnejsi rozmery stejne; prepnuti tehoz stolu mezi systemy jen pro zakladni konstrukci z profilu")
  Parametr `system` (30 | 35 | 40, vychozi 30) vybira zaznam v SYSTEMY: profil (30: Object_7 = Light 30x30; 35: profil_35x35 = 35x35 s drazkou 8 - od 2026-10-05 (Robert: 'spojky systemu 30, vzdy
  vystredit na stred drazky': rohove spojky 3158, patky 3251 a sikme spojky 3254 jsou ze systemu 30, zaslepka 3090 je 35x35, sablona `stul_sablona_system35.json` z odvod_sablony_35.py); 40: Object_11 = SuperLight S10 40x40),
  rohovou spojku (3158 / 3158 / 3176), zmrazenou
  sablonu (`stul_sablona_577.json` / `stul_sablona_system40.json`, odvozena skriptem scripts/2026-10-04_system40/odvod_sablony_40.py: VNEJSI rozmery stolu stejne, nohy dovnitr o 5 mm,
  konce, okraje a rohy prepocitane), zaslepku a patku na konci nohy a konstanty, ktere zavisi na sirce profilu (polovina profilu, rozteč polic, kraceni desky police, nejkratsi noha...).
  Pravidla posunu (R) jsou v obou systemech STEJNA (linearni v hloubce, sirce a vysce) - lisi se sablona a tyhle konstanty. Vychozi system 30 dava BITOVE STEJNE vysledky jako pred
  zavedenim systemu (zlaty test #577, hashe konfiguraci). Aktivni system drzi kontext `_v_systemu(...)`, ktery nastavuje vstup (`sestav_stul`, `_sestav_jadro`, ...); funkce nad vysledkem
  (`vyrobni_vypis`, `ovladani_3d`) ho berou z `r["parametry"]["system"]`, cenove/kusovnikove funkce nad dily poznaji system podle part_id (profil Object_7 / Object_11).
  Sikme vzpery ramen LED jsou v obou systemech (30: spojka 3254, 40: spojka 3220; geometrie 3220 z vlastniho tvaru #178 "Sikma spojka 40 na profilu 40" a z meshe, viz VZPERA_* a SYSTEMY[...]["vzpera_*"]).
  Priznak SYSTEMY[...]["vzpery"] = False by system bez vzper automaticky odebral (zapnuty parametr `vzpery` s duvodem v `odebrano`); dnes ho maji oba systemy zapnuty.

NAVLEK NOHOU (Robert 2026-10-05, jen system 35 - "ergonomicky balici stul": mechanicky volitelna vyska)
  Parametry `navlek` (zap/vyp) a `navlek_delka` (200-400 mm): na spodek KAZDE nohy (i strednich) se misto koleček / zaslepek / patek nasadi jekl 40x40, stena 2 mm (profil 35x35 se do
  vnitrnich 36 mm zasune s vuli 0,5 mm), tak aby aspon NAVLEK_ZASUN = 70 mm nohy bylo v jeklu; dole na jeklu je jeklova zaslepka (priruba 3 mm). Navlek vytlaci kolecka i patky
  (kolecka = patky = False, jsou-li zapnute) a profil nohy se zkrati o (delka navleku - 70 + priruba) - vyska stolu se nemeni. V UROVNI NAVLEKU (od podlahy po jeho horni konec + 3 mm) nesmi
  byt zadny jiny komponent: nejnizsi police (osa ramu) je nejmene o 3 mm + pul profilu nad hornim koncem jeklu, ostatni komponenty (drzak PET, supliky, police pod vyrezem...) pod nej nesmi sahat
  (problem `navlek_kolize`, prislusenstvi se odebere samo). Delka navleku se na stolu dane vysky orizne na nejvetsi mozne (`navlek_meze`); nevejde-li se ani 200 mm, navlek se odebere (`navlek_vyska`).
  Jekl ma vnejsi rohy srazene 45 st. o NAVLEK_SRAZENI = 2 mm (osmiuhelnikovy obrys jako jekl nohy stolu SSE v katalogu; Robert 2026-10-05), zaslepka stejny obrys prirub.
  Navlek a zaslepka jsou PROCEDURALNI dily (jekl_40x40x2, jekl_zaslepka_40; tvar vyrabi stul_glb, obalka PROCEDURALNI_BBOX), cena je pravidlo (stul_api.extra_prace: pravidla `cena_navlek_200` / `cena_navlek_400`).

CO TENHLE MODUL JE
  `sestav_stul(**parametry)` vrati dily stolu ve STEJNEM formatu jako `custom_shapes.data.parts` (position, quaternion,
  scale, lic_peers, attached_to) + problemy (porusena konstrukcni pravidla), rozmery a seznam spoju. Cista funkce:
  zadna DB, zadny zapis. Scena, server (cena/kosik) i zakaznicky prohlizec ji volaji STEJNE.

JAK TO FUNGUJE (recept = pravidla nize + zmrazena sablona)
  Zaklad je ZMRAZENY snimek #577 (`api/stul_sablona_577.json`, 50 dilu). Vychozi parametry davaji presne ten snimek
  (zlaty test). Kazdy dil sablony ma pravidlo: o kolik se POSUNE jeho stred a o kolik se zmeni jeho delka, kdyz se zmeni
  hloubka D, sirka W a vyska H - LINEARNE (kotvy: predni/zadni noha, leva/prava noha, podlaha, rovina desky).
  Spojky (rohove 30x30) se neposouvaji "po svem": poloha spojky = UZEL spoje (pruseciky os obou spojenych profilu) +
  pevne odsazeni ze vzoru (15 / 14,14 / 13,5 mm). Nove spoje (stredni nohy, stredni profily bocnic) dostanou spojku
  zkopirovanou z ANALOGICKEHO spoje sablony (stejny tvar spoje = stejna spojka).
  Profily konci vzdy na licich nohou: pricka = rozteč nohou - 30 mm (celo dosedá celou plochou).

KONTROLA NAPOJENI (vysledek v `problemy`; konfiguraci s problemy se nesmi nabidnout)
  * kazdy KONEC profilu, ktery v sablone dosedal na jiny profil, musi dosedat i ted (nic neni "ve vzduchu"),
  * spojky sedi na svem spoji (prekryvaji oba spojene profily),
  * dily se nezanoruji (prunik AABB > 1 mm), delky profilu >= 30 mm a <= 3000 mm (nejdelsi tyc).
  * `lic_peers` se pocitaji z GEOMETRIE stejnou definici spoje jako scena (celo na celo/stenu).
"""
import collections.abc
import contextvars
import json
import math
import os
import struct
from collections import OrderedDict

import numpy as np

_DIR = os.path.dirname(os.path.abspath(__file__))
SABLONA_PATH = os.path.join(_DIR, "stul_sablona_577.json")
SABLONA_PATH_40 = os.path.join(_DIR, "stul_sablona_system40.json")
SABLONA_PATH_35 = os.path.join(_DIR, "stul_sablona_system35.json")
KATALOG_DIR = os.path.join(os.path.dirname(_DIR), "webapp", "katalog")

# ---------------------------------------------------------------------------------------------------------------------
# SYSTEMY PROFILU (30 = Light 30x30, drazka 8; 40 = SuperLight S10 40x40, drazka 10) - viz hlavicka modulu
# ---------------------------------------------------------------------------------------------------------------------
DESKA_TLOUSTKA = 18.0              # laminodeska (obe systemy)
SYSTEMY = {
    30: {"system": 30, "profil": "Object_7", "profil_mm": 30.0, "spojka": "product_3158", "sablona": SABLONA_PATH, "nazev_profilu": "profil 30×30",
         "zaslepka": "product_3071", "zaslepka_vyska": 3.0, "patka": "product_3251", "patka_delka": 75.0, "patka_zasun": 30.0,
         "deska_zkraceni": 0.0,                 # o kolik je pracovni deska (a deska police) v sablone KRATSI nez v sablone 30 (800 / 650 mm)
         "police_min_od_podlahy": 130.0,        # nejnizsi mozna osa ramu police nad podlahou (mm)
         "vyrez_x": 100.0,                      # vychozi vzdalenost vyrezu od PREDNI hrany desky (mm); police pod vyrezem (zavesy z predni pricky) se pak nezanori do zavesu
         "odstup_od_nohou": 30.0,               # nejmensi volna vzdalenost suplikoveho boxu od lice nohy (mm; Robert): za rohovymi spojkami (u strednich noh sahaji 42 mm od osy nohy) zbyvaji 3 mm
         "vzpery": True},                       # sikme vzpery ramen LED (spojka 3254)
    35: {"system": 35, "profil": "profil_35x35", "profil_mm": 35.0, "spojka": "product_3158", "sablona": SABLONA_PATH_35, "nazev_profilu": "profil 35×35",   # Robert 2026-10-05: spojky systemu 30, vystredene na stred drazky
         "zaslepka": "product_3090", "zaslepka_vyska": 3.3, "patka": "product_3251", "patka_delka": 75.0, "patka_zasun": 30.0,
         "deska_zkraceni": 5.0,                 # zadni hrana desek lezi na lici zadnich noh, ktere jsou o 2 x 2,5 mm vic vpredu
         "police_min_od_podlahy": 132.5,        # stejne spodni lico ramu police nad podlahou jako v 30 (osa o 2,5 mm vys)
         "vyrez_x": 105.0,                      # zavesy police pod vyrezem jsou o 5 mm sirsi (profil 35)
         "odstup_od_nohou": 30.0,               # rohove spojky 3158 (rameno 27 mm) u strednich noh sahaji 27 + 17,5 = 44,5 mm od osy nohy: box od lice nohy 30 mm = 47,5 mm od osy (3 mm za spojkou)
         "vzpery": True},                       # sikme vzpery ramen LED (spojka 3254 ze systemu 30, vystredena na stred drazky)
    40: {"system": 40, "profil": "Object_11", "profil_mm": 40.0, "spojka": "product_3176", "sablona": SABLONA_PATH_40, "nazev_profilu": "profil 40×40",
         "zaslepka": "product_3091", "zaslepka_vyska": 3.3, "patka": "product_3283", "patka_delka": 79.0, "patka_zasun": 30.0,
         "deska_zkraceni": 10.0,                # zadni hrana desek lezi na lici zadnich noh, ktere jsou o 2 x 5 mm vic vpredu
         "police_min_od_podlahy": 135.0,        # stejne spodni lico ramu police nad podlahou jako v 30 (osa o 5 mm vys)
         "vyrez_x": 110.0,                      # zavesy police pod vyrezem jsou o 10 mm sirsi (profil 40): deska police (vyrez x - 40 mm) musi zacit az za jejich vnitrnim licem
         "odstup_od_nohou": 40.0,               # rohove spojky 3176 u strednich noh sahaji 57 mm od osy nohy (arm 37 + pul profilu 20): box od lice nohy 40 mm = 60 mm od osy, tedy tez 3 mm za spojkou
         "vzpery": True},                       # sikme vzpery ramen LED (spojka 3220, "Spojka uhel 45 4040"); geometrie viz VZPERA_* nize
}
SYSTEM_VYCHOZI = 30
# ---------------------------------------------------------------------------------------------------------------------
# SSE STUL = SYSTEM 41 (bot8, 2026-10-05; Robert: "ergonomicky stul SSE system 40": v podstate system 40, jen nohy jsou jeklove nohy SSE s vnitrnim profilem 35x35 pro vyskovou stavitelnost;
# viz api/stul_sse.py). Profil rámu = 40x40 jako v systemu 40, ale kostra je jina (podelniky + nohy SSE, bez sablony), proto vlastni cislo systemu 41. Konstanty z vlastniho tvaru #581 "Noha SSE".
# ---------------------------------------------------------------------------------------------------------------------
SYSTEM_SSE = 41
SYSTEMY_PLOCHA = (30, 35, 40)      # systemy, ktere sdileji "plochy" tvar ulozenych pravidel (jedna sada pro vsechny; stav do 2026-10-05); SSE ma vlastni
SSE_JEKL_PART, SSE_PROFIL_PART, SSE_PLECH_PART, SSE_PATKA_PART = "sse_jekl_40", "sse_profil_35", "sse_plech_150", "sse_patka_35"    # PROCEDURALNI dily (tvar vyrabi stul_glb), bez karty katalogu
SSE_PARTS = (SSE_JEKL_PART, SSE_PROFIL_PART, SSE_PLECH_PART, SSE_PATKA_PART)
SSE_JEKL = 40.0                 # vnejsi rozmer jeklu 40x40 (svisle jekly i spojnice)
SSE_STOJKA = 675.0              # delka svisleho jeklu nohy (#581: 40 x 675 x 40)
SSE_SPOJNICE_MIN, SSE_SPOJNICE_MAX = 400.0, 1100.0       # delka jeklove spojnice nohy (Robert): hloubka stolu = spojnice + 2 x 40 mm
SSE_SPOJNICE_ZVEDNUTI = 90.0    # spodni hrana spojnice nad spodkem jeklu (#581: spojnice y 218,7, jekl od 128,7)
SSE_ODSAZENI = 175.0            # vnejsi lice nohy od konce desky (vzor SSE: 175 mm => u desky 2000 mm je mezera mezi nohami 1570 mm - Robert)
SSE_PLECH_SIRKA, SSE_PLECH_VYSKA, SSE_PLECH_TL = 150.0, 40.0, 6.0     # plechova patka u horniho konce jeklu (#581: 150 x 40 x 6), na ni se sroubuje podelnik
SSE_PROFIL, SSE_PROFIL_DELKA, SSE_PATKA_TL = 35.0, 425.0, 3.0         # vnitrni profil 35x35 delky 425 + zaslepka 3 mm na podlaze (#581)
SSE_PREKRYTI_MIN = 100.0        # PREDPOKLAD: nejmene tolik mm vnitrniho profilu zustava v jeklu (omezuje nejvyssi vysku stolu); vyska 700-1000 mm => prekryti 121-421 mm
SSE_PODELNIK_PRIREZ = 10.0      # podelnik je o 10 mm kratsi nez deska (5 mm z kazde strany pro zaslepky) - Robert
SSE_POLICE_ODSTUP = 20.0        # deska police je o 20 mm mensi nez svetla hloubka mezi jekly (vzor SSE: spojnice 820, police 800)
SSE_POLICE_PRESAH = 7.5         # deska police presahuje vnejsi lice krajnich noh o 7,5 mm na kazde strane (vzor SSE: 1650 + 15 = 1665)
SSE_BOX_OKRAJ = 10.0            # nejmensi vzdalenost boxu od konce podelniku (mm)
SYSTEMY[SYSTEM_SSE] = dict(SYSTEMY[40], system=SYSTEM_SSE, nazev_profilu="profil 40×40", sse=True, deska_zkraceni=0.0, vzpery=False,
                           rozsah={"sirka": (800.0, 3000.0), "hloubka": (SSE_SPOJNICE_MIN + 2 * SSE_JEKL, SSE_SPOJNICE_MAX + 2 * SSE_JEKL), "vyska": (700.0, 1000.0)},        # sirka (= delka desky) max 3000
                           vychozi={"sirka": 2000.0, "hloubka": 900.0, "vyska": 830.0})        # vzor SSE: deska 2000 x 900, mezera mezi nohami 1570 mm, horni plocha ~830 mm
# ---------------------------------------------------------------------------------------------------------------------
# SYSTEM 45 (bot10, 2026-10-07; Robert: "postav generator stolu system 45, profil 1.1.10.040040.03, hloubka stolu az 2500 mm, mozna tam musime lehce zmenit konstrukci" a "kompatibilita
# s predeslymi generatory"): profil, rohove spojky, sablona, konce noh i vsechny ostatni dily jako SYSTEM 40 (SuperLight S10 40x40 = Object_11 = karta 3468 = SKU 1.1.10.040040.03), jen HLOUBKA
# 400-2500 mm. Do hloubky HLOUBKA_STREDNI_NOHA (1500 mm) je stul BIT PO BITU jako system 40 (stejne dily, jen `system` = 45; konfiguraci jde mezi systemy 30 / 35 / 40 / 45 prepinat);
# NAD NI prybyva uprostred hloubky na kazde strane STREDNI NOHA (svisly profil od podlahy az pod nejnizsi bocni pricku, navazuje na svisle profily bocnice) a pod podperami pracovni desky
# i kazde police PRICKA pres sirku mezi obema strednimi nohami - viz blok 2c-45 v `_sestav_jadro_systemu`.
# ---------------------------------------------------------------------------------------------------------------------
SYSTEM_45 = 45
HLOUBKA_STREDNI_NOHA = 1500.0      # system 45: VYCHOZI hloubka (mm), nad kterou pribyva stredni rada noh (viz vyse); skutecna hodnota je pravidlo `hloubka_stredni_noha` (Pravidla stolu, po systemech)
MIN_DELKA_STREDNI_NOHY = 50.0       # system 45: nejkratsi stredni noha (mm; pod nejnizsi bocni pricku): zmereno - od ~42 mm je sestava bez problemu (kratsi: spojka na konci noha se prekryva se zaslepkou), 50 mm = rezerva
SYSTEMY[SYSTEM_45] = dict(SYSTEMY[40], system=SYSTEM_45, hluboky=True, rozsah_navic={"hloubka": (400.0, 2500.0)})
PROFIL_PARTS = tuple(dict.fromkeys(s["profil"] for s in SYSTEMY.values()))           # ("Object_7", "profil_35x35", "Object_11")
SPOJKY_PARTS = tuple(dict.fromkeys(s["spojka"] for s in SYSTEMY.values()))           # rohove spojky vsech systemu (bez opakovani: 3158 je v systemech 30 i 35)
KONCE_PARTS = tuple(dict.fromkeys([s["zaslepka"] for s in SYSTEMY.values()] + [s["patka"] for s in SYSTEMY.values()]))      # zaslepky a patky vsech systemu (bez opakovani)
# NAVLEK NOHOU (viz hlavicka modulu): jen systemy, jejichz profil se vejde do jeklu 40x40x2 (vnitrni 36 mm): 35x35
NAVLEK_SYSTEMY = (35,)
NAVLEK_PART = "jekl_40x40x2"           # jekl 40x40, stena 2 mm; mesh 1000 mm podel lokalni osy Y, vystredeny (jako profil), delku dava meritko y
NAVLEK_ZASLEPKA = "jekl_zaslepka_40"   # zaslepka jeklu 40x40: priruba 3 mm pod jeklem + zatka dovnitr; lokalni +Z = do jeklu (jako zaslepka profilu), vnejsi plocha z = 0 lezi na podlaze
NAVLEK_PARTS = (NAVLEK_PART, NAVLEK_ZASLEPKA)
NAVLEK_JEKL = 40.0                     # vnejsi rozmer jeklu (mm)
NAVLEK_STENA = 2.0                     # stena jeklu (mm): vnitrni rozmer 36 mm
NAVLEK_PRIRUBA = 3.0                   # tloustka prirub zaslepky jeklu (mm): jekl na ni stoji, spodek jeklu je 3 mm nad podlahou
NAVLEK_ZATKA = 12.0                    # delka zatky zaslepky v jeklu (mm)
NAVLEK_ZASUN = 70.0                    # nejmene tolik mm nohy (profilu) musi byt v jeklu (Robert 2026-10-05); stul se kresli s presne tolika = nejvyssi poloha
NAVLEK_MEZERA_NAD = 3.0                # volne misto nad hornim koncem jeklu, nez zacne dalsi komponent (mm; Robert: v urovni navleku zadny jiny komponent; 2026-10-05 po skice: min. 3 mm)
NAVLEK_SRAZENI = 2.0                   # srazeni (45 st., delka kratke strany 2 mm) vnejsich rohu jeklu a prirub zaslepky - stejne jako na jeklu nohy stolu SSE (sse_full.glb: obrys +-20 / +-18)
NAVLEK_BARVA = "RAL 7016"              # barva jeklu navleku: tmava sedocerna (antracit), lesk (Robert 2026-10-05); zaslepka jeklu je cerny plast
NAVLEK_POVRCH = "lak RAL 7016 (tmavá šedočerná), lesk"
NAVLEK_KROK = 10.0                     # delka navleku po 10 mm (posuvnik)
NAVLEK_KG_NA_M = 7850.0 * (NAVLEK_JEKL ** 2 - (NAVLEK_JEKL - 2 * NAVLEK_STENA) ** 2 - 2 * NAVLEK_SRAZENI ** 2) / 1.0e6       # ocel 7850 kg/m3, prurez 296 mm2 (304 minus 4 srazeni 2 x 2 mm) = 2,32 kg/m (tabulkove 2,31)
NAVLEK_ZASLEPKA_KG = 0.012             # plastova zaslepka jeklu (odhad)
_SYSTEM = contextvars.ContextVar("stul_system", default=SYSTEM_VYCHOZI)


def over_system(s):
    """Systemy 30 / 40 jako int; cokoli jineho (vc. bool) = StulChyba."""
    try:
        if isinstance(s, bool):
            raise ValueError
        f = float(s.strip() if isinstance(s, str) else s)
        if f == int(f) and int(f) in SYSTEMY:
            return int(f)
    except (TypeError, ValueError, OverflowError):
        pass
    raise StulChyba(f"system: '{s}' neni jeden z {', '.join(str(k) for k in SYSTEMY)}", "mimo_rozsah")


class _v_systemu:
    """Kontext: do konce bloku plati sablona a konstanty systemu `s` (30 | 40); vnoreni a vlakna jsou bezpecne (contextvars)."""

    def __init__(self, s):
        self.s = over_system(s)
        self.tok = None

    def __enter__(self):
        self.tok = _SYSTEM.set(self.s)
        return SYSTEMY[self.s]

    def __exit__(self, *a):
        _SYSTEM.reset(self.tok)
        return False


def aktivni_system():
    return _SYSTEM.get()


def _sd():
    """Konstanty aktivniho systemu (SYSTEMY[...])."""
    return SYSTEMY[_SYSTEM.get()]


def _P():
    """Sirka profilu aktivniho systemu (mm)."""
    return SYSTEMY[_SYSTEM.get()]["profil_mm"]


def _H():
    """Polovina profilu (mm): vzdalenost lice profilu od jeho osy."""
    return SYSTEMY[_SYSTEM.get()]["profil_mm"] / 2.0


def deska_zadni_pokracovani(sd, stojky):
    """O kolik mm pokracuje pracovni deska za sablonovou zadni hranu (= predni lice zadnich noh; `sd` = SYSTEMY[system]). BEZ zadnich stojek (zadni nohy zkracene na vysku prednich) deska pokracuje
    dozadu a PREKRYVA zadni svisle profily (Robert 2026-10-08: "kdyz se odejmou zadni stojky (zkrati), deska musi pokracovat dozadu prekryt svisle profily"): konci v rovine zadniho lice zadnich noh,
    tedy o tloustku profilu - jako po stranach, kde deska konci v rovine vnejsich lic noh. Se stojkami 0 (zadni nohy stoji ZA deskou). Stul SSE ma vlastni jadro (stul_sse) a deska se mu nemeni."""
    return 0.0 if (stojky or sd.get("sse")) else float(sd["profil_mm"])


def bok_kraceni_desky():
    """O kolik se z kazde strany zkrati deska police pri hloubce nad prahem (svisly profil doprostred bocnice + 1 mm vule)."""
    return _P() + 1.0


def roztec_polic_min():
    """Nejmensi rozteč os ramu polic (mm): mezera + ram police + deska."""
    return MEZERA_POLIC + _P() + DESKA_TLOUSTKA


def odstup_od_nohou():
    """Nejmensi volna vzdalenost komponentu (suplikoveho boxu) od lice nohy (mm) v aktivnim systemu: 30 v systemu 30, 40 v systemu 40 (vetsi rohove spojky)."""
    return SYSTEMY[_SYSTEM.get()]["odstup_od_nohou"]


def min_delka_nohy():
    """Noha kratsi nez 2 sirky profilu uz neni noha (ram + stejne mnoho volne)."""
    return 2.0 * _P()

ROZSAH = {"sirka": (500, 3000), "hloubka": (400, 1500), "vyska": (140, 1200), "presah": (0, 100), "led_rameno": (200, 1500),
          "loz_rozteca": (40, 1000), "loz_okraj": (25, 500), "vzpera_delka": (100, 1000), "stojky_vyska": (200, 1500),
          "navlek_delka": (200, 400)}          # navlek nohou (jekl 40x40x2) v mm - Robert 2026-10-05


def _rozsahy(system):
    """ROZSAH systemu `system`: obecne meze + meze, ktere se v systemu lisi (`rozsah_navic`; system 45: hloubka az 2500 mm)."""
    return {**ROZSAH, **SYSTEMY[system].get("rozsah_navic", {})}


def _rz(klic):
    """Mez `klic` z ROZSAH v AKTIVNIM systemu (kontext `_v_systemu`)."""
    return SYSTEMY[_SYSTEM.get()].get("rozsah_navic", {}).get(klic) or ROZSAH[klic]


SIRKA_STREDNI_NOHY = 1500          # nad touto sirkou (mm) pribyvaji predni a zadni stredni noha
HLOUBKA_STREDNI_PROFIL = 900       # VYCHOZI prah (mm): nad touto hloubkou pribyva profil doprostred kazde bocnice, kratsi deska police a podpery pod policí i pod deskou
# NASTAVITELNA PRAVIDLA (Robert 2026-10-04: "tu hloubku 900 mm chci mit jako nastavitelnou promennou, lze zmenit zadani v textovem poli"): generator je cista funkce, hodnoty drzi
# tenhle slovnik; stul_api.py je pred pozadavkem nacte z app_settings (klic `stul_pravidla`, JSON) a upravuje je pole na strance Generator stolu. Mimo server (testy) platí vychozi.
CENA_VYREZU = 0                    # VYCHOZI cena za jeden vyrez v pracovni desce (Kc bez DPH): Robert ji stanovi primo v generatoru (Pravidla stolu); 0 = vyrez cenu nemeni
VZPERY_OD_RAMENE = 500             # VYCHOZI prah (mm): od teto delky ramene LED od zadnich stojek se samy pridavaji sikme vzpery (Robert 2026-10-04; zapnuti dela stranka/modul, ne generator)
CENA_NAVLEK_200 = 370              # VYCHOZI cena jednoho navleku nohy (jekl 40x40x2 vc. zaslepky; Kc bez DPH) pri delce 200 mm (Robert 2026-10-05); mezi 200 a 400 mm linearne
CENA_NAVLEK_400 = 550              # ... a pri delce 400 mm; staff ji meni v Pravidlech stolu
CENA_NOHA_SSE_400 = 0              # VYCHOZI cena JEDNE nohy SSE (2 jekly, spojnice, 2 plechy, 2 vnitrni profily, zaslepky; Kc bez DPH) pri delce spojnice 400 mm: Robert ji zada v Pravidlech stolu SSE (0 = nezadano)
CENA_NOHA_SSE_1100 = 0             # ... a pri delce spojnice 1100 mm; mezi 400 a 1100 mm linearne
PODPERA_MAX_ROZPON_VYCHOZI = 800.0         # VYCHOZI nejvetsi nepodepreny usek desky (mm) - pravidlo `podpera_max_rozpon` po systemech (konstanta PODPERA_MAX_ROZPON nize = tatez hodnota)
MIN_ODSTUP_STREDNI_NOHY_VYCHOZI = 150.0    # VYCHOZI nejmensi vzdalenost osy stredni nohy od osy krajni nohy (mm) - pravidlo `min_odstup_stredni_noha` po systemech
PRAVIDLA_VYCHOZI = {"hloubka_stredni_profil": float(HLOUBKA_STREDNI_PROFIL), "vzpery_od_ramene": float(VZPERY_OD_RAMENE), "cena_vyrez": float(CENA_VYREZU),
                    "sirka_stredni_noha": float(SIRKA_STREDNI_NOHY), "cena_navlek_200": float(CENA_NAVLEK_200), "cena_navlek_400": float(CENA_NAVLEK_400),
                    "cena_noha_sse_400": float(CENA_NOHA_SSE_400), "cena_noha_sse_1100": float(CENA_NOHA_SSE_1100),
                    "hloubka_stredni_noha": float(HLOUBKA_STREDNI_NOHA),          # system 45 (hluboky stul): hloubka, nad kterou pribyva stredni rada noh (u ostatnich systemu bez vlivu, nezobrazuje se)
                    "podpera_max_rozpon": PODPERA_MAX_ROZPON_VYCHOZI, "min_odstup_stredni_noha": MIN_ODSTUP_STREDNI_NOHY_VYCHOZI}
PRAVIDLA_ROZSAH = {"hloubka_stredni_profil": (400.0, 1600.0), "vzpery_od_ramene": (200.0, 1500.0), "cena_vyrez": (0.0, 100000.0), "sirka_stredni_noha": (500.0, 3000.0),
                   "cena_navlek_200": (0.0, 100000.0), "cena_navlek_400": (0.0, 100000.0), "cena_noha_sse_400": (0.0, 100000.0), "cena_noha_sse_1100": (0.0, 100000.0),
                   "hloubka_stredni_noha": (400.0, 2500.0),          # 2500 = nejvetsi hloubka systemu 45 = stredni rada se nikdy nepridava
                   "podpera_max_rozpon": (200.0, 3000.0), "min_odstup_stredni_noha": (50.0, 1000.0)}      # sirka: 3000 = nejvetsi stul, nikdy     # 400 = nejmensi hloubka stolu; >= 1500 (nejvetsi hloubka) = podpery a bocni profil nikdy
# PRAVIDLA PO SYSTEMECH (Robert 2026-10-05: "konkretni hodnoty chci mit nastavitelne pro jednotlive systemy zvlast, 30/35/40, kazdemu zadam individualne"): kazdy system (profil 30 / 35 / 40) ma
# VLASTNI sadu pravidel (`PRAVIDLA_SYSTEMU[system]`), vychozi hodnoty jsou stejne. `PRAVIDLA` je POHLED na sadu AKTIVNIHO systemu (kontext `_v_systemu`, tedy uvnitr generatoru ta, ktera patri
# stolu, ktery se sklada) - kod, ktery pravidla cetl jako jeden slovnik (`PRAVIDLA["x"]`, `.get`, `.items()`, `==`), funguje beze zmeny; mimo kontext systemu (API, mini-shop) se systém predava
# vyslovne: `pravidlo(klic, system)`, `prah_sirky(system)`, `prah_hloubky(system)`, `pravidla_systemu(system)`.
PRAVIDLA_VYCHOZI_SYSTEMU = {SYSTEM_SSE: {"sirka_stredni_noha": 2000.0}}      # vychozi hodnoty, ktere se v systemu LISI od PRAVIDLA_VYCHOZI: SSE ma do 2000 mm jen dve nohy (vzor SSE: deska 2000 mm, mezera mezi nohami 1570 mm)


def pravidla_vychozi(system=None):
    """Vychozi sada pravidel systemu `system` (None = aktivni): PRAVIDLA_VYCHOZI + vychozi hodnoty, ktere se v systemu lisi."""
    s_ = _SYSTEM.get() if system is None else over_system(system)
    return {**PRAVIDLA_VYCHOZI, **PRAVIDLA_VYCHOZI_SYSTEMU.get(s_, {})}


PRAVIDLA_SYSTEMU = {s_: pravidla_vychozi(s_) for s_ in SYSTEMY}


class _PravidlaAktivnihoSystemu(collections.abc.MutableMapping):
    """Slovnikovy pohled na `PRAVIDLA_SYSTEMU[aktivni system]` (cteni i zapis)."""

    def _d(self):
        return PRAVIDLA_SYSTEMU[_SYSTEM.get()]

    def __getitem__(self, k):
        return self._d()[k]

    def __setitem__(self, k, v):
        self._d()[k] = v

    def __delitem__(self, k):
        del self._d()[k]

    def __iter__(self):
        return iter(self._d())

    def __len__(self):
        return len(self._d())

    def __repr__(self):
        return repr(self._d())


PRAVIDLA = _PravidlaAktivnihoSystemu()


# FORMAT TABULE laminovane dreveny (Robert 2026-10-05: "formaty tabuli lamino desky jako jedno kriterium"): deska stolu (pracovni i police) se musi vejit do tabule (kratsi x delsi strana, mm).
# Vychozi 2070 x 2800 (DTDL; karty deskovych materialu maji pole board_sheet_width_mm / board_sheet_height_mm - u karty 4933 zatim prazdne: stul_api ho nacte, jakmile bude vyplnene).
# Generator je cista funkce, format drzi tenhle seznam; mimo server (testy) plati vychozi.
TABULE_VYCHOZI = (2070.0, 2800.0)
_TABULE = list(TABULE_VYCHOZI)


def nastav_tabuli(kratsi=None, delsi=None):
    """Nastavi format tabule laminodesky (mm). Neplatne / chybejici hodnoty (None, <= 0, mimo 300-6000 mm) = vychozi 2070 x 2800. Vola jen vrstva API (nacteni z karty 4933). Vraci (kratsi, delsi)."""
    try:
        a, b = sorted((float(kratsi), float(delsi)))
        if not (300.0 <= a and b <= 6000.0) or a != a or b != b:
            raise ValueError
    except (TypeError, ValueError):
        a, b = TABULE_VYCHOZI
    _TABULE[:] = [a, b]
    return tuple(_TABULE)


def tabule():
    """Aktualni format tabule laminodesky (kratsi, delsi strana; mm)."""
    return tuple(_TABULE)


def max_delka_desky():
    """Nejdelsi mozna deska stolu (mm) = delsi strana tabule."""
    return max(_TABULE)


TOLERANCE_TABULE = 0.1             # mm: sablona stolu ma desku o ~0,005 mm mimo osu (stred nohou), na mezi polohy opory by deska "pretekla" o setiny mm; rezna tolerance laminodesky je radu desetin mm


def deska_se_vejde_do_tabule(rozmer_a, rozmer_b):
    """Vejde se deska rozmeru a x b (mm) do tabule (v obou orientacich; tolerance TOLERANCE_TABULE)?"""
    kr, dl = _TABULE
    mn, mx = sorted((float(rozmer_a), float(rozmer_b)))
    return mn <= kr + TOLERANCE_TABULE and mx <= dl + TOLERANCE_TABULE


def stredni_noha_meze(sirka, system=None):
    """(nejmene, nejvic) mm od osy leve krajni nohy k ose stredni nohy / ramu: aspon MIN_ODSTUP_STREDNI_NOHY od kazde krajni nohy a OBE casti pracovni desky (deli se u stredni opory) se musi
    vejit do tabule laminodesky (leva cast = poloha + pul profilu, prava cast = rozpeti - poloha + pul profilu)."""
    with _v_systemu(VYCHOZI["system"] if system is None else system):
        pr = _P()
    rozpeti, pul, delka = float(sirka) - pr, pr / 2.0, max_delka_desky()
    mo = min_odstup_stredni_noha(_SYSTEM.get() if system is None else system)              # pravidlo systemu: bez `system` aktivni system (uvnitr generatoru ten, ktery se sklada); vychozi 150
    return max(mo, rozpeti + pul - delka), min(rozpeti - mo, delka - pul)


def pravidlo(klic, system=None):
    """Hodnota pravidla stolu `klic` v systemu `system` (None = aktivni system, tj. ten, ktery se prave sklada)."""
    return PRAVIDLA_SYSTEMU[_SYSTEM.get() if system is None else over_system(system)][klic]


def system_z_dilu(dily):
    """System profilu (30 / 35 / 40) sestavy podle jejich dilu (profil Object_7 / profil_35x35 / Object_11); nic z toho = aktivni system. Cena (stul_api) podle toho bere pravidla spravneho systemu."""
    pids = {d["part_id"] for d in dily}
    if pids & set(SSE_PARTS):
        return SYSTEM_SSE                                           # stul SSE ma podelniky z profilu 40 (Object_11) jako system 40, ale nohy SSE jsou jen v nem
    for s_, c_ in SYSTEMY.items():
        if s_ != SYSTEM_SSE and c_["profil"] in pids:
            return s_
    return _SYSTEM.get()


def pravidla_systemu(system=None):
    """Kopie sady pravidel systemu `system` (None = aktivni system)."""
    return dict(PRAVIDLA_SYSTEMU[_SYSTEM.get() if system is None else over_system(system)])


def prah_sirky(system=None):
    """Aktualni prah (mm) v systemu `system` (None = aktivni): nad touto sirkou stolu pribyva STREDNI OPORA (predni a zadni stredni noha, nebo vestaveny ram) a desky se deli (Robert 2026-10-04: nastavitelne v Pravidlech stolu;
    vychozi 1500). Nejvyse delka tabule laminodesky (2800): sirsi pracovni deska by se do tabule nevesla, takze stredni opora (a deleni desky) je od ni povinne bez ohledu na pravidlo."""
    return min(float(pravidlo("sirka_stredni_noha", system)), max_delka_desky())


def prah_hloubky(system=None):
    """Aktualni prah (mm) v systemu `system` (None = aktivni): nad touto hloubkou stolu pribyvaji svisly profil bocnic, kratsi deska police a podpery pod policí i pod pracovni deskou."""
    return float(pravidlo("hloubka_stredni_profil", system))


def prah_hloubky_noha(system=None):
    """Aktualni prah (mm) v systemu `system` (None = aktivni; jen systemy `hluboky`, tj. 45): nad touto hloubkou stolu pribyva uprostred hloubky na kazde strane STREDNI NOHA a pod podperami desky i polic
    PRICKA pres sirku (Robert 2026-10-07: kazdy system ma vlastni limitni rozmery pro stredni nohu; vychozi 1500). Plati nejvys od hloubky, nad kterou pribyvaji svisle profily bocnic (`prah_hloubky`)."""
    return float(pravidlo("hloubka_stredni_noha", system))


def podpera_max_rozpon(system=None):
    """Aktualni nejvetsi nepodepreny usek desky (mm) v systemu `system` (None = aktivni): pocet podper pod policí i pod pracovni deskou = ceil(rozpon / tato hodnota) - 1 (vychozi 800)."""
    return float(pravidlo("podpera_max_rozpon", system))


def min_odstup_stredni_noha(system=None):
    """Aktualni nejmensi vzdalenost (mm) osy stredni nohy od osy krajni nohy v systemu `system` (None = aktivni; vychozi 150): limit polohy stredni nohy / ramu."""
    return float(pravidlo("min_odstup_stredni_noha", system))


def _over_pravidla(nova, system=None):
    """Sada pravidel z `nova` (slovnik klic -> cislo; chybejici klic = vychozi hodnota SYSTEMU `system`, None = obecna): neznamy klic nebo hodnota mimo rozsah = ValueError."""
    out = dict(PRAVIDLA_VYCHOZI) if system is None else pravidla_vychozi(system)
    for k, v in (nova or {}).items():
        if k not in PRAVIDLA_ROZSAH:
            raise ValueError(f"neznamy klic pravidla: {k}")
        try:
            f = float(v)
        except (TypeError, ValueError):
            raise ValueError(f"{k}: '{v}' neni cislo")
        lo, hi = PRAVIDLA_ROZSAH[k]
        if not (lo <= f <= hi) or f != f:
            raise ValueError(f"{k}: {v} je mimo rozsah {lo:g}-{hi:g}")
        out[k] = float(round(f))
    return out


def nastav_pravidla(nova, system=None):
    """Nastavi pravidla (slovnik klic -> cislo) systemu `system` (30 / 35 / 40), BEZ `system` VSEM systemum (jako dosud, kdyz byla jedna sada pro vsechny); neznamy klic nebo hodnota mimo rozsah =
    ValueError (nic se nezmeni). Vraci pravidla nastaveneho systemu (bez `system` aktivniho). Volat jen z vrstvy API (nacteni z DB)."""
    cile = list(SYSTEMY) if system is None else [over_system(system)]
    sady = {s_: _over_pravidla(nova, s_) for s_ in cile}                         # chybejici klic = vychozi hodnota KAZDEHO systemu (SSE ma jinou vychozi sirku pro stredni nohu)
    for s_ in cile:
        PRAVIDLA_SYSTEMU[s_] = dict(sady[s_])                                    # NAHRADA slovniku (atomicka), ne clear + update: souběžné vlákno nikdy neuvidí poloprázdnou sadu
    return dict(PRAVIDLA_SYSTEMU[_SYSTEM.get() if system is None else cile[0]])


def nastav_pravidla_po_systemech(nova):
    """Nastavi pravidla vsech systemu najednou: `nova` = {system: {klic: cislo}}; system, ktery v `nova` chybi, dostane vychozi hodnoty. Nejdriv se overi VSE, az potom zapise (pri chybe
    ValueError / StulChyba se nezmeni nic)."""
    overeno = {}
    for s_, sada in (nova or {}).items():
        try:
            overeno[over_system(s_)] = _over_pravidla(sada, over_system(s_))
        except StulChyba as e:
            raise ValueError(str(e))
    for s_ in SYSTEMY:
        PRAVIDLA_SYSTEMU[s_] = dict(overeno.get(s_, pravidla_vychozi(s_)))         # nahrada slovniku (atomicka), viz nastav_pravidla
    return {s_: dict(PRAVIDLA_SYSTEMU[s_]) for s_ in SYSTEMY}
BOK_KRACENI_DESKY = 31.0           # Robert 2026-10-03: pri hloubce nad 900 mm (svisly profil doprostred bocnic) se deska spodni police zkrati po SIRCE z kazde strany o 31 mm (30 mm profil + 1 mm vule)
PODPERA_MAX_ROZPON = PODPERA_MAX_ROZPON_VYCHOZI   # (VYCHOZI hodnota pravidla `podpera_max_rozpon`; skutecna je pravidlo systemu) PREDPOKLAD (Robert upresni): nejvetsi nepodepreny usek desky police mezi bocnim ramem / stredni nohou a podpernym profilem (mm); pocet podper = ceil(rozpon / 800) - 1 na rozpon
MIN_ODSTUP_STREDNI_NOHY = MIN_ODSTUP_STREDNI_NOHY_VYCHOZI    # (VYCHOZI hodnota pravidla `min_odstup_stredni_noha`; skutecna je pravidlo systemu) nejmensi vzdalenost osy stredni nohy od osy krajni nohy (mm) - ZATIM PREDPOKLAD
MAX_POLIC = 10                     # nejvyssi zadatelny pocet polic (skutecny strop dava vyska: min. 100 mm volne mezi policemi)
MEZERA_POLIC = 100.0               # volne misto mezi policemi (mm): od horni plochy desky police po spodek ramu dalsi police (Robert)
ROZTEC_POLIC_MIN = MEZERA_POLIC + 48.0   # + rám police 30 mm + deska 18 mm = nejmensi rozteč os ramů polic
ODSTUP_KOMPONENTU_OD_NOHOU = 30.0  # komponent mezi nohama (suplikovy box) ma mit od nohou aspon 30 mm z kazde strany (Robert)
ODSTUP_PRI_TAZENI = 10.0           # tazeni stredni nohy mysi se zastavi 10 mm pred kolizi (Robert)
MAX_DELKA_PROFILU = 3000.0         # api/app.py PROFILE_MAX_LENGTH_MM
MIN_DELKA_NOHY = 60.0              # system 30: noha kratsi nez 2 sirky profilu uz neni noha (rám 30 mm + 30 mm volne) - ZATIM PREDPOKLAD (obecne 2 x profil, viz min_delka_nohy())
MIN_DELKA_PROFILU = 30.0           # nejkratsi vyrobitelny kus profilu (mm) v obou systemech; kratsi profil (vcetne svislych useku bocnice mezi ramy) je problem `kratky_profil`
PANEL_SIRKA = 1190.0               # product_4931 (z GLB)
PANEL_PART = "product_4931"
# DELKY PANELU: delka (mm) -> dil katalogu (karty #4972-4974 zalozil scripts/2026-10-07_perfopanel/zaloz_karty.py; GLB maji STEJNOU souradnicovou soustavu jako 4931: X = delka, Y = tloustka, Z = vyska).
# Sirka / vyska / tloustka panelu se berou z GLB (AABB), takze v kodu zadny rozmer panelu neni; vsechny panely stolu jsou stejne delky (`panely_delka`).
PANEL_TYPY = {1190: PANEL_PART, 1481: "product_4972", 1671: "product_4973", 1975: "product_4974"}
PANEL_DELKY = tuple(sorted(PANEL_TYPY))
PANEL_DELKA_VYCHOZI = 1190
PANEL_PARTY = frozenset(PANEL_TYPY.values())
PANEL_MEZERA = 1.0                 # Robert 2026-10-05: mezera mezi panelem a profily nad/pod nim i po stranach u stojek (mm)
PANEL_ODSTUP_OD_PRICKY = 2.0       # spodni profil panelu leziny v nejnizsi poloze 2 mm nad zadni prickou ramu desky: dotek profilu na profil (<= 1,5 mm) by se pocital jako spoj (110 Kc) - nejsou spojene
PANELY_MAX_RAD = 2                 # nejvic radu panelu nad sebou (vyska mezi rovinou desky a ramenem LED: 2 x 460 + 3 profily)
PANELY_MAX = 4                     # nejvyssi zadatelny pocet panelu (2 vedle sebe x 2 rady)
STREDNI_OPORY = ("auto", "noha", "ram")
RAM_ZAPNUT = True                  # vestaveny ram misto stredni nohy (Robert 2026-10-05)
RAM_VULE_VYREZU = 1.0              # vule mezi svislym profilem rámu a hranou desky police (mm z kazde strany): obe casti spodni police u vestaveneho ramu jsou kratsi o profil + 2 x tato vule (dritve vyrez 32 x 32 mm v jedne desce)
LED_SIRKA = 1247.0                 # product_4929 vc. koncovek (z GLB); dalsi LED vedle sebe naraz
LED_PREVIS = 47.0                  # LED je v sablone o 47 mm delsi nez stul (1247 vs 1200)
MIN_PODIL_PROFILU_LED = 0.9        # podelny profil nad LED je dany mezerou mezi nohami, ale nejkratsi mozny = 90 % delky svetla (Robert; svetla budou i v jinych delkach)
# DELKY LED (Robert 2026-10-07: "LED 600 doplnit do generatoru"): nominalni delka svitidla (mm) -> dil katalogu (karta #5359 LED600: GLB = LED 1200 zkracena o 600 mm, STEJNA lokalni souradnicova soustava
# a STEJNY stred bboxu jako product_4929, X = delka; sablonovy clen LED se klonuje se stejnou polohou / otocenim, jen s jinym dilem). Delka TELESA vc. koncovek se bere z GLB (`led_telo_dilu`: 1247 / 647 mm);
# vsechna svitidla stolu jsou stejne dlouha (`led_delka`, vychozi 1200 = beze zmeny stavajicich konfiguraci i hashu).
LED_PART = "product_4929"
LED_TYPY = {1200: LED_PART, 600: "product_5359"}
LED_DELKY = tuple(sorted(LED_TYPY))
LED_DELKA_VYCHOZI = 1200
LED_PARTY = frozenset(LED_TYPY.values())
LED_MAX = 4                         # nejvic svitidel LED na stole (nejsirsi stul 3000 mm: 4 x 600 mm); od 2026-10-08 je POCET svitidel RUCNI volba (`led_pocet`, vychozi 1), polohu kazdeho urcuje `led_z1..led_z<LED_MAX>`
LED_PARAMETRY_Z = tuple(f"led_z{_k}" for _k in range(1, LED_MAX + 1))

# ložiskové (kuličkové) jednotky na pracovní desce (Robert 2026-10-02): karta 3025 "Kuličková jednotka 15mm - 20kg" (Kola Pirkl), uživatel zadá
# rozteč a vzdálenost od okraje desky -> mřížka jednotek; jednotky v místě otvoru (výřezu) nebo kolidující s jiným dílem se vynechají
LOZ_PART = "product_3025"
LOZ_PRUMER = 34.0                  # příruba jednotky (mm) - ODHAD podle fotky karty, ověřit u dodavatele
LOZ_VYSKA = 9.0                    # výška nad deskou (příruba 3 mm + kulička 6 mm) - ODHAD
MAX_LOZ = 500                      # nejvyšší počet jednotek (výkon GLB/ceny); víc = problém "loz_moc"
LOZ_MEZERA_OTVOR = 2.0             # jednotka musí být aspoň 2 mm od okraje otvoru (jinak se vynechá)
MAX_VYREZU = 3                     # nejvyssi pocet vyrezu v pracovni desce (Robert: vyrezy libovolne velikosti na libovolnem miste)
VYREZ_OKRAJ = 30.0                 # nejmensi vzdalenost otvoru od okraje desky (mm); mensi pruh by se ulomil
VYREZ_MIN = 50.0                   # nejmensi rozmer otvoru (mm)
# konce noh bez koleček (Robert 2026-10-02): noha MUSÍ mít záslepku (Dogus 3071 "Záslepka 30x30") nebo stavitelnou patku (Dogus 3251 "Vyrovnávací
# šroubovací patka M8"). Záslepka: příruba 3 mm pod koncem nohy, zátka 6 mm uvnitř profilu. Patka: závit zasunutý PATKA_ZASUN mm do nohy (odhad -
# nastavitelné), viditelných PATKA_DELKA - PATKA_ZASUN mm.
ZASLEPKA, ZASLEPKA_VYSKA = "product_3071", 3.0
PATKA, PATKA_DELKA, PATKA_ZASUN = "product_3251", 75.0, 30.0
VYREZ_POLICE_PRESAH = 40.0         # police pod otvorem je o 40 mm na kazdou stranu vetsi nez otvor (Robert)
VYREZ_POLICE_MEZERA = 100.0        # mezera mezi horni plochou police a spodkem desky stolu (Robert)
VYREZ_MEZERA = 30.0                # nejmensi pruh desky mezi dvema otvory (mm)
VYREZ_VYCHOZI = {"w": 200.0, "d": 150.0, "x": 100.0}      # w = rozmer po sirce (Z), d = po hloubce (X), x = vzdalenost od PREDNI hrany desky; z viz nize
# sikme vzpery 45 st. pod rameny LED (Robert 2026-10-03: "podepreni rampy pro LED jako doplnujici stabilizace na zatizeni"): vzpera = profil 30x30 delky `vzpera_delka`
# (DELKU URCUJE DELKA PROFILU) + Sikma spojka 3254 (SKU 2.2.001.08.3030.06, "Spojka uhel 45 st. system 30") na OBOU koncich zrcadlove. Vzpera lezi v pravem uhlu mezi
# prednim licem zadni stojky a spodkem ramene LED; sikma plocha kazde spojky lezi presne na stene stojky / ramene (osy profilu svíraji 45 st.).
VZPERA_SPOJKA = "product_3254"
VZPERA_F_OSA = 24.53               # plosny stred sikme plochy spojky 3254 podel osy spojky od celniho ctverce (nativni Y; z skutecne site GLB, plocha 646 mm2)
VZPERA_F_BOK = -1.75               # jeho boční odsazeni od stredu celniho ctverce (nativni X: stred ctverce -15, plosny stred plochy -16.75)
VZPERA_CELO_STRED = 15.0           # pivot spojky je v ROHU celniho ctverce: stred ctverce 30x30 je o 15 mm vedle pocatku (nativni x = -15)
VZPERA_STEN = (VZPERA_F_OSA + VZPERA_F_BOK) * math.sqrt(0.5)   # kolmy odstup stredu konce profilu od steny stojky/ramene (~16.1 mm; osa 45 st. => slozky 24.53 a -1.75 do kolme roviny)
VZPERA_TOL_PLNY = 0.4              # nejvic mm, o kolik smi plocha spojky zasahnout do PLNEHO materialu stojky/ramene (sikma plocha site spojky je o 0.77 st. vychylena od 45 st.)
VZPERA_REZERVA_RAMENE = 0.0        # spojka u ramene musi cela lezet pod ramenem (jeji AABB nesmi presahnout predni konec ramene)
# SYSTEM 40 (bot10, 2026-10-04; Robert: "je ve scene ve vlastnich tvarech" = tvar #178 "Sikma spojka 40 na profilu 40": profil Object_11 delky 1000 s dvema spojkami 3220 na koncich): spojka 3220
# ma pocatek (nativni 0, 0, 0) ve STREDU celniho ctverce 40x40 (nativni x, z od -20 do 20), nativni Y = osa ven z konce profilu, sikma plocha ma normalu (0, +cos45, +sin45) => bocni osa
# `lat` je nativni +Z (u 3254 nativni +X), plocha lezi v rovine y + z = 31,96 (kolmy odstup od pocatku 22,627 mm; plocha 842 mm2, plosny stred y 35,385 / z -3,385). Tvar #178 ukazuje pivot
# spojky na ose profilu (boční odsazeni 0) a 0,1656 mm za koncem profilu (v ose ven) => kolmy odstup STREDU KONCE profilu od steny = 22,627 + 0,1656 * cos45 = 22,744 mm.
VZPERA_STEN_40_PLOCHA = 22.627     # kolmy odstup sikme plochy spojky 3220 od jejiho pocatku (z meshe product_3220.glb: rovina y + z = 31,96 v nativnich souradnicich)
VZPERA_ODSTUP_CELO_40 = 0.1656     # o kolik je pocatek 3220 za koncem profilu v ose ven (z vlastniho tvaru #178)
SYSTEMY[30].update(vzpera_spojka=VZPERA_SPOJKA, vzpera_sten=VZPERA_STEN, vzpera_celo_lat=VZPERA_CELO_STRED, vzpera_celo_osa=0.0, vzpera_lat_nativni="x", vzpera_sku="2.2.001.08.3030.06")
SYSTEMY[40].update(vzpera_spojka="product_3220", vzpera_sten=VZPERA_STEN_40_PLOCHA + VZPERA_ODSTUP_CELO_40 * math.sqrt(0.5), vzpera_celo_lat=0.0, vzpera_celo_osa=VZPERA_ODSTUP_CELO_40,
                   vzpera_lat_nativni="z", vzpera_sku="2.2.006.4040.08")
SYSTEMY[35].update(vzpera_spojka=VZPERA_SPOJKA, vzpera_sten=VZPERA_STEN, vzpera_celo_lat=VZPERA_CELO_STRED, vzpera_celo_osa=0.0, vzpera_lat_nativni="x", vzpera_sku="2.2.001.08.3030.06")      # spojka 3254 ze systemu 30
SYSTEMY[SYSTEM_SSE].update({k: v for k, v in SYSTEMY[40].items() if k.startswith("vzpera")})          # SSE nema vzpery (vzpery=False), ale klice musi existovat
SYSTEMY[SYSTEM_45].update({k: v for k, v in SYSTEMY[40].items() if k.startswith("vzpera")})          # system 45 = stejne vzpery jako 40
VZPERY_SPOJKY = tuple(dict.fromkeys(s["vzpera_spojka"] for s in SYSTEMY.values()))          # sikme spojky vsech systemu (bez opakovani)
VYREZY_PREP = tuple(f"vyrez{n}" for n in range(1, MAX_VYREZU + 1)) + tuple(f"vyrez{n}_police" for n in range(1, MAX_VYREZU + 1))
VYREZY_CISLA = tuple(f"vyrez{n}_{s}" for n in range(1, MAX_VYREZU + 1) for s in ("w", "d", "x", "z"))


def _vyrezy_vychozi():
    out = {}
    for n in range(1, MAX_VYREZU + 1):
        out[f"vyrez{n}"] = False
        out[f"vyrez{n}_w"] = VYREZ_VYCHOZI["w"]
        out[f"vyrez{n}_d"] = VYREZ_VYCHOZI["d"]
        out[f"vyrez{n}_x"] = VYREZ_VYCHOZI["x"]
        out[f"vyrez{n}_z"] = 100.0 + (n - 1) * 260.0          # dalsi vyrez vedle predchoziho (z = vzdalenost od LEVE hrany desky)
        out[f"vyrez{n}_police"] = False                      # police pod otvorem (o 40 mm vetsi na kazdou stranu, 100 mm pod deskou)
    return out


# OCELOVE SUPLIKY (box pod pracovni deskou) - POCET supliku 1 / 2 / 3 = tri karty katalogu (Robert 2026-10-05, vnejsi vysky od dodavatele 180 / 280 / 450 mm, sirka 565 a hloubka 583 mm stejne;
# SKU Suplik.ocel.440136 (#4956, 3 900 Kc), Dvojsuplik.ocel.440137 (#4930, 5 800 Kc), Trojsuplik.ocel.440138 (#4957, 5 900 Kc), ceny bez DPH). Box visi VRCHEM na pricich pod deskou, dil ma ve vsech
# trech modelech stejnou polohu a lisi se jen tim, jak hluboko pod pricky sahá (modely: scripts/2026-10-05_suplik_varianty_final.py).
SUPLIK_PARTY = {1: "product_4956", 2: "product_4930", 3: "product_4957"}
SUPLIK_PARTY_VSE = tuple(SUPLIK_PARTY.values())
SUPLIK_POCTY = tuple(SUPLIK_PARTY)
SUPLIK_POCET_VYCHOZI = 2


VYCHOZI = {
    "system": SYSTEM_VYCHOZI,     # Robert 2026-10-04: 30 = profil 30x30 (Object_7), 40 = SuperLight S10 40x40 (Object_11); viz SYSTEMY
    "sirka": 1280, "hloubka": 800, "vyska": 840,         # sirka 1280 (Robert 2026-10-05): vychozi stul ma 1 panel mezi zadnimi stojkami = nejmene 1190 + 2 + 2 x profil (1252 / 1272)
    "presah": 30,                 # presah pracovni desky pres CELNI profil (mm, 0-100; v sablone #577 = 30)
    "led_rameno": 560,            # delka ramene (profilu) drzici LED od zadnich stojek smerem k telu stolu (mm, 200-1500; sablona 560)
    "stojky": True,               # zadni stojky = zadni nohy prodlouzene nahoru (nesou panely, LED); vypnuto = zadni nohy jako predni
    "stojky_vyska": 1073.0,       # Robert 2026-10-05: VYSKA zadnich stojek nad rovinou pracovni desky (mm; 1073 = sablona #577); stojku lze zkracovat i natahovat, s ni jede rameno LED
    "police": 1,                  # POCET spodnich polic (0 = zadna; vice ks rovnomerne po vysce, min. 100 mm volne mezi nimi)
    "police_deska": True,         # Robert 2026-10-07: spodni police MAJI DESKU (laminodeska na rame); False = police BEZ DESKY, jen ram z profilu (odpadne deska, jeji deleni u opory a podpery pod ni);
                                  # plati pro vsechny spodni police (police pod vyrezem ma vlastni prepinac), bez spodnich polic a v systemu SSE nic nedela
    "kolecka": True, "panely": True, "led": True,
    "panely_pocet": 1,            # Robert 2026-10-05: POCET panelu po jednom kuse (vychozi stul ma 1); vedle sebe, kde to sirka dovoli (mezi nimi plna noha), jinak dalsi rada nad
    "panely_posun": 0.0,          # panel(y) s profily nad a pod nimi se daji posouvat po zadnich stojkach (mm nahoru od spodni polohy: spodni profil lezi na zadni pricce ramu desky)
    "panely_z": 0.0,              # Robert 2026-10-05: panely jsou VODOROVNE pohyblive, maji-li mezi nohama mezeru (mm od stredu useku mezi stojkami, kladne = doprava; spolecne pro vsechny panely, kazdy zustane aspon PANEL_MEZERA od noh)
    "panely_delka": float(PANEL_DELKA_VYCHOZI),   # Robert 2026-10-07: delka perforovanych panelu (1190 | 1481 | 1671 | 1975 mm; viz PANEL_TYPY); vsechny panely stolu jsou stejne; co se nevejde, se snizi na nejdelsi, ktera ano
    "stredni_opora": "auto",      # stredni opora u sirokeho stolu: "noha" (stredni nohy), "ram" (vestaveny ram mezi 4 podelniky - podelniky zustanou cele), "auto" (noha; ram jen kdyz se panel jinak nevejde)
    "elzlab_y": 0.0, "elzlab_z": 0.0,    # elektrozlab se dotyka panelu nebo profilu a je pohybliv svisle (y) i do stran (z); mm od vychozi polohy
    "patky": False,               # stavitelne patky misto zaslepek na koncich noh (jen u stolu BEZ koleček; Dogus)
    "navlek": False,              # Robert 2026-10-05 (jen system 35): navlek z jeklu 40x40x2 na spodku KAZDE nohy MISTO koleček / zaslepek / patek (mechanicka vyska); zapnuty navlek kolecka a patky vypne
    "navlek_delka": 300.0,        # delka navleku (mm, 200-400); na stole dane vysky se orizne na nejvetsi mozne (navlek_meze)
    "suplik": True, "elektrozlab": True, "drzak_pet": True,
    "suplik_posun": 0.0,          # mm podel sirky od vychozi polohy suplikoveho boxu (kladne = k vnejsi noze na zvolene strane; vpravo = doprava)
    "suplik_pocet": SUPLIK_POCET_VYCHOZI,   # Robert 2026-10-05: POCET supliku v boxu 1 / 2 / 3 (vnejsi vyska 180 / 280 / 450 mm; jiny dil katalogu - viz SUPLIK_PARTY); jen kdyz je box zapnuty
    "led_svetlo": True,           # Robert 2026-10-04: samotne SVITIDLO LED lze odebrat, profily (ramena + pricny profil) zustanou; relevantni jen kdyz led a stojky
    "led_delka": float(LED_DELKA_VYCHOZI),    # Robert 2026-10-07: delka svitidel LED (1200 | 600 mm; viz LED_TYPY); vsechna svitidla stolu jsou stejna; relevantni jen kdyz led, stojky a svitidlo
    "led_pocet": 1,               # Robert 2026-10-08: POCET svitidel LED RUCNE (1..LED_MAX; drive automaticky podle sirky stolu); relevantni jen kdyz led, stojky a svitidlo
    **{f"led_z{_k}": None for _k in range(1, LED_MAX + 1)},   # poloha STREDU _k-teho svitidla v mm od OSY STOLU (kladne = doprava); None = automaticka (svitidla tesne vedle sebe, skupina vystredena jako dosud)
    "suplik_vlevo": False,        # Robert 2026-10-04: suplikovy box na LEVE strane stolu (zrcadlova poloha vuci vychozi pravé); suplik_posun se pak meri od leve nohy
    **{f"police_h{k}": None for k in range(1, 11)},     # Robert 2026-10-04: VYSKA POLIC (cisluje se SHORA): police_h1 = odstup horni plochy desky 1. police pod spodni hranou podelniku pracovni plochy (mm),
                                  # police_h<k> (k >= 2) = mezera mezi policemi (mm; od horni plochy desky k-te police po spodek ramu predchozi). None = automaticky (rovnomerne rozlozeni)
    "pet_noha": "PL",             # Robert 2026-10-04: na KTERE svisle noze drzak PET visi: PL/PP = predni leva/prava, ZL/ZP = zadni leva/prava (stojka), FM/RM = predni/zadni stredni (jen kdyz jsou)
    "pet_strana": "vpravo",       # ... a na KTERE strane profilu: vpravo (+z, vychozi = sablona), vlevo (-z), vpredu (-x), vzadu (+x)
    "pet_posun": 0.0,             # Robert 2026-10-04: drzak PET lahve se da posunout po noze SVISLE (mm, kladne = nahoru); meze viz pet_meze
    "stredni_noha": None,         # mm od osy leve nohy k ose stredni nohy (None = uprostred); jen pri sirce > 1500
    "loz": False,                 # ložiskové jednotky na pracovní desce; loz_rozteca = rozteč středů (mm), loz_okraj = vzdálenost od okraje desky (mm)
    "loz_rozteca": 200, "loz_okraj": 100,
    "vzpery": False,              # sikme vzpery 45 st. pod rameny LED (jen se zadnimi stojkami a LED); vzpera_delka = delka PROFILU vzpery (mm, 100-1000 po 10; horni mez dava rameno LED/stojka - viz vzpera_meze)
    "vzpera_delka": 300,
    # HORNI POLICE MEZI ZADNIMI STOJKAMI (Robert 2026-10-07; api/stul_hpolice.py): vychozi = BEZ police (hashe, kody a ceny stavajicich stolu beze zmeny)
    "hpolice": False, "hpolice_typ": "rovna", "hpolice_deska": "lam18", "hpolice_vyska": None, "hpolice_hloubka": 300.0, "hpolice_sklon": 15.0,
    **_vyrezy_vychozi(),          # vyrez1..3 (zapnuto) + _w, _d (rozmer), _x (od predni hrany), _z (od leve hrany desky) v mm
}
PREPINACE = ("stojky", "kolecka", "panely", "led", "suplik", "elektrozlab", "drzak_pet", "patky", "navlek", "hpolice")

TOL_PRUNIK_MM = 1.0       # AABB pruniky mene nez 1 mm jsou dotyk (desky lezi na rame, panel u nohy...)
TOL_SPOJ_MM = 1.5         # stejna tolerance jako dimension_match_fbx.EPS_FACE_MM
TOL_PREKRYV_MM = 0.5      # stejna tolerance jako dimension_match_fbx.EPS_OVERLAP_MM

# Index dilu sablony (= poradi v custom_shapes #577).
DESKA_PRAC, DESKA_POLICE = 0, 1
ZRAIL_PRAC_ZAD, NOHA_PL, NOHA_PP, NOHA_ZL, NOHA_ZP, ZRAIL_PRAC_PRED = 2, 3, 4, 12, 13, 5
XRAIL_BOX1, XRAIL_BOX2, XRAIL_PRAC_L, XRAIL_PRAC_P = 6, 11, 10, 8
XRAIL_POL_L, XRAIL_POL_P, ZRAIL_POL_ZAD, ZRAIL_POL_PRED = 9, 7, 18, 19
ZRAIL_PANEL = 14
XRAIL_TOP_P, XRAIL_TOP_L, ZRAIL_TOP = 15, 16, 17
BOX, LED, ELZLAB, PANEL_D, PANEL_H, PET = 20, 21, 22, 23, 24, 25
KOLECKA = (26, 27, 28, 29)
SPOJKY = tuple(range(30, 50))
PROFILY = tuple(range(2, 20))
DESKY = (DESKA_PRAC, DESKA_POLICE)


def _f(d=0.0, w=0.0, h=0.0):
    """Linearni forma (kD, kW, kH): o kolik se hodnota zmeni na 1 mm zmeny hloubky/sirky/vysky oproti sablone."""
    return (d, w, h)


# Pravidla posunu STREDU dilu (sx, sy, sz) a zmeny DELKY profilu (ln). Kotvy: x = predni (0) / zadni noha (D),
# z = leva noha (0) / prava noha (W) / stred (W/2), y = podlaha (0) / rovina desky (H).
R = {
    ZRAIL_PRAC_PRED: dict(sx=_f(), sy=_f(h=1), sz=_f(w=.5), ln=_f(w=1)),
    ZRAIL_PRAC_ZAD: dict(sx=_f(d=1), sy=_f(h=1), sz=_f(w=.5), ln=_f(w=1)),
    XRAIL_PRAC_L: dict(sx=_f(d=.5), sy=_f(h=1), sz=_f(), ln=_f(d=1)),
    XRAIL_PRAC_P: dict(sx=_f(d=.5), sy=_f(h=1), sz=_f(w=1), ln=_f(d=1)),
    XRAIL_BOX1: dict(sx=_f(d=.5), sy=_f(h=1), sz=_f(w=1), ln=_f(d=1)),      # + suplik_posun
    XRAIL_BOX2: dict(sx=_f(d=.5), sy=_f(h=1), sz=_f(w=1), ln=_f(d=1)),
    XRAIL_POL_L: dict(sx=_f(d=.5), sy=_f(), sz=_f(), ln=_f(d=1)),
    XRAIL_POL_P: dict(sx=_f(d=.5), sy=_f(), sz=_f(w=1), ln=_f(d=1)),
    ZRAIL_POL_PRED: dict(sx=_f(), sy=_f(), sz=_f(w=.5), ln=_f(w=1)),
    ZRAIL_POL_ZAD: dict(sx=_f(d=1), sy=_f(), sz=_f(w=.5), ln=_f(w=1)),
    ZRAIL_PANEL: dict(sx=_f(d=1), sy=_f(h=1), sz=_f(w=.5), ln=_f(w=1)),
    XRAIL_TOP_L: dict(sx=_f(d=1), sy=_f(h=1), sz=_f(), ln=_f()),            # hloubka horniho ramu zvlast
    XRAIL_TOP_P: dict(sx=_f(d=1), sy=_f(h=1), sz=_f(w=1), ln=_f()),
    ZRAIL_TOP: dict(sx=_f(d=1), sy=_f(h=1), sz=_f(w=.5), ln=_f(w=1)),
    NOHA_PL: dict(sx=_f(), sz=_f()),                  # svisla poloha a delka nohou zvlast (kolecka, nastavba)
    NOHA_PP: dict(sx=_f(), sz=_f(w=1)),
    NOHA_ZL: dict(sx=_f(d=1), sz=_f()),
    NOHA_ZP: dict(sx=_f(d=1), sz=_f(w=1)),
    DESKA_PRAC: dict(sx=_f(d=.5), sy=_f(h=1), sz=_f(w=.5)),
    DESKA_POLICE: dict(sx=_f(d=.5), sy=_f(), sz=_f(w=.5)),
    BOX: dict(sx=_f(), sy=_f(h=1), sz=_f(w=1)),                              # + suplik_posun
    LED: dict(sx=_f(d=1), sy=_f(h=1), sz=_f(w=.5)),                          # skupina LED je vycentrovana
    ELZLAB: dict(sx=_f(d=1), sy=_f(h=1), sz=_f()),
    PANEL_D: dict(sx=_f(d=1), sy=_f(h=1), sz=_f(w=.5)),                      # skupina panelu je vycentrovana
    PANEL_H: dict(sx=_f(d=1), sy=_f(h=1), sz=_f(w=.5)),
    PET: dict(sx=_f(), sy=_f(h=1), sz=_f()),
    26: dict(sx=_f(d=1), sy=_f(), sz=_f()),       # kolecko u leve zadni nohy
    27: dict(sx=_f(), sy=_f(), sz=_f(w=1)),       # u prave predni
    28: dict(sx=_f(d=1), sy=_f(), sz=_f(w=1)),    # u prave zadni
    29: dict(sx=_f(), sy=_f(), sz=_f()),          # u leve predni
}


class StulChyba(ValueError):
    """Neplatny vstup (mimo rozsah, neznamy parametr). `kod` je strojovy kod."""

    def __init__(self, zprava, kod="neplatny_vstup"):
        super().__init__(zprava)
        self.kod = kod


# ---------------------------------------------------------------------------------------------------------------------
# pomocne funkce
# ---------------------------------------------------------------------------------------------------------------------
_SABLONY = {}              # system -> dily sablony (nacitaji se z JSON jednou)
_BBOX_CACHE = {}
BBOX_PREPIS = {}          # jen pro testy: {"product_4930": (lo, hi)} - jina lokalni bbox nez v souboru GLB


def sablona():
    """Dily zmrazene sablony AKTIVNIHO systemu."""
    s = _SYSTEM.get()
    if s not in _SABLONY:
        with open(SYSTEMY[s]["sablona"], encoding="utf-8") as f:
            _SABLONY[s] = json.load(f)["parts"]
    return _SABLONY[s]


def _glb_json(path):
    with open(path, "rb") as f:
        buf = f.read()
    off = 12
    while off < len(buf):
        ln, typ = struct.unpack("<II", buf[off:off + 8])
        if typ == 0x4E4F534A:
            return json.loads(buf[off + 8:off + 8 + ln].decode("utf-8"))
        off += 8 + ln
    raise StulChyba(f"{path}: chybi JSON chunk", "glb")


PROCEDURALNI_BBOX = {LOZ_PART: ([-LOZ_PRUMER / 2.0, 0.0, -LOZ_PRUMER / 2.0], [LOZ_PRUMER / 2.0, LOZ_VYSKA, LOZ_PRUMER / 2.0]),   # tvar vyrabi stul_glb.nacti_mesh
                     NAVLEK_PART: ([-NAVLEK_JEKL / 2.0, -500.0, -NAVLEK_JEKL / 2.0], [NAVLEK_JEKL / 2.0, 500.0, NAVLEK_JEKL / 2.0]),            # jekl 40x40, 1000 mm vystredeny podel Y (delku dava meritko y)
                     NAVLEK_ZASLEPKA: ([-NAVLEK_JEKL / 2.0, -NAVLEK_JEKL / 2.0, 0.0], [NAVLEK_JEKL / 2.0, NAVLEK_JEKL / 2.0, NAVLEK_PRIRUBA + NAVLEK_ZATKA]),   # priruba z 0..3, zatka z 3..15 (+Z = do jeklu)
                     # SSE (system 41): jekl 40x40 (stejny tvar jako navlek, 1000 mm vystredeny podel Y), vnitrni profil 35x35 (1000 mm podel Y), plechova patka 150x40x6, zaslepka vnitrniho profilu 35x35x3
                     SSE_JEKL_PART: ([-SSE_JEKL / 2.0, -500.0, -SSE_JEKL / 2.0], [SSE_JEKL / 2.0, 500.0, SSE_JEKL / 2.0]),
                     SSE_PROFIL_PART: ([-SSE_PROFIL / 2.0, -500.0, -SSE_PROFIL / 2.0], [SSE_PROFIL / 2.0, 500.0, SSE_PROFIL / 2.0]),
                     SSE_PLECH_PART: ([-SSE_PLECH_SIRKA / 2.0, -SSE_PLECH_VYSKA / 2.0, -SSE_PLECH_TL / 2.0], [SSE_PLECH_SIRKA / 2.0, SSE_PLECH_VYSKA / 2.0, SSE_PLECH_TL / 2.0]),
                     SSE_PATKA_PART: ([-SSE_PROFIL / 2.0, -SSE_PATKA_TL / 2.0, -SSE_PROFIL / 2.0], [SSE_PROFIL / 2.0, SSE_PATKA_TL / 2.0, SSE_PROFIL / 2.0])}


def glb_bbox(part_id):
    """Lokalni bbox GLB dilu (z accessor.min/max POSITION vsech meshu): (lo, hi) jako numpy pole."""
    if part_id in BBOX_PREPIS:
        lo, hi = BBOX_PREPIS[part_id]
        return np.array(lo, float), np.array(hi, float)
    if part_id in PROCEDURALNI_BBOX:
        lo, hi = PROCEDURALNI_BBOX[part_id]
        return np.array(lo, float), np.array(hi, float)
    if part_id in _BBOX_CACHE:
        return _BBOX_CACHE[part_id]
    if part_id in ZAVRENY_BBOX:
        pr = _bbox_ze_souboru(part_id)
        if pr[1][1] - pr[0][1] > 1000.0:          # v katalogu je model s vysunutym supliku -> pro konfigurator zavreny
            _BBOX_CACHE[part_id] = (np.array(ZAVRENY_BBOX[part_id][0], float), np.array(ZAVRENY_BBOX[part_id][1], float))
            return _BBOX_CACHE[part_id]
    pr = _bbox_ze_souboru(part_id)
    _BBOX_CACHE[part_id] = pr
    return pr


# `product_4930` (ocelove supliky) ma v katalogu jeden suplik VYSUNUTY (~50 cm pred skrin). Pro konfigurator se pocita se zavrenym
# (api/stul_glb.py ho pri skladani modelu zavre; katalogovy soubor se nemeni). Pokud se katalogovy soubor nahradi zavrenym, tohle
# se samo vypne (podminka: delka v lokalni ose Y > 1000 mm = vysunuty suplik).
ZAVRENY_BBOX = {"product_4930": ([-2279.2, -950.4, 627.4], [-1714.2, -367.3, 907.5])}


# GLB dilu, jejichz soubor se nejmenuje `<part_id>.glb` (karta ma jiny `glb_file`): horni police pouziva desky MDF 8 mm (#3939), PR10 (#3539) a Uhelnikovou spojku 30x30 (#3045)
GLB_SOUBORY = {"product_3939": "deska_mdf_seda_8.glb", "product_3539": "pr10.glb", "product_3045": "product_2895.glb"}


def glb_cesta(part_id):
    """Cesta k souboru GLB dilu v katalogu (vetsinou `<part_id>.glb`, vyjimky viz GLB_SOUBORY)."""
    return os.path.join(KATALOG_DIR, GLB_SOUBORY.get(part_id, part_id + ".glb"))


def _bbox_ze_souboru(part_id):
    path = glb_cesta(part_id)
    if not os.path.isfile(path):
        raise StulChyba(f"chybi GLB dilu {part_id} ({path})", "glb")
    js = _glb_json(path)
    lo = np.full(3, np.inf)
    hi = np.full(3, -np.inf)
    for m in js.get("meshes", []):
        for p in m.get("primitives", []):
            a = js["accessors"][p["attributes"]["POSITION"]]
            lo = np.minimum(lo, a["min"])
            hi = np.maximum(hi, a["max"])
    return lo, hi


_LED_TELO = {}


def _led_delka_int(delka):
    """Delka svitidla LED jako cele cislo z LED_TYPY (jinak StulChyba)."""
    d = int(round(float(delka)))
    if d not in LED_TYPY:
        raise StulChyba(f"led_delka: {delka!r} neni jedna z delek LED svitidla {', '.join(str(x) for x in LED_DELKY)} mm", "mimo_rozsah")
    return d


def _led_telo_presne(part_id):
    """Delka tělesa svitidla (mm) z GLB (accessor min/max): osa delky = lokalni X (sablonovy clen LED ji otaci do sirky stolu)."""
    lo, hi = glb_bbox(part_id)
    return float(hi[0] - lo[0])


def led_telo_dilu(part_id):
    """Delka TELESA svitidla vc. koncovek (mm, zaokrouhleno na cele mm jako LED_SIRKA = 1247 u product_4929) podle GLB dilu; vychozi svitidlo vraci konstantu LED_SIRKA (hodnota se nesmi zmenit).
    Chybi-li GLB dilu, vyhodi StulChyba (volitelna delka se pak nenabizi, vychozi cesta nespadne)."""
    if part_id == LED_PART:
        return LED_SIRKA
    v = _LED_TELO.get(part_id)
    if v is None:
        v = _LED_TELO[part_id] = float(round(_led_telo_presne(part_id)))
    return v


def led_max_pocet(sirka, telo):
    """Nejvic svitidel, ktera se na stul vejdou: soucet delek teles <= sirka stolu + LED_PREVIS (pravidlo jako dosud: max(1, floor((sirka + LED_PREVIS) / telo))), nejvic LED_MAX."""
    return max(1, min(LED_MAX, int((sirka + LED_PREVIS) // telo)))


def led_polohy(n, telo, c0, p0, p1, zadane, rozpeti_max):
    """Efektivni polohy STREDU teles `n` svitidel (absolutni z, zleva doprava), jejich AUTOMATICKE polohy a meze stredu jednoho svitidla.
    Automaticka poloha = svitidla tesne vedle sebe, skupina vystredena kolem `c0` (stred JEDNOHO svitidla ve vychozi / sablonove poloze: u 1 svitidla beze zmeny proti dosavadnimu stavu).
    `zadane` = n hodnot (absolutni z stredu, nebo None = automaticka poloha). Pravidla: poradi se nemeni (index = poradi zleva doprava), svitidla se neprekryvaji (nejmene tesne vedle sebe; kdo by se
    prekryl, je odsunut), aspon 90 % delky kazdeho svitidla lezi nad pricnym profilem <p0, p1> (MIN_PODIL_PROFILU_LED) a rozpeti cele skupiny nepresahne `rozpeti_max` (sirka stolu + LED_PREVIS,
    stejne pravidlo jako kontrola `mimo_obrys`). Vraci (polohy, automaticke, (nejmensi stred, nejvetsi stred))."""
    s_ = float(telo)
    q = MIN_PODIL_PROFILU_LED * s_
    cmin, cmax = p0 + q - s_ / 2.0, p1 - q + s_ / 2.0
    auto = [c0 + (k - (n - 1) / 2.0) * s_ for k in range(n)]
    v, zbyva = [], max(0.0, rozpeti_max - n * s_)
    for k in range(n):
        chce = zadane[k] if zadane[k] is not None else auto[k]
        lo = cmin if k == 0 else v[k - 1] + s_
        hi = cmax - (n - 1 - k) * s_
        if k:
            hi = min(hi, v[k - 1] + s_ + zbyva)
        x = min(max(chce, lo), hi) if lo <= hi else lo
        if k:
            zbyva -= x - v[k - 1] - s_
        v.append(x)
    return v, auto, (cmin, cmax)


def led_meze(v, telo, p0, p1, rozpeti_max):
    """Meze stredu kazdeho svitidla (absolutni z) pri dane poloze ostatnich: [(nejmene, nejvic), ...]. Sousedi se nesmi prekryt, aspon 90 % delky nad profilem, rozpeti skupiny <= `rozpeti_max`."""
    s_ = float(telo)
    q = MIN_PODIL_PROFILU_LED * s_
    cmin, cmax = p0 + q - s_ / 2.0, p1 - q + s_ / 2.0
    n = len(v)
    out = []
    for k in range(n):
        lo = cmin if k == 0 else v[k - 1] + s_
        hi = cmax if k == n - 1 else v[k + 1] - s_
        if n > 1 and k == 0:
            lo = max(lo, v[-1] + s_ - rozpeti_max)
        if n > 1 and k == n - 1:
            hi = min(hi, v[0] - s_ + rozpeti_max)
        out.append((lo, hi))
    return out


def _led_param_patch(pol, aut, zc):
    """Parametry generatoru pro svitidla v polohach `pol` (absolutni z stredu): `led_pocet` a `led_z1..`; poloha shodna s automatickou (`aut`) = None; zbyle az do LED_MAX = None."""
    out = {"led_pocet": len(pol)}
    for k in range(LED_MAX):
        out[f"led_z{k + 1}"] = (None if abs(pol[k] - aut[k]) < 0.05 else round(pol[k] - zc, 1)) if k < len(pol) else None
    return out


def led_pridat(st):
    """Parametry po PRIDANI dalsiho svitidla (nebo None, kdyz se uz zadne nevejde): nove svitidlo tesne vpravo od posledniho, jinak tesne vlevo od prvniho, jinak do mezery mezi dvema (kde je misto),
    a kdyz se nevejde ani tak (ostatni by se musela posunout), vsechna svitidla znovu tesne vedle sebe a vystredena (automaticke polohy); polohy ostatnich svitidel zustavaji, kdyz to jde."""
    n = st["n"]
    if n >= st["n_max"]:
        return None
    s_, v = st["telo"], list(st["v"])
    kandidati = [v + [v[-1] + s_], [v[0] - s_] + v]
    for k in range(n - 1):
        if v[k + 1] - v[k] >= 2 * s_ - 1e-9:
            kandidati.append(v[:k + 1] + [v[k] + s_] + v[k + 1:])
    for c in kandidati:
        pol, aut, _m = led_polohy(n + 1, s_, st["c0"], st["z_lo"], st["z_hi"], c, st["rozpeti"])
        if all(abs(pol[i] - c[i]) < 0.05 for i in range(n + 1)):
            return _led_param_patch(pol, aut, st["zc"])
    pol, aut, _m = led_polohy(n + 1, s_, st["c0"], st["z_lo"], st["z_hi"], [None] * (n + 1), st["rozpeti"])
    return _led_param_patch(pol, aut, st["zc"])


def led_odebrat(st, k):
    """Parametry po ODEBRANI svitidla cislo `k` (0 = nejlevejsi): ostatni zustanou na svych mistech (polohy se zapisou vyslovne, pokud nejsou shodne s automatickymi pro mensi pocet)."""
    v = [x for i, x in enumerate(st["v"]) if i != k]
    n = len(v)
    aut = [st["c0"] + (j - (n - 1) / 2.0) * st["telo"] for j in range(n)]
    return _led_param_patch(v, aut, st["zc"])


def kvat_na_matici(q):
    x, y, z, w = q
    return np.array([
        [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
        [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
        [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)],
    ], float)


def _otoc_spojku(odsazeni, q, osa, stupne):
    """Otoci spojku (jeji odsazeni od uzlu a kvaternion) o `stupne` (nasobek 90) kolem osy 'x' | 'y' | 'z' prochazejici uzlem: tentyz spoj ve ctyrech rozich (horni police)."""
    t = math.radians(stupne)
    c, sn = round(math.cos(t), 12), round(math.sin(t), 12)
    R = {"x": [[1, 0, 0], [0, c, -sn], [0, sn, c]], "y": [[c, 0, sn], [0, 1, 0], [-sn, 0, c]], "z": [[c, -sn, 0], [sn, c, 0], [0, 0, 1]]}[osa]
    qr = tuple(math.sin(t / 2.0) if i == "xyz".index(osa) else 0.0 for i in range(3)) + (math.cos(t / 2.0),)
    return np.round(np.array(R, float) @ np.asarray(odsazeni, float), 9), _kvat_nasob(qr, q)


def _kvat_nasob(a, b):
    """Soucin kvaternionu a*b ((x,y,z,w) - nejdriv b, pak a)."""
    ax, ay, az, aw = a
    bx, by, bz, bw = b
    return (aw * bx + ax * bw + ay * bz - az * by,
            aw * by - ax * bz + ay * bw + az * bx,
            aw * bz + ax * by - ay * bx + az * bw,
            aw * bw - ax * bx - ay * by - az * bz)


def _osa(q):
    """(index osy 0/1/2, smer +-1) dlouhe osy profilu (lokalni Y) ve svete."""
    d = kvat_na_matici(q) @ np.array([0.0, 1.0, 0.0])
    k = int(np.argmax(np.abs(d)))
    return k, (1.0 if d[k] > 0 else -1.0)


def _lin(forma, dD, dW, dH):
    return forma[0] * dD + forma[1] * dW + forma[2] * dH


def _norm_parametry(p):
    """Doplni vychozi hodnoty, zkontroluje typy a rozsahy. Vraci novy dict (nemeni vstup)."""
    cizi = sorted(set(p) - set(VYCHOZI))
    if cizi:
        raise StulChyba(f"neznamy parametr: {', '.join(cizi)}", "neznamy_parametr")
    out = dict(VYCHOZI)
    sys_ = over_system(p.get("system", VYCHOZI["system"]))              # vychozi system = VYCHOZI["system"] (30; testy ho prepnou na 40, aby cele sady bezely nad druhym systemem)
    for n in range(1, MAX_VYREZU + 1):
        out[f"vyrez{n}_x"] = SYSTEMY[sys_]["vyrez_x"]                   # vychozi poloha vyrezu od predni hrany desky podle systemu (explicitni hodnota ve vstupu ji prepise)
    out.update(SYSTEMY[sys_].get("vychozi", {}))                         # vychozi hodnoty SYSTEMU, ktere se lisi od VYCHOZI (SSE: deska 2000 x 900, vyska 830)
    out.update(p)
    out["system"] = sys_
    for k, (lo, hi) in _rozsahy(sys_).items():
        v = out[k]
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
            raise StulChyba(f"{k}: neni cislo", "mimo_rozsah")
        if not lo <= v <= hi:
            raise StulChyba(f"{k} {v} mm je mimo rozsah {lo}-{hi} mm", "mimo_rozsah")
        out[k] = float(v)
    for k in PREPINACE:
        out[k] = bool(out[k])
    if out["navlek"] and sys_ in NAVLEK_SYSTEMY:                       # navlek nahrazuje kolecka, zaslepky i patky (Robert 2026-10-05)
        out["kolecka"] = False
        out["patky"] = False
    out["loz"] = bool(out["loz"])
    out["vzpery"] = bool(out["vzpery"])
    out["suplik_vlevo"] = bool(out["suplik_vlevo"])
    out["led_svetlo"] = bool(out["led_svetlo"])
    ld_ = out["led_delka"]
    if isinstance(ld_, bool) or not isinstance(ld_, (int, float)) or not math.isfinite(ld_) or abs(ld_ - round(ld_)) > 1e-6 or int(round(ld_)) not in LED_TYPY:
        raise StulChyba(f"led_delka: {ld_!r} neni jedna z delek LED svitidla {', '.join(str(d_) for d_ in LED_DELKY)} mm", "mimo_rozsah")
    out["led_delka"] = float(int(round(ld_)))
    lp_ = out["led_pocet"]
    if isinstance(lp_, bool) or not isinstance(lp_, (int, float)) or not math.isfinite(lp_) or lp_ != int(lp_):
        raise StulChyba(f"led_pocet: pocet svitidel musi byt cele cislo, je {lp_!r}", "mimo_rozsah")
    if not 1 <= int(lp_) <= LED_MAX:
        raise StulChyba(f"led_pocet: pocet svitidel {int(lp_)} je mimo rozsah 1-{LED_MAX}", "mimo_rozsah")
    out["led_pocet"] = int(lp_)
    for k_ in LED_PARAMETRY_Z:
        v_ = out[k_]
        if v_ is None:
            continue
        if isinstance(v_, bool) or not isinstance(v_, (int, float)) or not math.isfinite(v_):
            raise StulChyba(f"{k_}: poloha svitidla neni cislo", "mimo_rozsah")
        out[k_] = round(float(v_), 1)
    pp = out["panely_pocet"]
    if isinstance(pp, bool) or not isinstance(pp, (int, float)) or not math.isfinite(pp) or pp != int(pp):
        raise StulChyba("panely_pocet: pocet musi byt cele cislo", "mimo_rozsah")
    if not 0 <= pp <= PANELY_MAX:
        raise StulChyba(f"panely_pocet: pocet {int(pp)} je mimo rozsah 0-{PANELY_MAX}", "mimo_rozsah")
    out["panely_pocet"] = int(pp)
    if out["panely_pocet"] == 0:
        out["panely"] = False                                           # 0 panelu = panely vypnute
    pd_ = out["panely_delka"]
    if isinstance(pd_, bool) or not isinstance(pd_, (int, float)) or not math.isfinite(pd_) or abs(pd_ - round(pd_)) > 1e-6 or int(round(pd_)) not in PANEL_TYPY:
        raise StulChyba(f"panely_delka: {pd_!r} neni jedna z delek panelu {', '.join(str(d_) for d_ in PANEL_DELKY)} mm", "mimo_rozsah")
    out["panely_delka"] = float(int(round(pd_)))
    if out["stredni_opora"] not in STREDNI_OPORY:
        raise StulChyba(f"stredni_opora: '{out['stredni_opora']}' neni jedna z {', '.join(STREDNI_OPORY)}", "mimo_rozsah")
    if out["pet_noha"] not in PET_NOHY:
        raise StulChyba(f"pet_noha: '{out['pet_noha']}' neni jedna z {', '.join(PET_NOHY)}", "mimo_rozsah")
    if out["pet_strana"] not in PET_STRANY:
        raise StulChyba(f"pet_strana: '{out['pet_strana']}' neni jedna z {', '.join(PET_STRANY)}", "mimo_rozsah")
    pol = out["police"]
    if isinstance(pol, bool):
        pol = int(pol)
    if not isinstance(pol, (int, float)) or not math.isfinite(pol) or pol != int(pol):
        raise StulChyba("police: pocet musi byt cele cislo", "mimo_rozsah")
    if not 0 <= pol <= MAX_POLIC:
        raise StulChyba(f"police: pocet {pol} je mimo rozsah 0-{MAX_POLIC}", "mimo_rozsah")
    out["police"] = int(pol)
    out["police_deska"] = bool(out["police_deska"])
    sp = out["suplik_pocet"]
    if isinstance(sp, bool) or not isinstance(sp, (int, float)) or not math.isfinite(sp) or sp != int(sp):
        raise StulChyba("suplik_pocet: pocet musi byt cele cislo", "mimo_rozsah")
    if int(sp) not in SUPLIK_PARTY:
        raise StulChyba(f"suplik_pocet: pocet {int(sp)} je mimo rozsah {SUPLIK_POCTY[0]}-{SUPLIK_POCTY[-1]}", "mimo_rozsah")
    out["suplik_pocet"] = int(sp)
    for k in ("suplik_posun", "stredni_noha", "pet_posun", "panely_posun", "panely_z", "elzlab_y", "elzlab_z") + tuple(f"police_h{j}" for j in range(1, 11)):
        v = out[k]
        if v is None and (k == "stredni_noha" or k.startswith("police_h")):
            continue
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
            raise StulChyba(f"{k}: neni cislo", "mimo_rozsah")
        out[k] = float(v)
    # vyrezy v pracovni desce: zapnuto + rozmery; mimo desku se otvor zmensi/posune (deska se pri zmene stolu nemuze zmensit pod otvor)
    sirka_desky = out["sirka"]
    hloubka_desky = (out["hloubka"] + out["presah"] - 30.0 - SYSTEMY[out["system"]]["deska_zkraceni"]          # 30 = vychozi presah
                     + deska_zadni_pokracovani(SYSTEMY[out["system"]], out["stojky"]))                            # bez zadnich stojek deska pokracuje dozadu pres zadni nohy
    for n in range(1, MAX_VYREZU + 1):
        out[f"vyrez{n}"] = bool(out[f"vyrez{n}"])
        out[f"vyrez{n}_police"] = bool(out[f"vyrez{n}_police"])
        for sfx in ("w", "d", "x", "z"):
            v = out[f"vyrez{n}_{sfx}"]
            if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
                raise StulChyba(f"vyrez{n}_{sfx}: neni cislo", "mimo_rozsah")
            out[f"vyrez{n}_{sfx}"] = float(v)
        w = min(max(out[f"vyrez{n}_w"], VYREZ_MIN), sirka_desky - 2 * VYREZ_OKRAJ)
        d = min(max(out[f"vyrez{n}_d"], VYREZ_MIN), hloubka_desky - 2 * VYREZ_OKRAJ)
        out[f"vyrez{n}_w"], out[f"vyrez{n}_d"] = round(w, 1), round(d, 1)
        out[f"vyrez{n}_x"] = round(min(max(out[f"vyrez{n}_x"], VYREZ_OKRAJ), hloubka_desky - VYREZ_OKRAJ - d), 1)
        out[f"vyrez{n}_z"] = round(min(max(out[f"vyrez{n}_z"], VYREZ_OKRAJ), sirka_desky - VYREZ_OKRAJ - w), 1)
    if sys_ == SYSTEM_SSE:
        out = _sse().over_parametry(out, p)                          # SSE: zuzene rozsahy, nepodporovane volby vypnute (explicitni zapnuti = StulChyba)
    else:
        out = _hpol().over_parametry(out, sys_)                      # horni police mezi zadnimi stojkami (Robert 2026-10-07): typ, deska, vyska, hloubka; vypnuta = kanonicka podoba
    return out


def _clen(part_id, q, scale, pos, druh, src=None, delka=None):
    return {"part_id": part_id, "quaternion": tuple(q), "scale": list(scale), "pos": np.array(pos, float),
            "druh": druh, "src": src}


def _klon(sab, i, pos, delka=None):
    """Novy clen se stejnym dilem/otocenim jako sablonovy dil i; pro profil lze zadat delku (mm)."""
    c = sab[i]
    scale = list(c["scale"])
    if delka is not None:
        scale[1] = delka / 1000.0
    druh = "profil" if c["part_id"] in PROFIL_PARTS else ("deska" if i in DESKY else "prisl")
    return _clen(c["part_id"], c["quaternion"], scale, pos, druh, src=i)


# ---------------------------------------------------------------------------------------------------------------------
# generator
# ---------------------------------------------------------------------------------------------------------------------
def _aktivni(p):
    """Indexy dilu sablony, ktere v dane konfiguraci existuji (spojky se vyradi podle profilu)."""
    a = set(range(50))
    postranni_spodni = (not p["police"]) and p["hloubka"] > prah_hloubky()
    if not p["police"]:
        a -= {DESKA_POLICE, ZRAIL_POL_ZAD, ZRAIL_POL_PRED}
        if not postranni_spodni:      # pod 900 mm hloubky odpadaji i spodni podelne pricky bocnic
            a -= {XRAIL_POL_L, XRAIL_POL_P}
    if not p.get("police_deska", True):
        a -= {DESKA_POLICE}                                           # Robert 2026-10-07: spodni police BEZ DESKY (jen ram z profilu): deska police, jeji deleni u opory a podpery pod ni odpadaji; spojky se vynechavaji
                                                                      # podle skutecnych dilu, takze se vrati rohove spojky, ktere dosud vynechala deska
    if not p["kolecka"]:
        a -= set(KOLECKA)
    a -= {PANEL_D, PANEL_H, ZRAIL_PANEL}                              # panely a jejich profily se stavi procedurne (panely vsazene do profilu mezi zadni stojky); sablonove dily a spojky 42, 45 se nepouzivaji
    if not p["led"] or not p["stojky"]:
        a -= {LED, XRAIL_TOP_L, XRAIL_TOP_P, ZRAIL_TOP}
    elif not p["led_svetlo"]:
        a -= {LED}                                                    # jen svitidlo, ramena a pricny profil zustavaji (Robert 2026-10-04)
    if not p["suplik"]:
        a -= {BOX, XRAIL_BOX1, XRAIL_BOX2}
    if not (p["elektrozlab"] and p["panely"] and p["stojky"]):         # elektrozlab se montuje na perforovany panel (na zadnich stojkach)
        a -= {ELZLAB}
    if not p["drzak_pet"]:
        a -= {PET}
    return a


def _usek(clenove, i, souradnice):
    """Klic clenu pro sablonovy profil i: je-li rozdeleny (stredni noha), tak usek, v jehoz rozsahu lezi `souradnice`
    (po ose profilu); jinak puvodni clen."""
    kandidati = [k for k in (("t", i), ("seg", i)) if k in clenove]
    if len(kandidati) == 1:
        return kandidati[0]
    best, best_d = None, None
    for k in kandidati:
        c = clenove[k]
        osa, _ = _osa(c["quaternion"])
        pul = 1000.0 * c["scale"][1] / 2.0
        d = max(c["pos"][osa] - pul - souradnice, souradnice - (c["pos"][osa] + pul), 0.0)
        if best_d is None or d < best_d:
            best, best_d = k, d
    return best


def _zanori_do_desky(clenove, part_id, q, scale, pos):
    """Zanorila by se spojka (dil `part_id` s otocenim q, meritkem scale na pozici pos) do nejake desky? Robert: rohove prvky
    se nedavaji vsude - nekde jsou nutne, nekde by kolidovaly s deskou; takova spojka se vynecha."""
    bb_sp = _aabb({"part_id": part_id, "quaternion": q, "scale": scale, "position": pos})
    for cd in clenove.values():
        if cd["druh"] != "deska" and cd["part_id"] not in PANEL_PARTY:     # deska, ale i perforovany panel (spojka, ktera by se do nej zanorila, se vynecha)
            continue
        lo_d, hi_d = _aabb({"part_id": cd["part_id"], "quaternion": cd["quaternion"], "scale": cd["scale"], "position": cd["pos"]})
        pres = np.minimum(bb_sp[1], hi_d) - np.maximum(bb_sp[0], lo_d)
        if np.all(pres > 0) and float(pres.min()) > TOL_PRUNIK_MM:
            return True
    return False


def _rozloz_desku(X0, X1, Z0, Z1, otvory):
    """Pracovni deska (obdelnik X0..X1 x Z0..Z1) bez otvoru (x0, x1, z0, z1) jako SOUBOR OBDELNIKU (bez booleovskych operaci): deska se
    rozreze v ose X na pasy mezi hranami otvoru a v kazdem pasu se vynecha pruh Z patrici otvorum; sousedni pasy se stejnymi kusy se slouci."""
    xs = sorted({X0, X1} | {o[0] for o in otvory} | {o[1] for o in otvory})
    pasy = []
    for xa, xb in zip(xs, xs[1:]):
        if xb - xa < 0.05:
            continue
        v_pasu = sorted((o[2], o[3]) for o in otvory if o[0] < xb - 1e-6 and o[1] > xa + 1e-6)
        sl = []
        for a, b in v_pasu:
            if sl and a <= sl[-1][1] + 1e-6:
                sl[-1][1] = max(sl[-1][1], b)
            else:
                sl.append([a, b])
        kusy, z = [], Z0
        for a, b in sl:
            if a - z > 0.05:
                kusy.append((z, a))
            z = max(z, b)
        if Z1 - z > 0.05:
            kusy.append((z, Z1))
        pasy.append((xa, xb, tuple(kusy)))
    sloucene = []
    for xa, xb, kusy in pasy:
        if sloucene and sloucene[-1][2] == kusy:
            sloucene[-1] = (sloucene[-1][0], xb, kusy)
        else:
            sloucene.append((xa, xb, kusy))
    return [(xa, xb, za, zb) for xa, xb, kusy in sloucene for za, zb in kusy]


def _loz_mrizka(X0, X1, Z0, Z1, okraj, rozteca):
    """Polohy stredu ložiskových jednotek na desce X0..X1 x Z0..Z1: pasmo ohranicene okrajem (okraj od vsech hran), v kazde ose jednotky po
    roztec, mrizka vycentrovana v pasmu (zbytek se rozdeli rovnomerne na oba konce). Vraci (seznam (x, z), pocet v ose X, pocet v ose Z)."""
    def osa(a, b):
        delka = (b - okraj) - (a + okraj)
        if delka < -1e-6:
            return []
        n = int((delka + 0.05) // rozteca) + 1                 # 0,05 mm tolerance (zaokrouhleni poloh desky)
        zbytek = max(0.0, delka - (n - 1) * rozteca)
        start = a + okraj + zbytek / 2.0
        return [start + i * rozteca for i in range(n)]
    xs, zs = osa(X0, X1), osa(Z0, Z1)
    return [(x, z) for x in xs for z in zs], len(xs), len(zs)


def _vlastnici_spojky(sab, c):
    return [i for i in PROFILY if c in (sab[i].get("lic_peers") or [])]


def _uzel(stredy, a, b, osa_a, osa_b):
    """Uzel spoje = pruseciky os: souradnice po ose A bere z B, po ose B z A, treti z A."""
    n = np.array(stredy[a], float)
    n[osa_a] = stredy[b][osa_a]
    n[osa_b] = stredy[a][osa_b]
    return n


NOHY_KLICE = (("t", NOHA_PL), ("t", NOHA_PP), ("t", NOHA_ZL), ("t", NOHA_ZP), "FM", "RM")


PET_NOHY = ("PL", "PP", "ZL", "ZP", "FM", "RM")
PET_STRANY = {"vpravo": 0.0, "vzadu": 90.0, "vlevo": 180.0, "vpredu": -90.0}          # otoceni drzaku kolem svisle osy nohy (stupne, +y): sablona visi na strane +z (vpravo)
PET_NOHY_NAZVY = {"PL": "přední levé", "PP": "přední pravé", "ZL": "zadní levé", "ZP": "zadní pravé", "FM": "přední střední", "RM": "zadní střední"}
POLICE_MIN_OD_PODLAHY = 130.0     # nejnizsi mozna osa ramu police nad podlahou (mm) v systemu 30: pod koleckem / patkou musi zbyt noha pro rohove spojky (system 40: SYSTEMY[40]["police_min_od_podlahy"])
POLICE_KROK_DESKA = 48.0          # system 30: ram police 30 mm + deska 18 mm: horni plocha desky = osa ramu + 33 mm, spodek ramu = osa - 15 mm => rozdil dvou ramu = mezera + 48 mm (obecne P + 18)


def _vysky_polic(p, n_pol, hladiny_auto, y0, strop, h_min):
    """VYSKY SPODNICH POLIC (Robert 2026-10-04: "pridat vyskove stavitelnosti spodnich polic"; mereni: horni plocha desky od spodni hrany podelniku podepirajicich pracovni plochu,
    kazda dalsi police jako mezera mezi policemi). Cisluje se SHORA: police 1 = nejvyssi. Parametry police_h1 (odstup horni plochy desky pod `y0` = spodni hranou podelniku pracovni
    plochy) a police_h2.. (mezera od horni plochy desky k-te police po spodek ramu predchozi police nad ni); None = automaticky (dnesni rovnomerne rozlozeni od nejnizsi police 330 mm).
    Vraci (hladiny - osy ramu polic ZDOLA NAHORU, info). info: {"n", "hodnoty": [efektivni h1..hn], "auto": [bool], "min": [..], "max": [..], "ok": bool, "problem": text|None}.
    Meze jednotlive police jsou dane tim, ze ostatni zustanou jak jsou: odstup 1. police nejmene MEZERA_POLIC pod stropem (spodek supliku / pracovniho ramu), mezery nejmene MEZERA_POLIC,
    nejnizsi police nejnize na `h_min` (osa ramu)."""
    if n_pol <= 0:                                                                        # bez polic: nic k nastaveni (hladiny_auto = [ys] pro dily ramu, ktere v sablone zustavaji)
        return list(hladiny_auto), {"n": 0, "hodnoty": [], "auto": [], "min": [], "max": [], "ok": True, "problem": None}
    krok_desky = _P() + DESKA_TLOUSTKA                                                    # system 30: 48 = ram police 30 + deska 18
    vrch_desky = _H() + DESKA_TLOUSTKA                                                    # system 30: 33 = polovina ramu 15 + deska 18 (horni plocha desky nad osou ramu)
    a_h = list(reversed(hladiny_auto))                                                    # shora dolu
    auto_h = [y0 - (a_h[0] + vrch_desky)] + [(a_h[k - 1] - a_h[k]) - krok_desky for k in range(1, n_pol)]
    zad = [p.get(f"police_h{k + 1}") for k in range(n_pol)]
    hod = [auto_h[k] if zad[k] is None else float(zad[k]) for k in range(n_pol)]
    horni = [y0 - hod[0] - vrch_desky]                                                    # osy ramu shora dolu
    for k in range(1, n_pol):
        horni.append(horni[-1] - krok_desky - hod[k])
    rozpocet = y0 - (h_min + vrch_desky)                                                        # nejvetsi klesani horni plochy desky nejnizsi police pod y0
    d_min = (y0 - strop) + MEZERA_POLIC
    mez_min = [d_min] + [MEZERA_POLIC] * (n_pol - 1)
    mez_max = []
    for k in range(n_pol):
        zbytek = rozpocet - sum((hod[j] if j == 0 else krok_desky + hod[j]) for j in range(n_pol) if j != k)
        mez_max.append(zbytek if k == 0 else zbytek - krok_desky)
    problem = None
    if any(zad[k] is not None for k in range(n_pol)):
        for k in range(n_pol):
            if zad[k] is None:
                continue
            if hod[k] < mez_min[k] - 1e-6:
                problem = f"police {k + 1}: " + (f"odstup pod pracovní deskou {hod[k]:.0f} mm je menší než nejmenší možný {mez_min[k]:.0f} mm" if k == 0 else f"mezera {hod[k]:.0f} mm je menší než {mez_min[k]:.0f} mm")
                break
        if problem is None and horni[-1] < h_min - 1e-6:
            problem = f"nejnižší police by byla {h_min - horni[-1]:.0f} mm pod nejnižší možnou polohou (zmenši odstup nebo mezery)"
    info = {"n": n_pol, "hodnoty": [float(v) for v in hod], "auto": [z is None for z in zad], "min": [math.ceil(float(v) * 10 - 1e-9) / 10.0 for v in mez_min],
            "max": [max(math.floor(float(m) * 10 + 1e-9) / 10.0, math.ceil(float(mn) * 10 - 1e-9) / 10.0) for m, mn in zip(mez_max, mez_min)],          # meze ZAOKROUHLENE DOVNITR na 0,1 mm; hodnoty BEZ zaokrouhleni (sonda zivych operaci)
            "ok": problem is None, "problem": problem}
    return list(reversed(horni)), info


def _suplik_meze(bb, clenove, spojky, idx, ef, vlevo=False, K=0.0):
    """PRESNE meze posunu suplikoveho boxu (Robert: "suplik v noze je neakceptovatelny, zapomnels na limity"): hodnoty parametru `suplik_posun`, pri kterych se box (a jeho
    dve pricky a jejich spojky) NEprekryva s zadnou nohou (krajni i stredni) ani s dalsim prislusenstvim pod deskou (drzak PET lahve) a box ma od kazde nohy aspon
    ODSTUP_KOMPONENTU_OD_NOHOU z obou stran. `ef` = EFEKTIVNI posun boxu od sablony (vcetne automatickeho posunu pri parametru 0). Povolena oblast = mezery mezi
    sousednimi nohami (box nesmi ven za krajni nohy) bez pasem u prislusenstvi; vybere se mezera obsahujici AKTUALNI polohu (posun 0 od ni), kdyz je aktualni stav
    neplatny, nejblizsi neprazdna. Hodnoty se zaokrouhluji DOVNITR na 10 mm. Vraci {"hodnota": ef, "min", "max", "vejde"}; nevejde-li se box nikam, min = max = hodnota
    a vejde False."""
    i_box = idx[("t", BOX)]
    kl_sk = [k for k in (("t", BOX), ("t", XRAIL_BOX1), ("t", XRAIL_BOX2)) if k in clenove]
    sk_i = [idx[k] for k in kl_sk] + [idx[sk] for sk, sp in spojky.items() if any(v in kl_sk for v in sp["vlastnici"])]
    nohy = [(round(float(clenove[k]["pos"][2]), 3), bb[idx[k]]) for k in NOHY_KLICE if k in clenove]
    nohy += [(round(float(c["pos"][2]), 3), bb[idx[k]]) for k, c in clenove.items() if isinstance(k, tuple) and k[0] == "ram"]          # svisle profily vestaveneho ramu drzi od boxu stejny odstup jako nohy
    prisl = []
    for k, c in clenove.items():
        if c["druh"] != "prisl" or c["src"] == BOX or k[0] == "konec" or _je_zasl(k) or (isinstance(k, str) and k.startswith("kolecko")) or (k[0] == "t" and k[1] in KOLECKA):
            continue
        prisl.append(bb[idx[k]])

    def xy(a, b):
        return min(a[1][0], b[1][0]) - max(a[0][0], b[0][0]) > TOL_PRUNIK_MM and min(a[1][1], b[1][1]) - max(a[0][1], b[0][1]) > TOL_PRUNIK_MM

    # nohy, ktere se nektere casti hybne skupiny prekryvaji v X a Y
    zs = sorted({z for z, b in nohy if any(xy(bb[i], b) for i in sk_i)})
    mezery = []
    for a, b in zip(zs, zs[1:]):
        lo, hi = -np.inf, np.inf
        for i in sk_i:
            odstup = odstup_od_nohou() if i == i_box else TOL_PRUNIK_MM          # box 30 mm od nohou, pricky a spojky aspon bez pruniku
            for z, b_leg in nohy:
                if not xy(bb[i], b_leg):
                    continue
                if z == a:
                    lo = max(lo, a + _H() + odstup - float(bb[i][0][2]))
                elif z == b:
                    hi = min(hi, b - _H() - odstup - float(bb[i][1][2]))
        if lo <= hi:
            mezery.append((float(lo), float(hi)))
    # prislusenstvi pod deskou (drzak PET lahve...): pasmo posunu, ve kterem by se cast skupiny boxu s nim prekryla (> TOL), se z mezer vyrizne; desky a ramy se pres celou
    # sirku nedaji obejit - hlida je obecna kontrola, kolecka/zaslepky/patky jsou pod nohami
    for b_c in prisl:
        for i in sk_i:
            if not xy(bb[i], b_c):
                continue
            fa, fb = float(b_c[0][2]) - float(bb[i][1][2]) + TOL_PRUNIK_MM, float(b_c[1][2]) - float(bb[i][0][2]) - TOL_PRUNIK_MM
            novy = []
            for lo, hi in mezery:
                if lo <= min(hi, fa):
                    novy.append((lo, min(hi, fa)))
                if max(lo, fb) <= hi:
                    novy.append((max(lo, fb), hi))
            mezery = novy
    hodnota = round(float(K - ef if vlevo else ef), 1)          # hodnota PARAMETRU suplik_posun (vlevo: fyzicky posun S = K - parametr)
    if not mezery:
        return {"hodnota": hodnota, "min": hodnota, "max": hodnota, "vejde": False}
    lo, hi = min(mezery, key=lambda m: 0.0 if m[0] <= 0.0 <= m[1] else min(abs(m[0]), abs(m[1])))
    p_lo, p_hi = ((K - (ef + hi)), (K - (ef + lo))) if vlevo else ((ef + lo), (ef + hi))
    vmin = math.ceil(p_lo / 10.0 - 1e-9) * 10.0
    vmax = math.floor(p_hi / 10.0 + 1e-9) * 10.0
    if vmin > vmax:
        return {"hodnota": hodnota, "min": hodnota, "max": hodnota, "vejde": False}
    return {"hodnota": hodnota, "min": float(vmin), "max": float(vmax), "vejde": True}


def _pet_meze(bb, idx, ef, dily):
    """PRESNE meze svisleho posunu drzaku PET lahve (Robert 2026-10-04): hodnoty parametru `pet_posun` (mm, kladne = nahoru), pri kterych drzak nezasahuje do zadneho jineho dilu, ktery
    se s nim prekryva v X a Z (rám desky, spojky, deska police, suplikovy box...). Kazda prekazka zakaze pasmo posunu, ve kterem by se s drzakem prekryla (> TOL); povolena je mezera
    mezi pasmy, ktera obsahuje AKTUALNI polohu (kdyz stoji v kolizi, nejblizsi mezera - viz suplik). Hodnoty se zaokrouhluji DOVNITR na 10 mm. Vraci
    {"hodnota", "min", "max", "vejde"}; nikam se nevejde -> min = max = hodnota, vejde False."""
    i = idx[("t", PET)]
    lo_p, hi_p = bb[i]
    zakaz = []
    for j in range(len(bb)):
        if j == i:
            continue
        a, b = bb[j]
        if min(float(b[0]), float(hi_p[0])) - max(float(a[0]), float(lo_p[0])) <= TOL_PRUNIK_MM or min(float(b[2]), float(hi_p[2])) - max(float(a[2]), float(lo_p[2])) <= TOL_PRUNIK_MM:
            continue
        zakaz.append((float(a[1]) - float(hi_p[1]) + TOL_PRUNIK_MM, float(b[1]) - float(lo_p[1]) - TOL_PRUNIK_MM))      # posun s (od aktualni polohy), pri kterem by se prekryl
    # drzak visi na noze (svisly profil, ke kteremu lici): nesmi ji opustit - horni a dolni konec profilu omezuji posun
    for j in range(len(bb)):
        if j == i or dily[j]["part_id"] not in PROFIL_PARTS:
            continue
        a, b = bb[j]
        ex, ey, ez = float(b[0] - a[0]), float(b[1] - a[1]), float(b[2] - a[2])
        if ey < 3.0 * max(ex, ez):
            continue
        ox = min(float(b[0]), float(hi_p[0])) - max(float(a[0]), float(lo_p[0])) > TOL_PRUNIK_MM
        oz = min(float(b[2]), float(hi_p[2])) - max(float(a[2]), float(lo_p[2])) > TOL_PRUNIK_MM
        tz = abs(float(b[2]) - float(lo_p[2])) <= 1.5 or abs(float(a[2]) - float(hi_p[2])) <= 1.5          # drzak lici ke strane profilu v ose Z ...
        tx = abs(float(b[0]) - float(lo_p[0])) <= 1.5 or abs(float(a[0]) - float(hi_p[0])) <= 1.5          # ... nebo v ose X
        if (tz and ox) or (tx and oz):
            zakaz.append((-np.inf, float(a[1]) - float(lo_p[1])))                  # pod koncem profilu
            zakaz.append((float(b[1]) - float(hi_p[1]), np.inf))                   # nad koncem profilu
    zakaz.sort()
    mezery, od = [], -np.inf
    for za, zb in zakaz:
        if za > od:
            mezery.append((od, za))
        od = max(od, zb)
    mezery.append((od, np.inf))
    hodnota = round(float(ef), 1)
    mezery = [(lo, hi) for lo, hi in mezery if lo <= hi]
    if not mezery:
        return {"hodnota": hodnota, "min": hodnota, "max": hodnota, "vejde": False}
    lo, hi = min(mezery, key=lambda m: 0.0 if m[0] <= 0.0 <= m[1] else min(abs(m[0]), abs(m[1])))
    vmin = hodnota if not np.isfinite(lo) else math.ceil((ef + lo) / 10.0 - 1e-9) * 10.0
    vmax = hodnota if not np.isfinite(hi) else math.floor((ef + hi) / 10.0 + 1e-9) * 10.0
    if vmin > vmax:
        return {"hodnota": hodnota, "min": hodnota, "max": hodnota, "vejde": False}
    return {"hodnota": hodnota, "min": float(vmin), "max": float(vmax), "vejde": True}


def _elzlab_meze(bb, klice_t, p, info):
    """PRESNE meze pohybu elektrozlabu (Robert 2026-10-05: dotyka se panelu nebo profilu, zatim pohybliv svisle i do stran): hodnoty parametru `elzlab_y` a `elzlab_z` (mm od vychozi polohy),
    pro ktere se zlab (a) dotyka panelu, profilu panelu nebo zadni stojky (aspon jedno z nich lezi za nim v rovine YZ; zlab se opre o NEJPREDNEJSI lico za nim), (b) nezasahuje do zadneho
    jineho dilu (deska, spojky, vzpery...) a (c) neni mimo sirku stolu. Zkouska vsech poloh po 5 mm vektorove (bez generovani stolu); povolen je souvisly usek, ktery obsahuje AKTUALNI
    polohu (kdyz stoji v kolizi, nejblizsi usek); zaokrouhleno DOVNITR na 10 mm. Vraci {"y": {hodnota, min, max}, "z": {...}, "vejde": bool} nebo None (bez elektrozlabu)."""
    zl = info.get("zlab") if info else None
    if not zl or ("t", ELZLAB) not in klice_t:
        return None
    i_s = klice_t.index(("t", ELZLAB))
    opory = [i for i, k in enumerate(klice_t) if (isinstance(k, tuple) and k[0] in ("pan", "panrail")) or k in (("t", NOHA_ZL), ("t", NOHA_ZP), "RM")]
    ost = [i for i in range(len(klice_t)) if i != i_s and i not in set(opory)]
    lo_k = np.array([bb[i][0] for i in opory], float)
    hi_k = np.array([bb[i][1] for i in opory], float)
    lo_o = np.array([bb[i][0] for i in ost], float)
    hi_o = np.array([bb[i][1] for i in ost], float)
    rozm = np.array(zl["rozmer"], float)
    noha_l, noha_p = klice_t.index(("t", NOHA_ZL)), klice_t.index(("t", NOHA_ZP))
    z_min, z_max = float(bb[noha_l][0][2]), float(bb[noha_p][1][2])           # vnejsi lica zadnich stojek = sirka stolu

    def platne(oy, oz):
        """Pole bool pro davku poloh (oy, oz: pole stejne delky)."""
        y0 = zl["y0"] + oy
        z0 = zl["z0"] + oz
        in_z = (z0 >= z_min - 1e-6) & (z0 + rozm[2] <= z_max + 1e-6)
        ov = ((np.minimum(hi_k[None, :, 1], (y0 + rozm[1])[:, None]) - np.maximum(lo_k[None, :, 1], y0[:, None]) > 0.5)
              & (np.minimum(hi_k[None, :, 2], (z0 + rozm[2])[:, None]) - np.maximum(lo_k[None, :, 2], z0[:, None]) > 0.5))
        mamo = ov.any(axis=1)
        xb = np.where(ov, lo_k[None, :, 0], np.inf).min(axis=1)
        xb = np.where(mamo, xb, 0.0)
        lo = np.stack([xb - rozm[0], y0, z0], axis=1)
        hi = np.stack([xb, y0 + rozm[1], z0 + rozm[2]], axis=1)
        pr = np.minimum(hi[:, None, :], hi_o[None, :, :]) - np.maximum(lo[:, None, :], lo_o[None, :, :])
        kol = (np.all(pr > 0, axis=2) & (pr.min(axis=2) > TOL_PRUNIK_MM)).any(axis=1)
        return in_z & mamo & ~kol

    def usek(osa, ef):
        g = np.arange(-1500.0, 1500.0 + 1e-6, 5.0)
        ok = platne(g, np.full_like(g, p["elzlab_z"])) if osa == "y" else platne(np.full_like(g, p["elzlab_y"]), g)
        cur = int(round((ef + 1500.0) / 5.0))
        cur = min(max(cur, 0), len(g) - 1)
        if not ok.any():
            return {"hodnota": round(float(ef), 1), "min": round(float(ef), 1), "max": round(float(ef), 1)}, False
        if not ok[cur]:
            blizko = np.nonzero(ok)[0]
            cur = int(blizko[np.argmin(np.abs(blizko - cur))])
        a = cur
        while a > 0 and ok[a - 1]:
            a -= 1
        b = cur
        while b < len(g) - 1 and ok[b + 1]:
            b += 1
        vmin, vmax = math.ceil(g[a] / 10.0 - 1e-9) * 10.0, math.floor(g[b] / 10.0 + 1e-9) * 10.0
        return {"hodnota": round(float(ef), 1), "min": float(min(vmin, vmax)), "max": float(max(vmin, vmax))}, bool(vmin <= vmax)

    my, ok_y = usek("y", float(p["elzlab_y"]))
    mz, ok_z = usek("z", float(p["elzlab_z"]))
    return {"y": my, "z": mz, "vejde": bool(ok_y and ok_z)}


def elzlab_meze(r):
    """Meze pohybu elektrozlabu z vysledku sestav_stul() (viz _elzlab_meze); None bez elektrozlabu. Vysledek se drzi v `r["elzlab_meze"]`."""
    if "elzlab_meze" not in r:
        klice_t = [tuple(k) if isinstance(k, (list, tuple)) else k for k in r["klice"]]
        klice_t = [tuple(tuple(x) if isinstance(x, list) else x for x in k) if isinstance(k, tuple) else k for k in klice_t]
        with _v_systemu(r["parametry"].get("system", SYSTEM_VYCHOZI)):
            bb = [_aabb(d) for d in r["dily"]]
            r["elzlab_meze"] = _elzlab_meze(bb, klice_t, r["parametry"], r.get("panely_info"))
    return r["elzlab_meze"]


def _je_vz(k):
    """Klic dilu sikme vzpery ("vz", strana, "prof" | 0 | 1)."""
    return isinstance(k, tuple) and len(k) > 0 and k[0] == "vz"


# ---------------------------------------------------------------------------------------------------------------------
# ZASLEPKY NA VOLNE KONCE PROFILU (Robert 2026-10-06: "v generatorech ... na volne konce profilu se musi automaticky davat zaslepky").
# Konec profilu je VOLNY, kdyz se ho nedotyka zadny jiny dil (ani profil, deska, spojka, kolecko / zaslepka pod nohou...): v pasu od ZASLEPKA_DOTYK_PRED_MM pod koncovou plochou
# po ZASLEPKA_DOTYK_ZA_MM za ni, v prurezu profilu zmenseném o ZASLEPKA_ZMENSENI_MM, neni AABB zadneho jineho dilu. Takovy konec dostane zaslepku systemu (3071 / 3090 / 3091):
# zatka do profilu, priruba (zaslepka_vyska) vne - stejna poloha jako u zaslepek pod nohami (konec profilu = povrch zaslepky + zaslepka_vyska). Klic dilu: ("zasl", klic profilu, "+" | "-").
# Konce sikmych vzper (nese je sikma spojka) a stolu SSE (vlastni jadro stul_sse, zaslepky podelniku tam jsou) se nehodnoti.
# ---------------------------------------------------------------------------------------------------------------------
ZASLEPKA_DOTYK_PRED_MM, ZASLEPKA_DOTYK_ZA_MM, ZASLEPKA_ZMENSENI_MM = 1.5, 2.5, 1.0


def _je_zasl(k):
    """Klic zaslepky volneho konce profilu ("zasl", klic profilu, "+" | "-")."""
    return isinstance(k, tuple) and len(k) == 3 and k[0] == "zasl"


def _kvat_z_matice(m):
    """Kvaternion (x, y, z, w) rotacni matice 3x3 (sloupce = obrazy lokalnich os X, Y, Z)."""
    m = np.asarray(m, float)
    stopa = m[0, 0] + m[1, 1] + m[2, 2]
    if stopa > 0.0:
        s_ = math.sqrt(stopa + 1.0) * 2.0
        q = [(m[2, 1] - m[1, 2]) / s_, (m[0, 2] - m[2, 0]) / s_, (m[1, 0] - m[0, 1]) / s_, 0.25 * s_]
    elif m[0, 0] > m[1, 1] and m[0, 0] > m[2, 2]:
        s_ = math.sqrt(1.0 + m[0, 0] - m[1, 1] - m[2, 2]) * 2.0
        q = [0.25 * s_, (m[0, 1] + m[1, 0]) / s_, (m[0, 2] + m[2, 0]) / s_, (m[2, 1] - m[1, 2]) / s_]
    elif m[1, 1] > m[2, 2]:
        s_ = math.sqrt(1.0 + m[1, 1] - m[0, 0] - m[2, 2]) * 2.0
        q = [(m[0, 1] + m[1, 0]) / s_, 0.25 * s_, (m[1, 2] + m[2, 1]) / s_, (m[0, 2] - m[2, 0]) / s_]
    else:
        s_ = math.sqrt(1.0 + m[2, 2] - m[0, 0] - m[1, 1]) * 2.0
        q = [(m[0, 2] + m[2, 0]) / s_, (m[1, 2] + m[2, 1]) / s_, 0.25 * s_, (m[1, 0] - m[0, 1]) / s_]
    return tuple(float(v) for v in q)


def _q_zaslepky(smer_dovnitr):
    """Kvaternion, ktery otoci lokalni +Z zaslepky (zatka do profilu) do `smer_dovnitr`; lokalni X zustane u svetoveho X (nebo Y u smeru podel X), takze pro smer +Y vychazi stejna
    rotace jako u zaslepek pod nohami (-90 st. kolem X)."""
    z = np.asarray(smer_dovnitr, float)
    z = z / np.linalg.norm(z)
    ref = np.array([1.0, 0.0, 0.0]) if abs(z[0]) < 0.9 else np.array([0.0, 1.0, 0.0])
    y = np.cross(z, ref)
    y /= np.linalg.norm(y)
    x = np.cross(y, z)
    return _kvat_z_matice(np.column_stack([x, y, z]))


def _volne_konce(clenove, spojky):
    """[(klic profilu, +1 / -1 = konec na kladne / zaporne strane osy, bod koncove plochy (stred, mm), vnejsi smer (jednotkovy))] pro konce profilu, na kterych nic nesedi (viz vyse)."""
    prof = [(k, c) for k, c in clenove.items() if c["druh"] == "profil" and not _je_vz(k) and c["part_id"] in PROFIL_PARTS]
    if not prof:
        return []
    drzaky = list(clenove.items()) + list(spojky.items())
    boxy = np.array([_aabb({"part_id": c["part_id"], "quaternion": c["quaternion"], "scale": c["scale"], "position": c["pos"]}) for _, c in drzaky], float)       # N x 2 x 3
    vlastni = {k: n for n, (k, _) in enumerate(drzaky)}
    w = _H() - ZASLEPKA_ZMENSENI_MM
    out = []
    for k, c in prof:
        R = kvat_na_matici(c["quaternion"])
        osa = R @ np.array([0.0, 1.0, 0.0])
        a1, a2 = R[:, 0], R[:, 2]
        stred = np.asarray(c["pos"], float)
        L = 1000.0 * c["scale"][1]
        for znak in (1, -1):
            dvn = osa * znak
            bod = stred + dvn * (L / 2.0)
            rohy = np.array([bod + dvn * t + a1 * u + a2 * v for t in (-ZASLEPKA_DOTYK_PRED_MM, ZASLEPKA_DOTYK_ZA_MM) for u in (-w, w) for v in (-w, w)])
            lo, hi = rohy.min(axis=0), rohy.max(axis=0)
            dotyk = (boxy[:, 1, :] > lo + 0.05).all(axis=1) & (boxy[:, 0, :] < hi - 0.05).all(axis=1)
            dotyk[vlastni[k]] = False
            if not dotyk.any():
                out.append((k, znak, bod, dvn))
    return out


def _mat_na_kvat(Rm):
    """Kvaternion (x, y, z, w) z otocne matice 3x3 (det +1)."""
    t = float(np.trace(Rm))
    if t > 0:
        s_ = math.sqrt(t + 1.0) * 2
        w, x, y, z = 0.25 * s_, (Rm[2, 1] - Rm[1, 2]) / s_, (Rm[0, 2] - Rm[2, 0]) / s_, (Rm[1, 0] - Rm[0, 1]) / s_
    else:
        i = int(np.argmax(np.diag(Rm)))
        j, k = (i + 1) % 3, (i + 2) % 3
        s_ = math.sqrt(1.0 + Rm[i, i] - Rm[j, j] - Rm[k, k]) * 2
        q = np.zeros(4)
        q[i] = 0.25 * s_
        q[j] = (Rm[j, i] + Rm[i, j]) / s_
        q[k] = (Rm[k, i] + Rm[i, k]) / s_
        w = (Rm[k, j] - Rm[j, k]) / s_
        x, y, z = q[0], q[1], q[2]
    q = np.array([x, y, z, w], float)
    return tuple(float(v) for v in q / np.linalg.norm(q))


_SAT_B = np.eye(3)


def _sat_osy(R1):
    """Deliciti osy SAT pro OBB s osami R1 (po sloupcich) a AABB: 3 + 3 + 9 vektorovych soucinu, normalizovane, nulove vyrazene. (n, 3)"""
    A = R1.T
    osy = np.vstack([A, _SAT_B, np.cross(A[:, None, :], _SAT_B[None, :, :]).reshape(-1, 3)])
    n = np.linalg.norm(osy, axis=1)
    return osy[n > 1e-9] / n[n > 1e-9, None]


def _sat_obb_aabb_davka(c1, R1, h1, lo, hi, osy=None):
    """Hloubky pruniku (mm; <= 0 = bez pruniku) OBB (stred c1, osy R1 po sloupcich, polorozmery h1) a davky AABB (lo, hi: (n, 3)) - nejmensi presah pres vsechny deliciti
    osy (SAT), vektorove. Sikmy profil vzpery ma velkou AABB, ktera se falesne protina se stojkou/ramenem - proto presny test."""
    osy = _sat_osy(R1) if osy is None else osy
    lo, hi = np.atleast_2d(lo), np.atleast_2d(hi)
    c2, h2 = (lo + hi) / 2.0, (hi - lo) / 2.0
    r1 = (np.abs(osy @ R1) * h1).sum(axis=1)                      # polomer OBB na kazde ose (osy @ R1 = soucin osy s osami OBB)
    r2 = (np.abs(osy)[None, :, :] * h2[:, None, :]).sum(axis=2)   # (n, osy)
    vz = np.abs((c2 - c1) @ osy.T)                                # (n, osy)
    return (r1[None, :] + r2 - vz).min(axis=1)


def _sat_obb_aabb(c1, R1, h1, lo, hi):
    """Hloubka pruniku jedne dvojice OBB x AABB (viz _sat_obb_aabb_davka)."""
    return float(_sat_obb_aabb_davka(c1, R1, h1, np.asarray(lo, float), np.asarray(hi, float))[0])


def _vzpera_sada(x_p, y_a, z, delka):
    """Dily jedne vzpery pro stojku s PREDNIM licem v x = x_p a rameno se SPODKEM v y = y_a (osa z = osa stojky/ramene). Roviny X-Y: u = vzdalenost dopredu od licem stojky (-x),
    v = vzdalenost dolu od spodku ramene (-y). Stred spodniho konce profilu E1 = (u1 = S, v1 = S + delka/sqrt2), horniho konce E2 = (u2 = S + delka/sqrt2, v2 = S), S = VZPERA_STEN.
    Spojka na konci: nativni X -> lat = (+1, +1, 0)/sqrt2, nativni Y -> osa ven z konce profilu (dole (+1, -1, 0)/sqrt2, nahore (-1, +1, 0)/sqrt2), nativni Z = lat x osa;
    pivot = stred konce + VZPERA_CELO_STRED * lat (pocatek spojky je v rohu celniho ctverce). Sikma plocha spojky (n = cos45 osa + sin45 lat) pak lezi na stene stojky (dole)
    a na spodku ramene (nahore). SYSTEM 40 (spojka 3220): bocni osa je nativni Z (ne X; nativni X = osa x lat), pocatek je ve stredu celniho ctverce (odsazeni 0) a o 0,1656 mm za koncem
    profilu v ose ven; parametry vzpera_* v SYSTEMY."""
    s2 = math.sqrt(0.5)
    sd = _sd()
    st = sd["vzpera_sten"]
    e1 = np.array([x_p - st, y_a - st - s2 * delka, z])
    e2 = np.array([x_p - st - s2 * delka, y_a - st, z])
    lat = np.array([s2, s2, 0.0])
    spojky = []
    for e, osa in ((e1, np.array([s2, -s2, 0.0])), (e2, np.array([-s2, s2, 0.0]))):
        if sd["vzpera_lat_nativni"] == "x":
            Rm = np.column_stack([lat, osa, np.cross(lat, osa)])                  # nativni X = lat, Y = osa, Z = lat x osa (3254)
        else:
            Rm = np.column_stack([np.cross(osa, lat), osa, lat])                  # nativni X = osa x lat, Y = osa, Z = lat (3220)
        spojky.append((e + sd["vzpera_celo_lat"] * lat + sd["vzpera_celo_osa"] * osa, _mat_na_kvat(Rm)))
    q_prof = (0.0, 0.0, math.sin(math.pi / 8), math.cos(math.pi / 8))           # nativni Y (osa profilu) -> (-1, +1, 0)/sqrt2: otoceni o +45 st. kolem Z
    return {"stred": (e1 + e2) / 2.0, "q_prof": q_prof, "spojky": spojky}


_VZPERA_CACHE = {}


def _vzpera_plati(delka, pary, bb_vse):
    """Vejde se vzpera delky `delka` (profil) pod VSECHNA zadana ramena? RYCHLA predkontrola stejne logiky jako `_zkontroluj_vzpery` (ta zustava rozhodujici): pro kazdy par
    (stojka, rameno) se spocita poloha vzpery, profil (OBB) nesmi zasahnout do stojky, ramene ani jineho dilu, spojky (AABB) do zadneho dilu krome stojky/ramene, spojka u ramene
    musi lezet pod ramenem a spojka u stojky nad spodkem stojky. `pary` = [{x_p, y_a, z, bb_post, bb_arm, ostatni: indexy do bb_vse}], `bb_vse` = pole (n, 2, 3)."""
    for par in pary:
        sada = _vzpera_sada(par["x_p"], par["y_a"], par["z"], delka)
        Rm = kvat_na_matici(sada["q_prof"])
        h = np.array([_H(), delka / 2.0, _H()])
        c = sada["stred"]
        ext = np.abs(Rm) @ h
        lo_p, hi_p = c - ext, c + ext
        bbs = [_aabb({"part_id": _sd()["vzpera_spojka"], "quaternion": q, "scale": [1.0, 1.0, 1.0], "position": pivot}) for pivot, q in sada["spojky"]]
        if bbs[1][0][0] < par["bb_arm"][0][0] - VZPERA_REZERVA_RAMENE - 0.01 or bbs[0][0][1] < par["bb_post"][0][1] + _P():
            return False
        osy = _sat_osy(Rm)
        fr_lo, fr_hi = np.array([par["bb_post"][0], par["bb_arm"][0]]), np.array([par["bb_post"][1], par["bb_arm"][1]])
        if np.any(_sat_obb_aabb_davka(c, Rm, h, fr_lo, fr_hi, osy) > TOL_PRUNIK_MM):
            return False
        lo_o, hi_o = bb_vse[par["ostatni"], 0], bb_vse[par["ostatni"], 1]
        blizko = np.nonzero(np.all((lo_o < hi_p) & (hi_o > lo_p), axis=1))[0]
        if blizko.size and np.any(_sat_obb_aabb_davka(c, Rm, h, lo_o[blizko], hi_o[blizko], osy) > TOL_PRUNIK_MM):
            return False
        for lo_s, hi_s in bbs:
            pr = np.minimum(hi_o, hi_s) - np.maximum(lo_o, lo_s)
            if np.any(np.all(pr > 0, axis=1) & (pr.min(axis=1) > TOL_PRUNIK_MM)):
                return False
    return True


def _delka_int(delka):
    """Delka panelu jako cele cislo z PANEL_TYPY (jinak StulChyba)."""
    d = int(round(float(delka)))
    if d not in PANEL_TYPY:
        raise StulChyba(f"panely_delka: {delka!r} neni jedna z delek panelu {', '.join(str(x) for x in PANEL_DELKY)} mm", "mimo_rozsah")
    return d


def _panel_geometrie(delka=None):
    """Rozmery perforovaneho panelu DANE DELKY (None = vychozi 1190) a elektrozlabu z AABB sablony aktivniho systemu: panel (tloustka x, vyska y, sirka z, stred, dil katalogu `part`), zlab (rozmery,
    odsazeni jeho dolniho leveho rohu od panelu). Panel jine delky nese STEJNE otoceni a polohu jako panel sablony (stred0 = stred JEHO obalky pri teto poloze, posun = cil - stred0); elektrozlab zustava
    na panelu v tomtez odstupu od jeho DOLNI a LEVE hrany jako v sablone (v sablone sedi u leveho konce panelu 1190; u delsiho panelu tedy zase u leveho konce)."""
    d = PANEL_DELKA_VYCHOZI if delka is None else _delka_int(delka)
    sab = sablona()
    lo0, hi0 = _aabb(sab[PANEL_D])                                   # panel sablony (1190)
    cast = dict(sab[PANEL_D])
    cast["part_id"] = PANEL_TYPY[d]
    lo, hi = _aabb(cast)
    ls, hs = _aabb(sab[ELZLAB])
    s1 = float(hi[2] - lo[2])
    return {"tl": float(hi[0] - lo[0]), "v": float(hi[1] - lo[1]), "s": s1, "stred0": (lo + hi) / 2.0, "delka": d, "part": PANEL_TYPY[d],
            "zlab": hs - ls, "zlab_stred0": (ls + hs) / 2.0, "zlab_od_y": float(ls[1] - lo0[1]), "zlab_od_z": float(ls[2] - lo0[2])}


def _pole_panelu(zl, zr, zm, rezim):
    """Useky mezi zadnimi stojkami, do kterych se vsazuji panely: [(a, b, klic leve stojky, klic prave stojky)], a/b = vnitrni lica stojek (z). Se strednimi nohami (rezim `noha`) dva useky,
    jinak (bez stredni opory nebo s vestavenym ramem - zadni podelniky jdou cele) jeden."""
    H = _H()
    if zm is not None and rezim == "noha":
        return [(zl + H, zm - H, ("t", NOHA_ZL), "RM"), (zm + H, zr - H, "RM", ("t", NOHA_ZP))]
    return [(zl + H, zr - H, ("t", NOHA_ZL), ("t", NOHA_ZP))]


def _deli_desku_u_opory(clenove, sab, src, klic_prvni, klic_kus, zm, mezera, vyrezy=None):
    """DELENI DESKY u stredni opory (Robert 2026-10-05, formaty tabuli lamino desky): deska (pracovni, spodni police) se u stredni nohy / vestaveneho ramu rozdeli na dve desky v ose opory `zm`.
    `mezera` = 0: desky na sebe PRUBEZNE NAVAZUJI (stredni nohy, pracovni deska i u ramu); `mezera` > 0: obe desky jsou o pulku mezery kratsi (spodni police u vestaveneho ramu: svisly profil
    ramu prochazi rovinou police). Desku tvori kusy (obdelniky; vyrezy v pracovni desce je rozrezaly): kusy pres osu se rozriznou. Deska z VICE kusu nese na prvnim kusu `celek` (rozmer cele desky
    = cena) a pocet vyrezu `vyrezu`, dalsi kusy `kus`; deska z jednoho kusu je obycejny dil bez priznaku. Klice: prvni kus leve desky zustava `klic_prvni`, dalsi kusy jsou (`klic_kus`, n)."""
    klice = [k for k in [klic_prvni] + [k for k in clenove if isinstance(k, tuple) and k[0] == klic_kus] if k in clenove]
    if not klice:
        return
    cast = sab[src]
    lo_g, hi_g = glb_bbox(cast["part_id"])
    lc = (lo_g + hi_g) / 2.0
    Rm = kvat_na_matici(cast["quaternion"])
    sc_t = clenove[klic_prvni]["scale"][2]
    obd = []
    y_stred = 0.0
    for k in klice:
        c = clenove[k]
        lo, hi = _aabb({"part_id": c["part_id"], "quaternion": c["quaternion"], "scale": c["scale"], "position": c["pos"]})
        sc_k = c["scale"]                                              # NOMINALNI rozmery kusu (scale x 1000), stred z AABB: bez sumu meshe desky (~0,005 mm), cena a vypis sedi na desetiny mm
        cx_k, cz_k = float(lo[0] + hi[0]) / 2.0, float(lo[2] + hi[2]) / 2.0
        obd.append((cx_k - 500.0 * sc_k[0], cx_k + 500.0 * sc_k[0], cz_k - 500.0 * sc_k[1], cz_k + 500.0 * sc_k[1]))
        y_stred = float((lo[1] + hi[1]) / 2.0)
    z_l, z_p = zm - mezera / 2.0, zm + mezera / 2.0
    leve, prave = [], []
    for xa, xb, za, zb in obd:
        if zb <= z_l + 1e-6:
            leve.append((xa, xb, za, zb))
        elif za >= z_p - 1e-6:
            prave.append((xa, xb, za, zb))
        else:
            if z_l - za > 0.05:
                leve.append((xa, xb, za, z_l))
            if zb - z_p > 0.05:
                prave.append((xa, xb, z_p, zb))
    n_vyr = [0, 0]
    for v in vyrezy or []:
        n_vyr[0 if (v["z0"] + v["z1"]) / 2.0 <= zm else 1] += 1          # kazdy vyrez se pocita u desky, v niz lezi jeho stred (soucet = pocet vyrezu)
    for k in klice:
        if k != klic_prvni:
            del clenove[k]
    n_kus = 0
    for strana, rects in enumerate((leve, prave)):
        if not rects:
            continue
        hloubka_b = max(r[1] for r in rects) - min(r[0] for r in rects)
        sirka_b = max(r[3] for r in rects) - min(r[2] for r in rects)
        for j, (xa, xb, za, zb) in enumerate(rects):
            s_k = np.array([(xb - xa) / 1000.0, (zb - za) / 1000.0, sc_t])
            stred = np.array([(xa + xb) / 2.0, y_stred, (za + zb) / 2.0])
            clen = _clen(cast["part_id"], cast["quaternion"], s_k.tolist(), stred - Rm @ (s_k * lc), "deska", src=src)
            if len(rects) > 1:
                if j == 0:
                    clen["celek"] = [round(hloubka_b, 3), round(sirka_b, 3)]       # cena: cela deska (rozmery pred rozrezanim na kusy kolem vyrezu)
                    clen["vyrezu"] = n_vyr[strana]
                else:
                    clen["kus"] = True
            if strana == 0 and j == 0:
                clenove[klic_prvni] = clen
            else:
                n_kus += 1
                while (klic_kus, n_kus) in clenove:
                    n_kus += 1
                clenove[(klic_kus, n_kus)] = clen


def _oznac_desky(clenove, zm):
    """Kazdemu dilu desky pridela `deska_id` (kam patri): pracovni deska `prac_<strana>`, spodni police urovne k `pol<k>_<strana>`, police pod vyrezem `polvyr<n>`; strana 0 = vlevo od stredni
    opory (nebo jedina deska), 1 = vpravo. Deska rozrezana vyrezy ma vsechny kusy stejne id."""
    for k, c in clenove.items():
        if c["druh"] != "deska" or c.get("deska_id"):          # deska horni police ma deska_id uz od vzniku (api/stul_hpolice.py)
            continue
        lo, hi = _aabb({"part_id": c["part_id"], "quaternion": c["quaternion"], "scale": c["scale"], "position": c["pos"]})
        strana = 0 if (zm is None or (float(lo[2]) + float(hi[2])) / 2.0 <= zm) else 1
        if k == ("t", DESKA_PRAC) or k[0] == "kus":
            c["deska_id"] = f"prac_{strana}"
        elif k == ("t", DESKA_POLICE) or k[0] == "kusp":
            c["deska_id"] = f"pol0_{strana}"
        elif k[0] == "polic":
            c["deska_id"] = f"pol{k[1]}_{strana}"
        elif k[0] == "polvyr":
            c["deska_id"] = f"polvyr{k[1]}"


def _popis_desky(deska_id, rozdelena=False):
    """Citelny nazev desky podle `deska_id` (viz _oznac_desky): pracovni deska / spodni police (cislo police) / police pod vyrezem; u stolu delene u stredni opory (`rozdelena`) s casti
    (leva / prava - pri pohledu zepredu, osa Z doprava)."""
    if deska_id.startswith("hpol"):
        return _hpol().popis_desky(deska_id)
    zaklad, _, strana = deska_id.rpartition("_") if not deska_id.startswith("polvyr") else (deska_id, "", "0")
    cast = (" – levá část" if strana == "0" else " – pravá část") if rozdelena else ""
    if zaklad == "prac":
        return "pracovní deska" + cast
    if zaklad.startswith("polvyr"):
        return f"police pod výřezem {zaklad[6:]}"
    k = int(zaklad[3:]) if zaklad.startswith("pol") else 0
    return ("spodní police" if k == 0 else f"spodní police č. {k + 1}") + cast


def panel_limity(system=None, delka=None):
    """Nejmensi rozmery pro perforovany panel DANE DELKY (None = nejkratsi, 1190) v systemu profilu (mm, zaokrouhleno nahoru): `usek` = volna sirka mezi stojkami (panel + 2 x mezera), `min_sirka` = nejuzsi stul
    (jedna rada, bez strednich noh), `min_sirka_nohy` = nejuzsi stul, kdy se panel vejde mezi stredni nohy (dva useky, stredni noha uprostred), `min_stojky` = nejnizsi zadni stojky nad deskou pro jednu radu."""
    with _v_systemu(VYCHOZI["system"] if system is None else system):
        pg, P = _panel_geometrie(delka), _P()
        usek = pg["s"] + 2 * PANEL_MEZERA
        return {"usek": int(math.ceil(usek)), "min_sirka": int(math.ceil(usek + 2 * P)), "min_sirka_nohy": int(math.ceil(2 * usek + 3 * P)),
                "min_stojky": int(math.ceil(PANEL_ODSTUP_OD_PRICKY + pg["v"] + 2 * PANEL_MEZERA + 2 * P))}


def _sloupcu_panelu(zl, zr, zm, rezim, delka=None):
    """Pocet useku mezi stojkami (v danem rezimu stredni opory), do kterych se panel dane delky vejde (panel + 2 x 1 mm)."""
    pg = _panel_geometrie(delka)
    return sum(1 for (a, b, _kl, _kr) in _pole_panelu(zl, zr, zm, rezim) if b - a >= pg["s"] + 2 * PANEL_MEZERA - 1e-6)


def _kapacita_panelu(zl, zr, zm, rezim, delka=None):
    """Kolik panelu se vejde mezi stojky v danem rezimu stredni opory: pocet useku, do kterych se panel vejde (delka + 2 x 1 mm), krat nejvyssi pocet radu."""
    return _sloupcu_panelu(zl, zr, zm, rezim, delka) * PANELY_MAX_RAD


def _rezim_opory(p, n_pol, zl, zr, zm, delka=None):
    """Stredni opora u sirokeho stolu (sirka nad prahem): `noha` (stredni nohy, delici zadni podelniky) nebo `ram` (vestaveny ram mezi 4 podelniky, podelniky zustanou cele; jen se spodni
    policí). `auto` = noha, ram jen kdyz se pozadovany pocet panelu jinak nevejde (stredni noha deli zadni stranu na dva useky kratsi nez panel) a drzak PET neni na stredni noze."""
    volba = p["stredni_opora"]
    delka = p["panely_delka"] if delka is None else delka                  # delka panelu, pro kterou se kapacita pocita (efektivni delku urcuje _delka_panelu_ef)
    ram_mozny = RAM_ZAPNUT and n_pol >= 1
    if volba == "noha":
        return "noha"
    if volba == "ram":
        return "ram" if ram_mozny else "noha"
    n = int(p["panely_pocet"]) if (p["panely"] and p["stojky"]) else 0
    if n <= 0:
        return "noha"
    if p["drzak_pet"] and p["pet_noha"] in ("FM", "RM"):               # drzak PET na stredni noze: stredni nohy musi byt (panel, ktery se pak nevejde, se odebere); vestaveny ram jen na vyslovne pozadani
        return "noha"
    kap_noha = _kapacita_panelu(zl, zr, zm, "noha", delka)
    if kap_noha >= n:
        return "noha"
    if ram_mozny:
        kap_ram = _kapacita_panelu(zl, zr, zm, "ram", delka)
        if kap_ram >= n or kap_ram > kap_noha:
            return "ram"
    return "noha"


def _pg_nebo_none(d):
    """_panel_geometrie(d), nebo None, kdyz GLB dilu teto delky v katalogu chybi (delka se pak nenabizi; vychozi cesta nesmi spadnout kvuli volitelne delce)."""
    try:
        return _panel_geometrie(d)
    except StulChyba:
        return None


def _rad_panelu(pg, volna_vyska):
    """Kolik radu panelu daneho rozmeru se vejde na zadni stojky (`volna_vyska` = misto nad spodni polohou panelu bez horniho profilu, mm): stejny vzorec jako v bloku panelu (rad_max)."""
    return max(0, min(PANELY_MAX_RAD, int((volna_vyska + 1e-3) // (_P() + pg["v"] + 2.0 * PANEL_MEZERA))))


def _delka_panelu_ef(p, n_pol, zl, zr, zm, stredni, volna_vyska):
    """(delka, rezim): EFEKTIVNI delka panelu a rezim stredni opory (None bez stredni opory). Zvolena delka `panely_delka`, ktera se do zadneho useku mezi stojkami nevejde (sirka) nebo se na zadni
    stojky nevejde na vysku (panel 1671 ma 455 mm, ostatni 460), se snizi na nejdelsi MENSI, ktera se vejde (stejna zasada jako snizeni poctu supliku / panelu: snizit, ne odebrat); nevejde-li se
    ani nejkratsi, zustane nejkratsi (1190) a nasledne plati puvodni problem `panel_nevejde` s jeji sirkou / vyskou."""
    pozad = _delka_int(p["panely_delka"])
    if p["panely"] and p["stojky"]:
        for d in sorted((x for x in PANEL_DELKY if x <= pozad), reverse=True):
            pg = _pg_nebo_none(d)
            if pg is None:
                continue
            rez = _rezim_opory(p, n_pol, zl, zr, zm, d) if stredni else None
            if _sloupcu_panelu(zl, zr, zm, rez, d) >= 1 and _rad_panelu(pg, volna_vyska) >= 1:
                return d, rez
        pozad = min(PANEL_DELKY)
    return pozad, (_rezim_opory(p, n_pol, zl, zr, zm, pozad) if stredni else None)


def _typy_panelu(p, n_pol, zl, zr, zm, stredni, volna_vyska):
    """[{delka, sirka, vyska, vejde, vejde_sirka, vejde_vyska, min_sirka, min_sirka_nohy, usek, min_stojky}] pro VSECHNY delky panelu v dane konstrukci (`vejde` = aspon jeden panel teto delky se mezi
    stojky vejde na sirku i na vysku; nabidka delek v UI, delka bez GLB v katalogu se vynechava)."""
    out = []
    P = _P()
    for d in PANEL_DELKY:
        pg = _pg_nebo_none(d)
        if pg is None:
            continue
        rez = _rezim_opory(p, n_pol, zl, zr, zm, d) if stredni else None
        v_s, v_v = _sloupcu_panelu(zl, zr, zm, rez, d) >= 1, _rad_panelu(pg, volna_vyska) >= 1
        out.append({"delka": d, "sirka": round(pg["s"], 3), "vyska": round(pg["v"], 3), "vejde": v_s and v_v, "vejde_sirka": v_s, "vejde_vyska": v_v,
                    "usek": int(math.ceil(pg["s"] + 2 * PANEL_MEZERA)), "min_sirka": int(math.ceil(pg["s"] + 2 * PANEL_MEZERA + 2 * P)),
                    "min_sirka_nohy": int(math.ceil(2 * (pg["s"] + 2 * PANEL_MEZERA) + 3 * P)),
                    "min_stojky": int(math.ceil(PANEL_ODSTUP_OD_PRICKY + pg["v"] + 2 * PANEL_MEZERA + 2 * P))})
    return out


def _sse():
    """Modul SSE stolu (system 41); import az pri pouziti (stul_sse importuje tenhle modul)."""
    import stul_sse
    return stul_sse


def _hpol():
    """Modul horni police mezi zadnimi stojkami (api/stul_hpolice.py); import az pri pouziti (modul importuje tenhle)."""
    import stul_hpolice
    return stul_hpolice


def _je_sse(p):
    """Patri parametry `p` (normalizovane i surove) systemu SSE (41)?"""
    s_ = (p or {}).get("system", SYSTEM_VYCHOZI)
    try:
        return over_system(s_) == SYSTEM_SSE
    except StulChyba:
        return False


def _sestav_jadro(p, meze=False):
    """Dily stolu pro normalizovane parametry `p` v JEJICH SYSTEMU (`p["system"]`, chybi-li, 30); viz _sestav_jadro_systemu. System SSE (41) ma vlastni jadro (stul_sse.sestav)."""
    with _v_systemu(p.get("system", SYSTEM_VYCHOZI)):
        if SYSTEMY[_SYSTEM.get()].get("sse"):
            return _sse().sestav(p, meze)
        return _sestav_jadro_systemu(p, meze)


def _sestav_jadro_systemu(p, meze=False):
    """Vytvori dily stolu pro uz normalizovane parametry `p` (bez automatickeho odebirani prislusenstvi - viz sestav_stul). `meze=True` navic spocita PRESNE meze delky
    vzper (`vzpera_meze` {hodnota, min, max, vejde}; jinak jen {hodnota, vejde} - uplne hledani je drahe a potrebuje ho jen jezdec v UI, viz vzpera_meze())."""
    p = dict(p)
    if p["navlek"] and _SYSTEM.get() in NAVLEK_SYSTEMY:           # navlek nahrazuje kolecka i patky (i pri primem volani jadra bez normalizace)
        p["kolecka"], p["patky"] = False, False
    sab = list(sablona())
    sab[BOX] = {**sab[BOX], "part_id": SUPLIK_PARTY[int(p["suplik_pocet"])]}          # dil boxu podle poctu supliku (box je v sablone #577 dvojsuplik 4930); vsechny dalsi vypocty (strop polic, poloha, kolize) jedou nad nim
    dD, dW, dH = p["hloubka"] - 800.0, p["sirka"] - 1200.0, p["vyska"] - 840.0
    aktivni = _aktivni(p)
    ext = p["stojky"]                              # nastavba zadnich nohou = zadni stojky (Robert: zadni nohy se zkrati jen kdyz je vypnuty tento prepinac)
    stredni = p["sirka"] > prah_sirky()
    bocni_profil = p["hloubka"] > prah_hloubky()

    # ----- kotvy v novych souradnicich -----
    nast = p["stojky_vyska"]                       # vyska zadnich stojek nad rovinou desky (Robert 2026-10-05: nastavitelna; sablona 1073)
    xf = sab[NOHA_PL]["position"][0]
    xr = sab[NOHA_ZL]["position"][0] + dD
    zl = sab[NOHA_PL]["position"][2]
    zr = sab[NOHA_PP]["position"][2] + dW
    zc = (zl + zr) / 2.0
    yw = sab[ZRAIL_PRAC_PRED]["position"][1] + dH              # osa pracovniho ramu
    ys0 = sab[XRAIL_POL_L]["position"][1]                      # osa ramu police v sablone (pevna vyska 330 mm)
    ys = min(ys0, yw - (_P() + 30.0))                          # nizka deska: rám police nesmi byt nad pracovnim ramem; horni lico ramu police 30 mm pod spodkem pracovniho ramu (system 30: osy 60 mm od sebe)
    podlaha_ = sab[KOLECKA[0]]["position"][1] - glb_bbox("product_4916")[1][1]          # podlaha (spodek kolecka)
    # ----- NAVLEK NOHOU (Robert 2026-10-05; viz hlavicka modulu): delka se orizne na nejvetsi mozne pro vysku stolu, horni konec jeklu a nejnizsi osa ramu police nad nim -----
    navlek = bool(p["navlek"]) and _SYSTEM.get() in NAVLEK_SYSTEMY
    navlek_meze = None
    navlek_vrch = None                                         # y horniho konce jeklu (podlaha + priruba zaslepky + delka)
    ys_navlek = None                                           # nejnizsi povolena osa ramu police: NAVLEK_MEZERA_NAD + pul profilu nad hornim koncem jeklu
    if navlek:
        lim_rama = yw - _H() - NAVLEK_MEZERA_NAD - podlaha_ - NAVLEK_PRIRUBA               # jekl + NAVLEK_MEZERA_NAD zustane pod spodkem pracovniho ramu
        lim_police = (yw - (_P() + 30.0)) - _H() - NAVLEK_MEZERA_NAD - podlaha_ - NAVLEK_PRIRUBA      # ... a pod nejnizsi policí / bocnimi pricky police (osa nejvyse yw - (P + 30))
        lim = min(lim_rama, lim_police) if (p["police"] >= 1 or bocni_profil) else lim_rama
        d_lo, d_hi = float(ROZSAH["navlek_delka"][0]), float(ROZSAH["navlek_delka"][1])
        d_max = min(d_hi, math.floor(lim / NAVLEK_KROK + 1e-9) * NAVLEK_KROK)
        vejde = d_max >= d_lo
        if vejde:
            p["navlek_delka"] = float(min(p["navlek_delka"], d_max))
        navlek_meze = {"hodnota": float(p["navlek_delka"]), "min": d_lo, "max": float(d_max) if vejde else d_lo, "vejde": bool(vejde),
                       "chybi_mm": float(max(0.0, d_lo - lim)), "horni_mm": float(p["navlek_delka"]) + NAVLEK_PRIRUBA}      # chybi_mm: o kolik by musel byt stul vyssi, aby se vesel navlek 200 mm; horni_mm: vyska horniho konce jeklu nad podlahou
        navlek_vrch = podlaha_ + NAVLEK_PRIRUBA + float(p["navlek_delka"])
        ys_navlek = navlek_vrch + NAVLEK_MEZERA_NAD + _H()
        ys = max(ys, ys_navlek)
    # vice polic (Robert: libovolny pocet, min. 100 mm volne mezi nimi): nejnizsi police zustava (330 mm), dalsi se rozlozi rovnomerne
    # nahoru az po strop = spodek supliku (jsou-li) nebo spodek pracovniho ramu, minus 100 mm a minus deska + rám police
    strop = (_aabb(sab[BOX])[0][1] + dH) if p["suplik"] else (yw - _H())
    y_nahore = strop - MEZERA_POLIC - (_H() + DESKA_TLOUSTKA)
    n_max = max(1, 1 + int((y_nahore - ys) // roztec_polic_min())) if y_nahore > ys else 1
    n_pol = min(p["police"], n_max)
    p["police"] = n_pol
    if not n_pol:
        p["police_deska"] = True                   # bez spodnich polic volba 'bez desky' nic nedela: ucinne parametry maji jednu podobu
    hladiny_auto = ([ys + i * (y_nahore - ys) / (n_pol - 1) for i in range(n_pol)] if n_pol >= 2 else [ys])
    h_min_police = podlaha_ + _sd()["police_min_od_podlahy"]
    if ys_navlek is not None:
        h_min_police = max(h_min_police, ys_navlek)            # police (i rucne zadane vysky) nejnize nad navlekem
    hladiny, police_meze = _vysky_polic(p, n_pol, hladiny_auto, yw - _H(), strop, h_min_police)
    ys = hladiny[0]                                            # nejnizsi police (vsechny dily jejiho ramu se posouvaji o ys - ys0)
    yt = sab[XRAIL_TOP_L]["position"][1] + dH                  # osa horniho ramu

    clenove = {}          # klic -> clen (insertion order = poradi vystupu)
    spojky = {}           # klic -> dict(spojka)
    konce_ocek = {}       # klic -> (minus, plus) ocekavane dosednuti koncu profilu

    stred0 = {i: np.array(sab[i]["position"], float) for i in range(50)}

    # ----- 1) dily sablony s linearnimi pravidly -----
    for i in range(50):
        if i in SPOJKY or i not in aktivni:
            continue
        c = sab[i]
        pos = np.array(c["position"], float)
        scale = list(c["scale"])
        pr = R.get(i)
        if pr:
            pos[0] += _lin(pr["sx"], dD, dW, dH) if "sx" in pr else 0
            pos[1] += _lin(pr["sy"], dD, dW, dH) if "sy" in pr else 0
            pos[2] += _lin(pr["sz"], dD, dW, dH) if "sz" in pr else 0
            if "ln" in pr and c["part_id"] in PROFIL_PARTS:
                scale[1] = (1000.0 * c["scale"][1] + _lin(pr["ln"], dD, dW, dH)) / 1000.0
        if i in (XRAIL_POL_L, XRAIL_POL_P, ZRAIL_POL_PRED, ZRAIL_POL_ZAD):
            pos[1] += ys - ys0
        druh = "profil" if c["part_id"] in PROFIL_PARTS else ("deska" if i in DESKY else "prisl")
        clenove[("t", i)] = _clen(c["part_id"], c["quaternion"], scale, pos, druh, src=i)

    # horni ram (LED: ramena, pricka, svitidlo) jede s vrchem zadnich stojek: stojku lze zkracovat i natahovat (Robert 2026-10-05)
    dy_top = nast - (sab[NOHA_ZL]["position"][1] + 1000.0 * sab[NOHA_ZL]["scale"][1] / 2.0 - (sab[NOHA_PL]["position"][1] + 1000.0 * sab[NOHA_PL]["scale"][1] / 2.0))
    if dy_top:
        for i_top in (XRAIL_TOP_L, XRAIL_TOP_P, ZRAIL_TOP, LED):
            if ("t", i_top) in clenove:
                clenove[("t", i_top)]["pos"][1] += dy_top

    # horni ram (LED): hloubka 560, nejvyse hloubka stolu; zadni konec zustava na zadni noze
    hl_top0 = 1000.0 * sab[XRAIL_TOP_L]["scale"][1]
    hl_top = p["led_rameno"]                       # Robert: delka ramene od zadnich stojek smerem k telu je nastavitelna
    top_zkr = hl_top0 - hl_top                     # > 0 = kratsi nez v sablone (predni konec couva dozadu), < 0 = delsi
    for i in (XRAIL_TOP_L, XRAIL_TOP_P):
        if ("t", i) in clenove:
            clenove[("t", i)]["pos"][0] += top_zkr / 2.0
            clenove[("t", i)]["scale"][1] = hl_top / 1000.0
    if ("t", ZRAIL_TOP) in clenove:
        clenove[("t", ZRAIL_TOP)]["pos"][0] += top_zkr
    x_led = top_zkr                                              # predni konec horniho ramu couva dozadu

    # suplikovy box a jeho dve pricky pod deskou se posouvaji spolecne. Vychozi poloha (posun 0) se u uzsiho stolu SAMA posune tak, aby
    # box mel od nohou aspon 30 mm z kazde strany (Robert); rucne zadany posun se nemeni (kolize -> nabidka smazani, ne oprava)
    posun = p["suplik_posun"]
    if posun == 0 and p["suplik"]:
        b_lo, b_hi = _aabb(sab[BOX])
        smin = (zl + _H() + odstup_od_nohou()) - (b_lo[2] + dW)
        smax = (zr - _H() - odstup_od_nohou()) - (b_hi[2] + dW)
        if smin <= smax:
            posun = min(smax, max(smin, 0.0))
    # SUPLIKY VLEVO (Robert 2026-10-04: "nech lze prehodit supliky zprava doleva"): box se zrcadli kolem svisle roviny uprostred stolu; `suplik_posun` se pak meri od LEVE nohy
    # (kladne = k leve noze), tj. stejny odstup od vnejsi nohy na zvolene strane. Fyzicky posun od sablony: vpravo S = posun, vlevo S = K - posun (K = zl + zr - 2 * stred boxu v sablone).
    suplik_K = 0.0
    if p["suplik"] and p["suplik_vlevo"]:
        b_lo0, b_hi0 = _aabb(sab[BOX])
        suplik_K = (zl + zr) - ((b_lo0[2] + b_hi0[2]) + 2.0 * dW)
    posun_fyz = (suplik_K - posun) if (p["suplik"] and p["suplik_vlevo"]) else posun
    if posun_fyz:
        for i in (BOX, XRAIL_BOX1, XRAIL_BOX2):
            if ("t", i) in clenove:
                clenove[("t", i)]["pos"][2] += posun_fyz

    # drzak PET lahve: posun po noze SVISLE (Robert 2026-10-04); meze viz _pet_meze
    if ("t", PET) in clenove and p["pet_posun"]:
        clenove[("t", PET)]["pos"][1] += p["pet_posun"]

    # nohy: dolni konec = kolecko (z sablony) nebo podlaha; horni = rovina desky (+ nastavba)
    horni_pred0 = sab[NOHA_PL]["position"][1] + 1000.0 * sab[NOHA_PL]["scale"][1] / 2.0
    horni_zad0 = sab[NOHA_ZL]["position"][1] + 1000.0 * sab[NOHA_ZL]["scale"][1] / 2.0
    dolni0 = sab[NOHA_PL]["position"][1] - 1000.0 * sab[NOHA_PL]["scale"][1] / 2.0
    nastavba = horni_zad0 - horni_pred0                          # vyska stojek nad rovinou desky v sablone (1073)
    podlaha = sab[KOLECKA[0]]["position"][1] - glb_bbox("product_4916")[1][1]      # spodek kolecka = podlaha
    horni_pred = horni_pred0 + dH
    p["patky"] = bool(p["patky"]) and not p["kolecka"] and not navlek           # patky jen bez koleček (s kolecky nema smysl) a bez navleku
    if navlek:
        vyska_konce = NAVLEK_PRIRUBA + p["navlek_delka"] - NAVLEK_ZASUN             # spodek PROFILU nohy: priruba zaslepky jeklu + (delka jeklu - zasun nohy do jeklu)
    else:
        vyska_konce = (_sd()["patka_delka"] - _sd()["patka_zasun"]) if p["patky"] else _sd()["zaslepka_vyska"]      # co je pod koncem nohy: viditelna cast patky / priruba zaslepky
    dolni = dolni0 if p["kolecka"] else podlaha + vyska_konce

    def nastav_nohu(clen, zadni):
        horni = horni_pred + (nast if (zadni and ext) else 0.0)
        clen["pos"][1] = (horni + dolni) / 2.0
        clen["scale"][1] = (horni - dolni) / 1000.0

    for i in (NOHA_PL, NOHA_PP, NOHA_ZL, NOHA_ZP):
        nastav_nohu(clenove[("t", i)], i in (NOHA_ZL, NOHA_ZP))

    # STREDNI OPORA (sirka > prah): poloha osy `zm` a rezim (noha / ram) - desky se u ni DELI (formaty tabuli laminodesky, Robert 2026-10-05)
    zm = None
    rezim = None
    if stredni:
        zm_rel = p["stredni_noha"] if p["stredni_noha"] is not None else (zr - zl) / 2.0
        zm_min, zm_max = stredni_noha_meze(p["sirka"])
        if zm_min > zm_max:                  # (jen u mensi tabule nez 2 x sirka stolu) zadna poloha opory nevyhovuje obema castem desky: poloha se zkontroluje jen proti nohám, deska mimo tabuli ohlasi problem `deska_mimo_tabuli`
            zm_min, zm_max = min_odstup_stredni_noha(), (zr - zl) - min_odstup_stredni_noha()
        if p["stredni_noha"] is not None and not zm_min - 1e-6 <= zm_rel <= zm_max + 1e-6:
            raise StulChyba(f"stredni_noha {zm_rel:.0f} mm: musi byt aspon {min_odstup_stredni_noha():.0f} mm od kazde krajni nohy a obe casti desky se musi vejit do tabule "
                            f"{max_delka_desky():.0f} mm (pripustno {zm_min:.0f} az {zm_max:.0f})", "mimo_rozsah")
        zm = zl + zm_rel
    volna_vyska_pan = (horni_pred + (nast if ext else 0.0)) - (yw + _H() + PANEL_ODSTUP_OD_PRICKY) - _P()          # misto na zadnich stojkach nad spodni polohou panelu (bez horniho profilu): kolik radu panelu se vejde
    delka_panelu, rezim = _delka_panelu_ef(p, n_pol, zl, zr, zm, stredni, volna_vyska_pan)       # EFEKTIVNI delka panelu (zvolena, nebo nejdelsi mensi, ktera se vejde) a rezim stredni opory pro ni
    p["panely_delka"] = float(delka_panelu)

    # desky: stred (pravidla) + rozmer; GLB desky je 1000 x 1000 x 18, rozmer dava scale
    dP = p["presah"] - 30.0                                    # zmena presahu desky vpredu oproti sablone (zadni hrana zustava)
    deska_zkr = _sd()["deska_zkraceni"]                        # system 40: obe desky o 10 mm kratsi (zadni hrana na lici zadnich noh)
    dZ = deska_zadni_pokracovani(_sd(), ext)                   # bez zadnich stojek pracovni deska pokracuje dozadu a prekryva zadni svisle profily (zadni hrana v rovine jejich zadniho lice)
    for i, rozmer_d in ((DESKA_PRAC, 800.0 - deska_zkr + dD + dP + dZ), (DESKA_POLICE, 650.0 - deska_zkr + dD)):
        if ("t", i) not in clenove:
            continue
        cast = sab[i]
        lo, hi = glb_bbox(cast["part_id"])
        lc = (lo + hi) / 2.0
        Rm = kvat_na_matici(cast["quaternion"])
        s0 = np.array(cast["scale"], float)
        stred_sv0 = np.array(cast["position"], float) + Rm @ (s0 * lc)
        stred_sv1 = stred_sv0 + np.array([_lin(R[i]["sx"], dD, dW, dH), _lin(R[i]["sy"], dD, dW, dH),
                                          _lin(R[i]["sz"], dD, dW, dH)])
        if i == DESKA_POLICE:
            stred_sv1[1] += ys - ys0
        if i == DESKA_PRAC:
            stred_sv1[0] -= dP / 2.0                            # predni hrana couva dopredu, stred o polovinu
            stred_sv1[0] += dZ / 2.0                            # zadni hrana couva dozadu (bez zadnich stojek), stred o polovinu
        sirka_desky_i = 1200.0 + dW
        if i == DESKA_POLICE and bocni_profil:
            sirka_desky_i -= 2.0 * bok_kraceni_desky()                # deska police lezi UVNITR ramu: svisly profil bocnice (hloubka > 900) ji uz nezasahne
        s1 = np.array([rozmer_d / 1000.0, sirka_desky_i / 1000.0, s0[2]])
        clenove[("t", i)]["scale"] = s1.tolist()
        clenove[("t", i)]["pos"] = stred_sv1 - Rm @ (s1 * lc)

    # vyrezy v pracovni desce: deska se nahradi souborem obdelnikovych kusu kolem otvoru (cena zustava ceny CELE desky)
    vyrezy = []
    if ("t", DESKA_PRAC) in clenove and any(p[f"vyrez{n}"] for n in range(1, MAX_VYREZU + 1)):
        cast = sab[DESKA_PRAC]
        lo_d, hi_d = _aabb({"part_id": cast["part_id"], "quaternion": clenove[("t", DESKA_PRAC)]["quaternion"],
                            "scale": clenove[("t", DESKA_PRAC)]["scale"], "position": clenove[("t", DESKA_PRAC)]["pos"]})
        sc_p = clenove[("t", DESKA_PRAC)]["scale"]
        cx_p, cz_p = float(lo_d[0] + hi_d[0]) / 2.0, float(lo_d[2] + hi_d[2]) / 2.0
        X0, X1, Z0, Z1 = cx_p - 500.0 * sc_p[0], cx_p + 500.0 * sc_p[0], cz_p - 500.0 * sc_p[1], cz_p + 500.0 * sc_p[1]          # NOMINALNI rozmery (mesh desky neni presne 1000 mm: sum ~0,005 mm)
        y_dno_desky = float(lo_d[1])                              # spodek pracovni desky (police pod otvorem se meri od nej)
        for n in range(1, MAX_VYREZU + 1):
            if p[f"vyrez{n}"]:
                x0, z0 = X0 + p[f"vyrez{n}_x"], Z0 + p[f"vyrez{n}_z"]
                vyrezy.append({"n": n, "x0": x0, "x1": x0 + p[f"vyrez{n}_d"], "z0": z0, "z1": z0 + p[f"vyrez{n}_w"]})
        kusy = _rozloz_desku(X0, X1, Z0, Z1, [(v["x0"], v["x1"], v["z0"], v["z1"]) for v in vyrezy])
        lc_d = (glb_bbox(cast["part_id"])[0] + glb_bbox(cast["part_id"])[1]) / 2.0
        Rm_d = kvat_na_matici(cast["quaternion"])
        sc_d = clenove[("t", DESKA_PRAC)]["scale"]
        y_stred = float((lo_d[1] + hi_d[1]) / 2.0)
        puvodni = clenove[("t", DESKA_PRAC)]
        for k_, (xa, xb, za, zb) in enumerate(kusy):
            s_k = np.array([(xb - xa) / 1000.0, (zb - za) / 1000.0, sc_d[2]])
            stred_k = np.array([(xa + xb) / 2.0, y_stred, (za + zb) / 2.0])
            clen = _clen(cast["part_id"], cast["quaternion"], s_k.tolist(), stred_k - Rm_d @ (s_k * lc_d), "deska", src=DESKA_PRAC)
            if k_ == 0:
                clen["celek"] = [round(800.0 - deska_zkr + dD + dP + dZ, 3), round(1200.0 + dW, 3)]        # cena: cela deska (rozmery pred rozrezanim)
                clenove[("t", DESKA_PRAC)] = clen
            else:
                clen["kus"] = True
                clenove[("kus", k_)] = clen

    # DELENI DESEK u stredni opory (Robert 2026-10-05): pracovni deska i police se deli v ose stredni nohy / vestaveneho ramu na dve desky (kazda se musi vejit do tabule laminodesky).
    # Pracovni deska a police u stredni nohy na sebe NAVAZUJI bez mezery; spodni police u vestaveneho ramu se u ramu zkracuji (svisly profil ramu prochazi rovinou police).
    if zm is not None:
        _deli_desku_u_opory(clenove, sab, DESKA_PRAC, ("t", DESKA_PRAC), "kus", zm, 0.0, vyrezy)
        if ("t", DESKA_POLICE) in clenove:
            _deli_desku_u_opory(clenove, sab, DESKA_POLICE, ("t", DESKA_POLICE), "kusp", zm, 2.0 * (_H() + RAM_VULE_VYREZU) if rezim == "ram" else 0.0)

    # ----- 2) strukturalni doplnky -----
    odvozene_spojky = []          # (src spojka, mapa vlastniku stary->novy klic, rotace, uzel_stary_vlastnici)

    # 2a) svitidla LED: POCET i POLOHA jsou RUCNI volba (Robert 2026-10-08: "svitidla se maji pridavat jen rucne a mohla se posouvat podel profilu"); vychozi = jedno svitidlo, polohy None = svitidla
    #     tesne vedle sebe, skupina vystredena jako dosud. PANELY se stavi az po strednich nohach (viz 2b+)
    led_stav = None
    if (p["led"] and p["stojky"] and p["led_svetlo"]):
        d_led = _led_delka_int(p["led_delka"])                       # delka svitidel (vsechna stejna): dil katalogu zvolene delky, rozteč = delka jeho tělesa z GLB (1200: 1247, 600: 647 mm)
        s_led = led_telo_dilu(LED_TYPY[d_led])
        n_max_led = led_max_pocet(p["sirka"], s_led)                 # nejvic svitidel, ktera se vejdou (soucet delek <= sirka + LED_PREVIS)
        n_l = min(int(p["led_pocet"]), n_max_led)
        zakl = clenove[("t", LED)]
        zakl["part_id"] = LED_TYPY[d_led]                            # clen sablony nese dil 1200; jina delka = jiny dil se STEJNYM otocenim a polohou (stejny stred bboxu)
        zakl["pos"][0] += x_led
        b_lo_l, b_hi_l = _aabb({"part_id": zakl["part_id"], "quaternion": zakl["quaternion"], "scale": zakl["scale"], "position": zakl["pos"]})
        c0_led = float((b_lo_l[2] + b_hi_l[2]) / 2.0)                # stred JEDNOHO svitidla ve vychozi poloze (sablona; neni presne ve stredu stolu)
        z_lo_led, z_hi_led = float(zl - _H()), float(zr + _H())      # vnejsi okraje stolu = rozsah pricneho profilu nad LED
        zc_led = (z_lo_led + z_hi_led) / 2.0                         # osa stolu (referencni nula poloh led_z<k>)
        rozpeti_led = (z_hi_led - z_lo_led) + LED_PREVIS
        proveditelne = bool(n_l * s_led <= rozpeti_led + 1e-9 and (z_hi_led - z_lo_led) >= MIN_PODIL_PROFILU_LED * s_led)          # stul uzky pro svitidlo: dosavadni chovani (auto poloha, kontroly ohlasi problem)
        zad_led = [(zc_led + float(p[f"led_z{_k + 1}"])) if (proveditelne and p[f"led_z{_k + 1}"] is not None) else None for _k in range(n_l)]
        v_led, auto_led, mez_stred = led_polohy(n_l, s_led, c0_led, z_lo_led, z_hi_led, zad_led, rozpeti_led)
        if not proveditelne:
            v_led = list(auto_led)
        rel_led = []                                                 # efektivni poloha kazdeho svitidla v mm od osy stolu na mrizce 0,1 mm (stejna hodnota se pouzije pro geometrii i pro parametry)
        for k_led in range(n_l):
            if abs(v_led[k_led] - auto_led[k_led]) < 0.05:
                v_led[k_led] = auto_led[k_led]
                rel_led.append(None)
            else:
                rel_led.append(round(v_led[k_led] - zc_led, 1))
                v_led[k_led] = zc_led + rel_led[-1]
        z_base_led = float(zakl["pos"][2])
        zakl["pos"][2] = z_base_led + (v_led[0] - c0_led)
        for k in range(1, n_l):
            kl = _klon(sab, LED, np.array([zakl["pos"][0], zakl["pos"][1], z_base_led + (v_led[k] - c0_led)]))
            kl["part_id"] = LED_TYPY[d_led]
            clenove[("led", k)] = kl
        p["led_pocet"] = n_l                                         # efektivni hodnoty (pozadovany pocet / poloha se mohly orezat): jedna konfigurace = jedna kanonicka podoba = jeden hash
        for k_led in range(LED_MAX):
            p[f"led_z{k_led + 1}"] = rel_led[k_led] if k_led < n_l else None
        led_stav = {"n": n_l, "n_max": n_max_led, "telo": s_led, "c0": c0_led, "zc": zc_led, "z_lo": z_lo_led, "z_hi": z_hi_led, "rozpeti": rozpeti_led, "proveditelne": proveditelne,
                    "v": [float(x) for x in v_led], "auto": [float(x) for x in auto_led], "rel": rel_led, "stred_meze": (float(mez_stred[0]), float(mez_stred[1]))}
    else:
        p["led_delka"] = float(LED_DELKA_VYCHOZI)                    # bez svitidla (vypnute LED / stojky / svitidlo, nebo odebrane, protoze se nevejde) delka, pocet ani poloha nic nedelaji
        p["led_pocet"] = 1
        for k_led in LED_PARAMETRY_Z:
            p[k_led] = None

    # 2b) stredni opora (sirka > prah): noha / vestaveny ram (poloha zm a rezim jsou spocitane vyse, pred deskami - desky se deli v ose opory)
    if rezim == "noha":
        fm = _klon(sab, NOHA_PP, [xf, 0, zm])
        rm = _klon(sab, NOHA_ZP, [xr, 0, zm])
        nastav_nohu(fm, False)
        nastav_nohu(rm, True)
        clenove["FM"], clenove["RM"] = fm, rm
        if p["kolecka"]:
            # Robert: maji-li nohy kolecka, musi je mit i stredni nohy (stejne odsazeni kolecka od osy nohy jako u prave strany)
            for klic, kol_src, noha_src in (("kolecko_FM", 27, NOHA_PP), ("kolecko_RM", 28, NOHA_ZP)):
                nz = np.array(sab[kol_src]["position"], float) - np.array(sab[noha_src]["position"], float)
                kolecko = _klon(sab, kol_src, [(xf if kol_src == 27 else xr) + nz[0], sab[kol_src]["position"][1], zm + nz[2]])
                clenove[klic] = kolecko

        def rozdel(klic_t, i, z_a, z_b, z_m, stavi_sloupek=None):
            """Rozdeli prickou i (osa Z) na dva useky mezi krajnimi licemi a stredni nohou (+-15)."""
            c = clenove[("t", i)]
            levy = (z_a + _H(), z_m - _H())
            pravy = (z_m + _H(), z_b - _H())
            c["pos"][2] = (levy[0] + levy[1]) / 2.0
            c["scale"][1] = (levy[1] - levy[0]) / 1000.0
            pr = _klon(sab, i, c["pos"].copy())
            pr["pos"][2] = (pravy[0] + pravy[1]) / 2.0
            pr["scale"][1] = (pravy[1] - pravy[0]) / 1000.0
            clenove[("seg", i)] = pr
            return ("t", i), ("seg", i)

        for i in (ZRAIL_PRAC_PRED, ZRAIL_PRAC_ZAD, ZRAIL_POL_PRED, ZRAIL_POL_ZAD):
            if ("t", i) in clenove:
                rozdel(("t", i), i, zl, zr, zm)
        # stredni X pricky: pracovni uroven, uroven police, horni ram
        base = clenove[("t", XRAIL_PRAC_L)]
        xp = _klon(sab, XRAIL_PRAC_L, [base["pos"][0], yw, zm])
        xp["scale"] = list(base["scale"])
        clenove["XM_prac"] = xp
        if p["police"]:
            base = clenove[("t", XRAIL_POL_L)]
            xs = _klon(sab, XRAIL_POL_L, [base["pos"][0], ys, zm])
            xs["scale"] = list(base["scale"])
            clenove["XM_pol"] = xs
        if (p["led"] and p["stojky"]):
            xt = _klon(sab, XRAIL_TOP_L, clenove[("t", XRAIL_TOP_L)]["pos"].copy())
            xt["pos"][2] = zm
            xt["scale"] = list(clenove[("t", XRAIL_TOP_L)]["scale"])
            clenove["XM_top"] = xt
        # spojky stredni nohy: z analogickych spoju sablony (stejny tvar spoje = stejna spojka)
        odvozene_spojky += [
            (33, {4: "FM", 5: ("t", ZRAIL_PRAC_PRED)}), (30, {3: "FM", 5: ("seg", ZRAIL_PRAC_PRED)}),
            (32, {3: "FM", 10: "XM_prac"}), (41, {10: "XM_prac", 12: "RM"}),
        ]
        if p["police"]:
            odvozene_spojky += [
                (47, {13: "RM", 18: ("t", ZRAIL_POL_ZAD)}), (44, {12: "RM", 18: ("seg", ZRAIL_POL_ZAD)}),
                (31, {3: "FM", 9: "XM_pol"}),
            ]
        if (p["led"] and p["stojky"]):
            odvozene_spojky += [(43, {12: "RM", 16: "XM_top"}), (49, {16: "XM_top", 17: ("t", ZRAIL_TOP)})]

    elif rezim == "ram":
        # ----- 2b#) VESTAVENY RAM misto stredni nohy (Robert 2026-10-05; skica 3, 1. verze): zadne stredni nohy, vsechny podelniky (predni a zadni pricka desky a polic, pricky panelu...) jdou CELE.
        #       Ram uprostred sirky = horni pricka (osa X) od predniho podelniku desky po zadni (jako stredni pricka u nohy, 740 mm), dolni pricka (osa X) od predniho podelniku police po zadni
        #       (o 148 mm kratsi) a svisle profily (predni na predni podelnik police az pod horni prickou, zadni mezi zadnimi podelniky); dolni pricka drzi desku police.
        base = clenove[("t", XRAIL_PRAC_L)]
        xp = _klon(sab, XRAIL_PRAC_L, [base["pos"][0], yw, zm])
        xp["scale"] = list(base["scale"])
        clenove["XM_prac"] = xp
        x_pred_f = float(clenove[("t", ZRAIL_POL_PRED)]["pos"][0])             # predni podelnik police (150 mm za predni nohou)
        x_zad_f = float(clenove[("t", ZRAIL_POL_ZAD)]["pos"][0])
        clenove["XM_pol"] = _klon(sab, XRAIL_POL_L, [(x_pred_f + x_zad_f) / 2.0, ys, zm], delka=(x_zad_f - _H()) - (x_pred_f + _H()))
        odvozene_spojky += [(36, {5: ("t", ZRAIL_PRAC_PRED), 6: "XM_prac"}), (37, {5: ("t", ZRAIL_PRAC_PRED), 6: "XM_prac"}),          # predni konce pricek: jako pricky drzici supliky
                            (36, {5: ("t", ZRAIL_POL_PRED), 6: "XM_pol"}), (37, {5: ("t", ZRAIL_POL_PRED), 6: "XM_pol"})]
    # ----- 2b+) PANELY VSAZENE DO PROFILU (Robert 2026-10-05; skici ve Sdilenem disku): perforovany panel sedi MEZI zadnimi stojkami v jejich rovine, nad a pod nim je podelny profil (mezi stojkami),
    #       mezera 1 mm; podel kratkych stran panelu zadny profil neni (je tam stojka). Panely se pridavaji po jednom kuse: nejdriv vedle sebe (kazdy usek mezi stojkami max. 1 panel; mezi dvema
    #       panely je tedy plna stredni noha), pak dalsi rada nad (max. PANELY_MAX_RAD). Cele sestava (panely + profily + elektrozlab) se da posouvat po zadnich stojkach (`panely_posun`).
    panely_info = {"pocet": 0, "max": 0, "pozadovano": int(p["panely_pocet"]) if p["panely"] else 0, "sloupcu": 0, "radu": 0, "rezim": rezim, "min_sirka": None, "min_stojky": None, "posun_max": 0.0,
                   "posun_z": {"hodnota": 0.0, "min": 0.0, "max": 0.0}, "zaber": []}
    panely_klice = []
    stojky_min = float(ROZSAH["stojky_vyska"][0])                  # nejnizsi stojka: s panely tolik, aby se vesly (viz nize)
    if p["panely"] and p["stojky"]:
        pg = _panel_geometrie(delka_panelu)
        panely_info["delka"] = int(delka_panelu)
        panely_info["vyska_panelu"] = round(float(pg["v"]), 3)
        panely_info["typy"] = _typy_panelu(p, n_pol, zl, zr, zm, stredni, volna_vyska_pan)
        panely_info["min_sirka"] = int(math.ceil(pg["s"] + 2 * PANEL_MEZERA + 2 * _P()))
        panely_info["min_stojky"] = int(math.ceil(PANEL_ODSTUP_OD_PRICKY + pg["v"] + 2 * PANEL_MEZERA + 2 * _P()))       # jedna rada: profil + panel + profil, 2 mm nad zadni prickou
        vejde = [u for u in _pole_panelu(zl, zr, zm, rezim) if u[1] - u[0] >= pg["s"] + 2 * PANEL_MEZERA - 1e-6]
        ncols = len(vejde)
        y_nula = yw + _H() + PANEL_ODSTUP_OD_PRICKY               # spodni lico spodniho profilu pri posunu 0 = nad zadni prickou ramu desky (2 mm; nejsou spojene)
        y_vrch = horni_pred + (nast if ext else 0.0)             # vrch zadnich stojek (pod nim je rameno LED)
        krok = _P() + pg["v"] + 2.0 * PANEL_MEZERA
        rad_max = max(0, min(PANELY_MAX_RAD, int((y_vrch - y_nula - _P() + 1e-3) // krok)))          # 1e-3 mm: rozmery modelu maji sum rady 1e-4 mm (presne min. vyska stojek se musi vejit)
        cap = ncols * rad_max
        n_ef = max(0, min(int(p["panely_pocet"]), cap, PANELY_MAX))
        panely_info.update(max=cap, sloupcu=ncols, pocet=n_ef, rad_max=rad_max)
        p["panely_pocet"] = n_ef if n_ef else int(p["panely_pocet"])
        if n_ef:
            radu = -(-n_ef // ncols)
            panely_info["radu"] = radu
            posun_max = max(0.0, y_vrch - (y_nula + radu * krok + _P()))
            stojky_min = max(stojky_min, float(math.ceil(PANEL_ODSTUP_OD_PRICKY + radu * krok + _P() + float(p["panely_posun"]))))     # stojka musi unest pozadovane panely i s posunem
            posun = min(max(float(p["panely_posun"]), 0.0), posun_max)
            p["panely_posun"] = posun
            panely_info["posun_max"] = posun_max
            pozice = [divmod(idx, ncols) for idx in range(n_ef)]       # (rada, usek): nejdriv cela spodni rada zleva doprava, pak dalsi
            radu_v_useku = [0] * ncols
            for r_, c_ in pozice:
                radu_v_useku[c_] = max(radu_v_useku[c_], r_ + 1)
            for c_, (a_, b_, kl_, kr_) in enumerate(vejde):
                for k_ in (range(radu_v_useku[c_] + 1) if radu_v_useku[c_] else ()):          # usek bez panelu nema zadne profily (u 2 useku a 1 panelu je druhy usek prazdny)
                    yb = y_nula + posun + k_ * krok
                    kl_pr = ("panrail", c_, k_)
                    clenove[kl_pr] = _klon(sab, ZRAIL_PANEL, [xr, yb + _H(), (a_ + b_) / 2.0], delka=b_ - a_)
                    odvozene_spojky.append((42, {12: kl_, 14: kl_pr}))
                    odvozene_spojky.append((45, {13: kr_, 14: kl_pr}))
            # VODOROVNY POSUN panelu (Robert 2026-10-05: "panely chceme pohyblive, pokud maji mezeru mezi nohama"): spolecny pro vsechny panely (obsazene useky), kazdy panel zustane aspon PANEL_MEZERA od
            # noh (u stredni nohy z obou stran). Panel je vychozne vystredeny v useku mezi stojkami; mezera od kazde nohy pri posunu 0 = (usek - panel) / 2. Elektrozlab jede s panelem.
            ob_useky = [c_ for c_ in range(ncols) if radu_v_useku[c_]]
            volno_z = min(((vejde[c_][1] - vejde[c_][0]) - pg["s"]) / 2.0 - PANEL_MEZERA for c_ in ob_useky)
            lim_z = max(0.0, float(math.floor(volno_z + 1e-6)))                               # na CELE mm dolu: panel nikdy neprekroci mez (jezdec, uchyt i verejny slot jedou po 1 mm)
            dz = min(max(float(p["panely_z"]), -lim_z), lim_z) + 0.0                           # + 0.0: bez zaporne nuly
            p["panely_z"] = dz
            panely_info["posun_z"] = {"hodnota": dz, "min": -lim_z, "max": lim_z}
            panely_info["zaber"] = [{"mezera": float(((vejde[c_][1] - vejde[c_][0]) - pg["s"]) / 2.0), "levy": "levá noha" if vejde[c_][2] == ("t", NOHA_ZL) else "střední noha",
                                     "pravy": "pravá noha" if vejde[c_][3] == ("t", NOHA_ZP) else "střední noha"} for c_ in ob_useky]
            pos_pd = np.array(sab[PANEL_D]["position"], float)
            for r_, c_ in pozice:
                a_, b_ = vejde[c_][0], vejde[c_][1]
                cil = np.array([xr, y_nula + posun + _P() + PANEL_MEZERA + r_ * krok + pg["v"] / 2.0, (a_ + b_) / 2.0 + dz])
                klic_pan = ("pan", r_, c_)
                clenove[klic_pan] = _klon(sab, PANEL_D, pos_pd + (cil - pg["stred0"]))
                clenove[klic_pan]["part_id"] = pg["part"]                    # dil katalogu zvolene delky (stejne otoceni jako panel sablony)
                panely_klice.append(klic_pan)
    if not panely_klice:
        p["panely_z"] = 0.0                                          # bez panelu nema vodorovny posun smysl (do hashe se nepocita)
        p["panely_delka"] = float(PANEL_DELKA_VYCHOZI)               # ... ani delka panelu
    if ("t", ELZLAB) in clenove:
        elzlab_bez_opory = False
        if panely_klice:
            pg = _panel_geometrie(delka_panelu)
            lo_pan, hi_pan = _aabb({"part_id": clenove[panely_klice[0]]["part_id"], "quaternion": clenove[panely_klice[0]]["quaternion"], "scale": clenove[panely_klice[0]]["scale"],
                                    "position": clenove[panely_klice[0]]["pos"]})
            y_lo, z_lo = float(lo_pan[1] + pg["zlab_od_y"] + p["elzlab_y"]), float(lo_pan[2] + pg["zlab_od_z"] + p["elzlab_z"])
            x_zad = float(lo_pan[0])                                   # bez opory (zlab mimo panel i profily) zustane u predniho lica panelu
            dotyk = []
            for k_o, c_o in clenove.items():
                if not (k_o in panely_klice or (isinstance(k_o, tuple) and k_o[0] == "panrail") or k_o in (("t", NOHA_ZL), ("t", NOHA_ZP), "RM")):
                    continue
                lo_o, hi_o = _aabb({"part_id": c_o["part_id"], "quaternion": c_o["quaternion"], "scale": c_o["scale"], "position": c_o["pos"]})
                if min(hi_o[1], y_lo + pg["zlab"][1]) - max(lo_o[1], y_lo) > 0.5 and min(hi_o[2], z_lo + pg["zlab"][2]) - max(lo_o[2], z_lo) > 0.5:
                    dotyk.append(float(lo_o[0]))
            if dotyk:
                x_zad = min(dotyk)                                      # zlab se opre o nejpredni lico za nim (panel, profil nebo stojka)
            else:
                elzlab_bez_opory = True
            cil_z = np.array([x_zad - pg["zlab"][0] / 2.0, y_lo + pg["zlab"][1] / 2.0, z_lo + pg["zlab"][2] / 2.0])
            clenove[("t", ELZLAB)]["pos"] = np.array(sab[ELZLAB]["position"], float) + (cil_z - pg["zlab_stred0"])
            panely_info["zlab"] = {"y0": float(y_lo - p["elzlab_y"]), "z0": float(z_lo - p["elzlab_z"]), "rozmer": [float(v) for v in pg["zlab"]]}
        panely_info["elzlab_bez_opory"] = elzlab_bez_opory

    # ----- 2b++) HORNI POLICE MEZI ZADNIMI STOJKAMI (Robert 2026-10-07; api/stul_hpolice.py): ram z profilu mezi stojkami, deska / prepazky s uhelniky; vypnuta = beze zmeny -----
    hpolice_info = None
    hpolice_spojky = []                                          # spojky police se pridaji AZ NA KONEC odvozenych spojek: cislovani ostatnich se police nemeni
    if p["hpolice"] and p["stojky"]:
        hpolice_info = _hpol().postav({"p": p, "sab": sab, "clenove": clenove, "odvozene": hpolice_spojky, "zl": zl, "zr": zr, "zm": zm, "rezim": rezim, "xr": xr, "xf": xf,
                                       "y_deska": horni_pred + DESKA_TLOUSTKA, "y_vrch": horni_pred + (nast if ext else 0.0)})

    # 2b-) konce noh bez koleček: zaslepka (vzdy) nebo stavitelna patka pod kazdou nohou (i strednimi)
    if not p["kolecka"]:
        for kn in (("t", NOHA_PL), ("t", NOHA_PP), ("t", NOHA_ZL), ("t", NOHA_ZP), "FM", "RM"):
            if kn not in clenove:
                continue
            xn, zn = float(clenove[kn]["pos"][0]), float(clenove[kn]["pos"][2])
            if navlek:
                # navlek: jekl 40x40x2 stoji na prirube zaslepky (spodek jeklu = podlaha + 3 mm), osa jeklu = osa nohy; profil nohy v nem konci NAVLEK_ZASUN mm pod jeho hornim koncem (viz `dolni`)
                delka_n = float(p["navlek_delka"])
                clenove[("konec", kn, "navlek")] = _clen(NAVLEK_PART, (0.0, 0.0, 0.0, 1.0), [1.0, delka_n / 1000.0, 1.0], [xn, podlaha + NAVLEK_PRIRUBA + delka_n / 2.0, zn], "prisl", src=None)
                clenove[("konec", kn, "zasl")] = _clen(NAVLEK_ZASLEPKA, (-0.70710678, 0.0, 0.0, 0.70710678), [1.0, 1.0, 1.0], [xn, podlaha, zn], "prisl", src=None)      # jeklova zaslepka: priruba na podlaze, zatka nahoru do jeklu
            elif p["patky"]:
                # patka: pocatek = horni stred zavitu; zavit je patka_zasun mm v noze, zakladna (system 30: 75 mm pod pocatkem) stoji na podlaze
                clenove[("konec", kn)] = _clen(_sd()["patka"], (0.0, 0.0, 0.0, 1.0), [1.0, 1.0, 1.0], [xn, podlaha + _sd()["patka_delka"], zn], "prisl", src=None)
            else:
                # zaslepka: lokalni +Z = do profilu (zatka), vnejsi plocha z = 0 lezi na podlaze; rotace -90 st. kolem X (+Z -> +Y)
                clenove[("konec", kn)] = _clen(_sd()["zaslepka"], (-0.70710678, 0.0, 0.0, 0.70710678), [1.0, 1.0, 1.0], [xn, podlaha, zn], "prisl", src=None)

    # 2b') dalsi police (k >= 1): kopie cele skupiny police (deska, 2 podelne + 2 pricne pricky, stredni usek/pricka) posunute po vysce
    skupina_polic = [k_ for k_ in (("t", DESKA_POLICE), ("t", XRAIL_POL_L), ("t", XRAIL_POL_P), ("t", ZRAIL_POL_ZAD), ("t", ZRAIL_POL_PRED),
                                   ("seg", ZRAIL_POL_ZAD), ("seg", ZRAIL_POL_PRED), "XM_pol") if k_ in clenove] + [k_ for k_ in clenove if isinstance(k_, tuple) and k_[0] == "kusp"]
    polic_klice = {}
    for k in range(1, n_pol):
        dy = hladiny[k] - hladiny[0]
        mapa_k = {}
        for kl_ in skupina_polic:
            zdroj = clenove[kl_]
            nk = ("polic", k, kl_)
            clenove[nk] = {"part_id": zdroj["part_id"], "quaternion": zdroj["quaternion"], "scale": list(zdroj["scale"]),
                           "pos": zdroj["pos"] + np.array([0.0, dy, 0.0]), "druh": zdroj["druh"], "src": zdroj["src"]}
            for fl in ("celek", "kus", "vyrezu"):                                  # priznaky rozrezane desky police (vyrez pro svisly profil rámu) se kopiruji s deskou
                if fl in zdroj:
                    clenove[nk][fl] = zdroj[fl]
            mapa_k[kl_] = nk
        polic_klice[k] = mapa_k

    # 2b#') svisle profily vestaveneho ramu (po kopiich polic: potrebuji podelniky vsech polic): v kazde mezere mezi urovnemi (police, police, ..., pracovni ram) jeden ZADNI profil (mezi zadnimi
    #       podelniky v rovine stojek) a jeden PREDNI (na predni podelnik police az pod prickou; pod pracovni deskou pod horni prickou ramu)
    if rezim == "ram":
        urovne = [{"y": hladiny[0], "zad": ("t", ZRAIL_POL_ZAD), "pred": ("t", ZRAIL_POL_PRED), "pric": "XM_pol"}]
        for k in range(1, n_pol):
            mk = polic_klice[k]
            urovne.append({"y": hladiny[k], "zad": mk[("t", ZRAIL_POL_ZAD)], "pred": mk[("t", ZRAIL_POL_PRED)], "pric": mk["XM_pol"]})
        urovne.append({"y": yw, "zad": ("t", ZRAIL_PRAC_ZAD), "pred": None, "pric": "XM_prac"})
        for j in range(len(urovne) - 1):
            ya, yb = urovne[j]["y"], urovne[j + 1]["y"]
            dl_p = (yb - _H()) - (ya + _H())
            kz, kpf = ("ram", "pz", j), ("ram", "pf", j)
            clenove[kz] = _klon(sab, NOHA_PL, [xr, (ya + yb) / 2.0, zm], delka=dl_p)
            clenove[kpf] = _klon(sab, NOHA_PL, [x_pred_f, (ya + yb) / 2.0, zm], delka=dl_p)
            odvozene_spojky.append((43, {12: kz, 16: urovne[j + 1]["zad"]}, "ry90"))                      # svisly profil pod zadnim podelnikem (osa Z)
            odvozene_spojky.append((43, {12: kz, 16: urovne[j]["zad"]}, ("rx180", "ry90")))               # ... a na zadnim podelniku pod nim
            if urovne[j + 1]["pred"] is not None:
                odvozene_spojky.append((43, {12: kpf, 16: urovne[j + 1]["pred"]}, "ry90"))
            else:
                odvozene_spojky.append((43, {12: kpf, 16: urovne[j + 1]["pric"]}))                        # pod horni prickou ramu (osa X)
            odvozene_spojky.append((43, {12: kpf, 16: urovne[j]["pred"]}, ("rx180", "ry90")))

    # 2c) svisly profil doprostred kazde bocnice (hloubka > 900) - mezi VSEMI po sobe jdoucimi podelnymi pricky bocnice
    #     (spodni ramy polic + pracovni ram); pres kazdou policii by jinak prosel jeden dlouhy profil skrz pricky dalsich polic
    if bocni_profil:
        x_mid = (xf + xr) / 2.0
        for strana, (zs, leg_src, horni_x, dolni_x, analog) in {
            "L": (zl, NOHA_PL, XRAIL_PRAC_L, XRAIL_POL_L, (43, 12, 16)),
            "P": (zr, NOHA_PP, XRAIL_PRAC_P, XRAIL_POL_P, (46, 13, 15)),
        }.items():
            koleje = []
            if ("t", dolni_x) in clenove:
                koleje.append((hladiny[0], ("t", dolni_x)))
                for k in range(1, n_pol):
                    koleje.append((hladiny[k], polic_klice[k][("t", dolni_x)]))
            koleje.append((yw, ("t", horni_x)))
            a_spojka, a_noha, a_rail = analog
            for j in range(len(koleje) - 1):
                (y_a, klic_a_r), (y_b, klic_b_r) = koleje[j], koleje[j + 1]
                delka_s = (y_b - _H()) - (y_a + _H())
                kl = _klon(sab, leg_src, [x_mid, (y_a + y_b) / 2.0, zs], delka=delka_s)
                seg_klic = ("bok", strana, j)
                clenove[seg_klic] = kl
                odvozene_spojky.append((a_spojka, {a_noha: seg_klic, a_rail: klic_b_r}))
                odvozene_spojky.append((a_spojka, {a_noha: seg_klic, a_rail: klic_a_r}, "rx180"))

    # ----- 2c-45) STREDNI RADA NOH (system 45, hloubka > pravidlo `hloubka_stredni_noha`, vychozi HLOUBKA_STREDNI_NOHA = 1500; bot10, 2026-10-07): svisly profil doprostred bocnice (2c) stoji jen mezi pricky bocnice; od teto hloubky se
    #       prodlouzi AZ NA PODLAHU (stredni noha = segment od konce nohy / kolecka po spodni lico nejnizsi bocni pricky, konec jako u ostatnich noh) a pod podpery pracovni desky i kazde police
    #       prijde PRICKA pres sirku mezi obe stredni nohy. Pricka visi o jeden profil POD podperami (horni lico pricky = spodni lico podper), takze podpery (i stredni pricky sirky XM_*) pres ni
    #       jen prechazi a nic se nedeli; konce pricky dosedaji na boky svislych profilu (spojky 42 / 45 jako konce pricek panelu mezi zadnimi stojkami).
    rada_noh = bool(bocni_profil and _sd().get("hluboky") and p["hloubka"] > prah_hloubky_noha()
                    and (hladiny[0] - _H()) - dolni >= MIN_DELKA_STREDNI_NOHY - 0.01)          # velmi nizky stul (nejnizsi bocni pricka tesne nad podlahou, ~ vyska desky pod 190 mm): stredni noha aspon MIN_DELKA_STREDNI_NOHY se pod ni nevejde -> bez stredni rady (stul jako system 40)
    if rada_noh:
        top_nej = hladiny[0] - _H()                                    # spodni lico nejnizsi bocni pricky (police 0 nebo "postranni spodni" pricka u stolu bez police)
        for strana, (zs, leg_src, kol_src, dolni_x, analog) in {
            "L": (zl, NOHA_PL, 29, XRAIL_POL_L, (43, 12, 16)),
            "P": (zr, NOHA_PP, 27, XRAIL_POL_P, (46, 13, 15)),
        }.items():
            a_spojka, a_noha, a_rail = analog
            kn = ("bok", strana, "dno")
            clenove[kn] = _klon(sab, leg_src, [x_mid, (top_nej + dolni) / 2.0, zs], delka=top_nej - dolni)
            odvozene_spojky.append((a_spojka, {a_noha: kn, a_rail: ("t", dolni_x)}))                    # horni konec pod nejnizsi bocni pricku (jako horni konec svisleho profilu bocnice)
            if p["kolecka"]:
                nz = np.array(sab[kol_src]["position"], float) - np.array(sab[leg_src]["position"], float)            # stejne odsazeni kolecka od osy nohy jako u krajni nohy te strany
                clenove[("bok_kolecko", strana)] = _klon(sab, kol_src, [x_mid + nz[0], sab[kol_src]["position"][1], zs + nz[2]])
            elif p["patky"]:
                clenove[("konec", kn)] = _clen(_sd()["patka"], (0.0, 0.0, 0.0, 1.0), [1.0, 1.0, 1.0], [x_mid, podlaha + _sd()["patka_delka"], zs], "prisl", src=None)
            else:
                clenove[("konec", kn)] = _clen(_sd()["zaslepka"], (-0.70710678, 0.0, 0.0, 0.70710678), [1.0, 1.0, 1.0], [x_mid, podlaha, zs], "prisl", src=None)
        # pricky pres sirku: pracovni ram (pod podperami desky) a kazda police s deskou; konce na boky segmentu pod prislusnou bocni pricku (police 0: stredni noha, vyssi: svisly profil bocnice)
        n_urovni_bok = max(n_pol, 1)

        def _pricka_vejde(y_u, y_pod):         # pricka [y_u - P - H, y_u - H] (pod podperami) musi lezet nad dilem pod ni (+1 mm): nizky stul s policí tesne pod deskou na ni nema misto
            return (y_u - _P() - _H()) >= y_pod + 1.0
        urovne_rady = []
        for k in range(n_pol):
            y_pod = dolni if k == 0 else hladiny[k - 1] + _H() + DESKA_TLOUSTKA              # police 0: stredni noha od dolniho konce; vyssi police: deska nizsi police
            if _pricka_vejde(hladiny[k], y_pod):
                urovne_rady.append((hladiny[k], ("bok", "L", "dno") if k == 0 else ("bok", "L", k - 1), ("bok", "P", "dno") if k == 0 else ("bok", "P", k - 1)))
        y_pod_d = (hladiny[n_pol - 1] + _H() + DESKA_TLOUSTKA) if n_pol >= 1 else (hladiny[0] + _H())          # pod pracovnim ramem: deska nejvyssi police, bez police bocni pricka
        if _pricka_vejde(yw, y_pod_d):
            urovne_rady.append((yw, ("bok", "L", n_urovni_bok - 1), ("bok", "P", n_urovni_bok - 1)))
        for j_u, (y_u, seg_l, seg_p) in enumerate(urovne_rady):
            k_r = ("zmid", j_u)
            clenove[k_r] = _klon(sab, ZRAIL_PANEL, [x_mid, y_u - _P(), (zl + zr) / 2.0], delka=(zr - zl) - _P())
            odvozene_spojky.append((42, {12: seg_l, 14: k_r}))
            odvozene_spojky.append((45, {13: seg_p, 14: k_r}))

    # ----- 2c') podpery spodni police (hloubka > 900, Robert 2026-10-03): deska police se zkratila (viz vyse) a pod ni pribudou podperne profily v ose X mezi PREDNI a ZADNI
    #       podelnik ramu police (T-styl: predni konec pres dvojici rohovych spojek jako u pricek drzicich supliky, zadni konec primo na celo podelniku). Pocet podle sirky:
    #       rozpon desky mezi vnitrni plochou bocni pricky (a pricky stredni nohy XM_pol, ktera desku podpira sama) a dalsi podperou nesmi byt vetsi nez PODPERA_MAX_ROZPON.
    z_podpery = []
    if bocni_profil and p["police"] and ("t", DESKA_POLICE) in clenove:
        useky = [(zl + _H(), zm - _H()), (zm + _H(), zr - _H())] if zm is not None else [(zl + _H(), zr - _H())]
        for a_, b_ in useky:
            roz_ = b_ - a_
            n_ = max(0, int(math.ceil(roz_ / podpera_max_rozpon() - 1e-9)) - 1)
            z_podpery += [a_ + (j_ + 1) * roz_ / (n_ + 1) for j_ in range(n_)]

        def _pokryva(kk, z_):
            c_ = clenove[kk]
            h_ = 500.0 * c_["scale"][1]
            return c_["pos"][2] - h_ - 0.5 <= z_ <= c_["pos"][2] + h_ + 0.5
        x_pred = float(clenove[("t", ZRAIL_POL_PRED)]["pos"][0])             # predni podelnik police NENI na predni nohe (je o ~133 mm vzadu, pod predni polovinou desky police)
        x_zad = float(clenove[("t", ZRAIL_POL_ZAD)]["pos"][0])
        for k in range(n_pol):
            kand = [("t", ZRAIL_POL_PRED), ("seg", ZRAIL_POL_PRED)] if k == 0 else [polic_klice[k].get(("t", ZRAIL_POL_PRED)), polic_klice[k].get(("seg", ZRAIL_POL_PRED))]
            kand = [kk for kk in kand if kk and kk in clenove]
            for j_, zc_p in enumerate(z_podpery):
                klic_p = ("podpera", k, j_)
                clenove[klic_p] = _klon(sab, XRAIL_POL_L, [(x_pred + x_zad) / 2.0, hladiny[k], zc_p], delka=(x_zad - x_pred) - _P())
                predni = next((kk for kk in kand if _pokryva(kk, zc_p)), None)
                if predni is not None:
                    odvozene_spojky.append((36, {5: predni, 6: klic_p}))              # jako predni konce pricek drzicich supliky (36/37: dve spojky na bocich pricky)
                    odvozene_spojky.append((37, {5: predni, 6: klic_p}))

    # ----- 2c'') podpery pod PRACOVNI DESKOU (hloubka > 900, Robert 2026-10-04: "stejne jako pod spodni policí, stejné podperné profily pod hlavní desku ve stejné vzdálenosti od noh,
    #       resp. nad sebou"): profily v ose X mezi PREDNI a ZADNI pricku pracovniho ramu, stejny tvar a spojky jako pricky drzici supliky (tamtez 36/37 vpredu, vzadu primo na celo).
    #       Rozpony se pocitaji PO USECICH mezi caramy podelnych profilu pod deskou: bocni pricky, pricka stredni nohy (XM_prac) a pricky supliku - kdyz supliky jsou, drzi desku samy
    #       (jejich pricky se pocitaji jako podpera); kdyz supliky nejsou, pricky zmizely a podpery se doplni. Bez supliku vychazi stejna mista jako pod policí.
    z_podpery_d = []
    if bocni_profil and ("t", DESKA_PRAC) in clenove and ("t", XRAIL_PRAC_L) in clenove and ("t", ZRAIL_PRAC_PRED) in clenove:
        cary = [zl, zr] + ([zm] if zm is not None else []) + [float(clenove[kb]["pos"][2]) for kb in (("t", XRAIL_BOX1), ("t", XRAIL_BOX2)) if kb in clenove]
        cary.sort()
        for za_, zb_ in zip(cary, cary[1:]):
            a_, b_ = za_ + _H(), zb_ - _H()
            n_ = max(0, int(math.ceil((b_ - a_) / podpera_max_rozpon() - 1e-9)) - 1)
            z_podpery_d += [a_ + (j_ + 1) * (b_ - a_) / (n_ + 1) for j_ in range(n_)]
        bok_ = clenove[("t", XRAIL_PRAC_L)]
        delka_d = float(bok_["scale"][1]) * 1000.0
        kand_d = [kk for kk in (("t", ZRAIL_PRAC_PRED), ("seg", ZRAIL_PRAC_PRED)) if kk in clenove]

        def _pokryva_d(kk, z_):
            c_ = clenove[kk]
            h_ = 500.0 * c_["scale"][1]
            return c_["pos"][2] - h_ - 0.5 <= z_ <= c_["pos"][2] + h_ + 0.5
        for j_, zc_p in enumerate(z_podpery_d):
            klic_p = ("podpera_d", j_)
            clenove[klic_p] = _klon(sab, XRAIL_PRAC_L, [float(bok_["pos"][0]), float(bok_["pos"][1]), zc_p], delka=delka_d)
            predni = next((kk for kk in kand_d if _pokryva_d(kk, zc_p)), None)
            if predni is not None:
                odvozene_spojky.append((36, {5: predni, 6: klic_p}))
                odvozene_spojky.append((37, {5: predni, 6: klic_p}))

    # ----- 2c''') drzak PET lahve na JINE noze / JINE strane profilu (Robert 2026-10-04: "drzak PET nech prepnutelny na jakoukoli jinou stranu profilu nebo jiny svisly profil"): sablona visi na
    #       predni leve noze, na strane +z (vpravo); jina strana = otoceni drzaku kolem svisle osy nohy o 90/180/270 st. (poloha vuci ose nohy se otaci s nim), jina noha = posun osy.
    pet_noha_chybi = False
    if ("t", PET) in clenove and (p["pet_noha"] != "PL" or p["pet_strana"] != "vpravo"):
        cil = {"PL": (xf, zl), "PP": (xf, zr), "ZL": (xr, zl), "ZP": (xr, zr), "FM": (xf, zm), "RM": (xr, zm)}[p["pet_noha"]]
        if cil[1] is None or (p["pet_noha"] in ("FM", "RM") and p["pet_noha"] not in clenove):
            pet_noha_chybi = True                                              # stredni noha neni (sirka <= prah): drzak zustane na sablonove noze, hlasi se problem
        else:
            c_pet = clenove[("t", PET)]
            d0 = np.array([float(c_pet["pos"][0]) - xf, float(c_pet["pos"][2]) - zl])          # poloha drzaku vuci ose predni leve nohy
            th = math.radians(PET_STRANY[p["pet_strana"]])
            d1 = np.array([d0[0] * math.cos(th) + d0[1] * math.sin(th), -d0[0] * math.sin(th) + d0[1] * math.cos(th)])
            c_pet["pos"][0], c_pet["pos"][2] = float(cil[0] + d1[0]), float(cil[1] + d1[1])
            qy = (0.0, math.sin(th / 2.0), 0.0, math.cos(th / 2.0))
            c_pet["quaternion"] = tuple(_kvat_nasob(qy, tuple(c_pet["quaternion"])))

    # ----- 2b'') police pod otvorem (vyrezem): deska + 2 nosne profily v ose X + 4 zavesy (svisle profily) z predniho a zadniho ramu -----
    # Nosne profily (osa X) lezi pod okraji police v ose Z a jsou zavesene na predni a zadni ramovy profil (osa Z, x = predni/zadni noha) pres
    # zavesy; police (deska 18 mm) lezi na nosnych profilech. Kolize s nohami, supliky apod. hlasi obecne kontroly (nabidka odebrani police).
    polvyr_nizka = []
    for v in vyrezy:
        n = v["n"]
        if not p[f"vyrez{n}_police"]:
            continue
        cast = sab[DESKA_POLICE]
        lc_p = (glb_bbox(cast["part_id"])[0] + glb_bbox(cast["part_id"])[1]) / 2.0
        Rm_p = kvat_na_matici(cast["quaternion"])
        tl = float((glb_bbox(cast["part_id"])[1] - glb_bbox(cast["part_id"])[0])[2] * cast["scale"][2])      # tloustka desky (18 mm: lokalni osa Z mesh)
        y_dno = y_dno_desky
        y_horni = y_dno - VYREZ_POLICE_MEZERA                    # horni plocha police
        x_a, x_b = v["x0"] - VYREZ_POLICE_PRESAH, v["x1"] + VYREZ_POLICE_PRESAH
        z_a, z_b = v["z0"] - VYREZ_POLICE_PRESAH, v["z1"] + VYREZ_POLICE_PRESAH
        s_k = np.array([(x_b - x_a) / 1000.0, (z_b - z_a) / 1000.0, cast["scale"][2]])
        stred_k = np.array([(x_a + x_b) / 2.0, y_horni - tl / 2.0, (z_a + z_b) / 2.0])
        clenove[("polvyr", n, "deska")] = _clen(cast["part_id"], cast["quaternion"], s_k.tolist(), stred_k - Rm_p @ (s_k * lc_p), "deska", src=DESKA_POLICE)
        y_nos_h = y_horni - tl                                   # horni hrana nosneho profilu = spodek desky police
        y_ram_dole = yw - _H()                                   # spodek predniho/zadniho ramu
        delka_zavesu = y_ram_dole - (y_nos_h - _P())
        for j, zc_n in enumerate((z_a + _H(), z_b - _H())):
            nos = _klon(sab, XRAIL_PRAC_L, [(xf + xr) / 2.0, y_nos_h - _H(), zc_n], delka=(xr - xf) - _P())
            clenove[("polvyr", n, "nos", j)] = nos
            for i_x, xc_n in enumerate((xf, xr)):
                clenove[("polvyr", n, "zaves", j, i_x)] = _klon(sab, NOHA_PL, [xc_n, (y_ram_dole + (y_nos_h - _P())) / 2.0, zc_n], delka=delka_zavesu)
        if y_nos_h - _P() < max(podlaha + _P(), (navlek_vrch + NAVLEK_MEZERA_NAD) if navlek else 0.0) or delka_zavesu < min_delka_nohy():
            polvyr_nizka.append(n)

    # ----- 2c) ložiskové jednotky na pracovní desce -----
    loz_info = None
    if p["loz"] and ("t", DESKA_PRAC) in clenove:
        cast = sab[DESKA_PRAC]
        # rozmer CELE desky (vyrezy ji rozrezaly na kusy, ale obrys je stejny)
        kusy_d = [c for k, c in clenove.items() if c["druh"] == "deska" and (k == ("t", DESKA_PRAC) or k[0] == "kus")]
        bbs = [_aabb({"part_id": c["part_id"], "quaternion": c["quaternion"], "scale": c["scale"], "position": c["pos"]}) for c in kusy_d]
        X0 = min(float(b[0][0]) for b in bbs); X1 = max(float(b[1][0]) for b in bbs)
        Z0 = min(float(b[0][2]) for b in bbs); Z1 = max(float(b[1][2]) for b in bbs)
        y_povrch = max(float(b[1][1]) for b in bbs)
        mrizka, nx, nz = _loz_mrizka(X0, X1, Z0, Z1, p["loz_okraj"], p["loz_rozteca"])
        r_j = LOZ_PRUMER / 2.0
        otvory_r = [(v["x0"] - LOZ_MEZERA_OTVOR, v["x1"] + LOZ_MEZERA_OTVOR, v["z0"] - LOZ_MEZERA_OTVOR, v["z1"] + LOZ_MEZERA_OTVOR) for v in vyrezy]
        if zm is not None:                                  # dělicí spára desek u střední opory: jednotka se nevrtá přes spáru (jako u výřezu se vynechá)
            otvory_r.append((X0 - 1.0, X1 + 1.0, zm - LOZ_MEZERA_OTVOR, zm + LOZ_MEZERA_OTVOR))
        # ostatni dily nad deskou (panely, elektrozlab, drzak PET, profily nastavby...), s nimiz by jednotka kolidovala
        prekazky_d = []
        for k, c in clenove.items():
            if c["druh"] == "deska":
                continue
            lo_c, hi_c = _aabb({"part_id": c["part_id"], "quaternion": c["quaternion"], "scale": c["scale"], "position": c["pos"]})
            if hi_c[1] > y_povrch + TOL_PRUNIK_MM:
                prekazky_d.append((lo_c, hi_c))
        vynechano = 0
        if len(mrizka) > MAX_LOZ:
            loz_info = {"pocet": 0, "radku": nx, "sloupcu": nz, "vynechano": 0, "navrh": len(mrizka), "moc": True}
        else:
            for (x, z) in mrizka:
                if any(o[0] < x + r_j and x - r_j < o[1] and o[2] < z + r_j and z - r_j < o[3] for o in otvory_r):
                    vynechano += 1
                    continue
                lo_j, hi_j = np.array([x - r_j, y_povrch, z - r_j]), np.array([x + r_j, y_povrch + LOZ_VYSKA, z + r_j])
                if any(np.all(np.minimum(hi_j, hi_c) - np.maximum(lo_j, lo_c) > TOL_PRUNIK_MM) for lo_c, hi_c in prekazky_d):
                    vynechano += 1
                    continue
                clenove[("loz", len(clenove))] = _clen(LOZ_PART, (0.0, 0.0, 0.0, 1.0), [1.0, 1.0, 1.0], [x, y_povrch, z], "loz", src=None)
            loz_info = {"pocet": sum(1 for k in clenove if k[0] == "loz"), "radku": nx, "sloupcu": nz, "vynechano": vynechano, "moc": False}

    # ----- 3) spojky: poloha = novy uzel + puvodni odsazeni od puvodniho uzlu -----
    for c in SPOJKY:
        a, b = _vlastnici_spojky(sab, c)
        if ("t", a) not in clenove or ("t", b) not in clenove:
            continue
        ka, _ = _osa(sab[a]["quaternion"])
        kb, _ = _osa(sab[b]["quaternion"])
        u0 = _uzel(stred0, a, b, ka, kb)
        u1 = _uzel({a: clenove[("t", a)]["pos"], b: clenove[("t", b)]["pos"]}, a, b, ka, kb)
        pos = stred0[c] + (u1 - u0)
        cc = sab[c]
        if _zanori_do_desky(clenove, cc["part_id"], tuple(cc["quaternion"]), cc["scale"], pos):
            continue
        att = json.loads(json.dumps(cc["attached_to"]))
        ka_osa = {a: ka, b: kb}
        kl_a, kl_b = _usek(clenove, a, u1[ka]), _usek(clenove, b, u1[kb])
        kl_att = kl_a if att["prof"] == a else (kl_b if att["prof"] == b else ("t", att["prof"]))
        spojky[("s", c)] = {"part_id": cc["part_id"], "quaternion": tuple(cc["quaternion"]), "scale": list(cc["scale"]),
                            "pos": pos, "vlastnici": (kl_a, kl_b), "attached_to_klic": kl_att,
                            "attached_to": att, "color": cc.get("color"), "used_conn": cc.get("used_conn")}

    odvozene_spojky += hpolice_spojky                          # spojky horni police az na konec: cislovani ostatnich odvozenych spojek se police nemeni
    for n, spec in enumerate(odvozene_spojky):
        c_src, mapa = spec[0], spec[1]
        priznaky = set(spec[2]) if (len(spec) > 2 and isinstance(spec[2], (tuple, list, set))) else ({spec[2]} if len(spec) > 2 else set())
        rot = "rx180" in priznaky
        a, b = _vlastnici_spojky(sab, c_src)
        ka, _ = _osa(sab[a]["quaternion"])
        kb, _ = _osa(sab[b]["quaternion"])
        klic_a, klic_b = mapa[a], mapa[b]
        if klic_a not in clenove or klic_b not in clenove:
            continue
        # osy novych vlastniku (maji stejne otoceni jako vzorove), uzel z jejich novych stredu; `ry90` = spoj je OTOCENY o 90 st. kolem svisle osy (svisly profil na pricku v ose Z misto X)
        u0 = _uzel(stred0, a, b, ka, kb)
        ka_n, kb_n = ka, kb
        if "ry90" in priznaky:
            ka_n = {0: 2, 2: 0}.get(ka, ka)
            kb_n = {0: 2, 2: 0}.get(kb, kb)
        u1 = _uzel({a: clenove[klic_a]["pos"], b: clenove[klic_b]["pos"]}, a, b, ka_n, kb_n)
        cc = sab[c_src]
        odsazeni = stred0[c_src] - u0
        q = tuple(cc["quaternion"])
        if rot:                     # otoceni celeho spoje o 180 stupnu kolem osy pricky (kolem osy X)
            odsazeni = np.array([odsazeni[0], -odsazeni[1], -odsazeni[2]])
            q = _kvat_nasob((1.0, 0.0, 0.0, 0.0), q)
        if "ry90" in priznaky:      # otoceni celeho spoje o +90 st. kolem svisle osy Y: (x, y, z) -> (z, y, -x)
            odsazeni = np.array([odsazeni[2], odsazeni[1], -odsazeni[0]])
            q = _kvat_nasob((0.0, math.sin(math.pi / 4.0), 0.0, math.cos(math.pi / 4.0)), q)
        rotace = spec[3] if len(spec) > 3 else ()              # (osa, stupne) ...: dalsi otoceni kolem uzlu (horni police: stejny spoj v jinem rohu)
        for osa_r, st_r in rotace:
            odsazeni, q = _otoc_spojku(odsazeni, q, osa_r, st_r)
        pos_spojky = u1 + odsazeni
        if _zanori_do_desky(clenove, cc["part_id"], q, cc["scale"], pos_spojky):
            continue
        att = None
        if not rot and "ry90" not in priznaky and not rotace:
            att = json.loads(json.dumps(cc["attached_to"]))
        spojky[("n", n)] = {"part_id": cc["part_id"], "quaternion": q, "scale": list(cc["scale"]),
                            "pos": pos_spojky, "vlastnici": (klic_a, klic_b),
                            "attached_to_klic": mapa.get(cc["attached_to"]["prof"]) if att else None,
                            "attached_to": att, "color": cc.get("color"), "used_conn": cc.get("used_conn")}

    # 3b) spojky dalsich polic: kopie spojek, ktere patri skupine prvni police (mimo spojky svislych profilu bocnic), posunute po vysce;
    #     spojka, ktera by se zanorila do desky, se vynecha (jako vsude)
    for ksp, sp in list(spojky.items()):
        if any(v[0] in ("bok", "podpera", "podpera_d", "ram") if isinstance(v, tuple) else False for v in sp["vlastnici"]):
            continue                                                       # svisle profily bocnic, podpery police a svisle profily ramu maji spojky pro kazdou uroven zvlast
        if not any(v in skupina_polic for v in sp["vlastnici"]):
            continue
        for k in range(1, n_pol):
            mapa_k = polic_klice[k]
            dy = hladiny[k] - hladiny[0]
            pos_n = sp["pos"] + np.array([0.0, dy, 0.0])
            if _zanori_do_desky(clenove, sp["part_id"], sp["quaternion"], sp["scale"], pos_n):
                continue
            att = json.loads(json.dumps(sp["attached_to"])) if sp["attached_to"] else None
            spojky[("sk", ksp, k)] = {"part_id": sp["part_id"], "quaternion": sp["quaternion"], "scale": list(sp["scale"]), "pos": pos_n,
                                      "vlastnici": tuple(mapa_k.get(v, v) for v in sp["vlastnici"]),
                                      "attached_to_klic": mapa_k.get(sp["attached_to_klic"], sp["attached_to_klic"]),
                                      "attached_to": att, "color": sp.get("color"), "used_conn": sp.get("used_conn")}

    # ----- 3c) sikme vzpery 45 st. pod rameny LED (jen se zadnimi stojkami a LED; dily se pridavaji NA KONEC seznamu dilu, viz poradi nize) -----
    vz_info = []
    vz_meze = None
    if p["vzpery"] and p["stojky"] and p["led"] and _sd()["vzpery"]:
        def _bb_clenu(c):
            return _aabb({"part_id": c["part_id"], "quaternion": c["quaternion"], "scale": c["scale"], "position": c["pos"]})
        pary = [("L", ("t", NOHA_ZL), ("t", XRAIL_TOP_L)), ("P", ("t", NOHA_ZP), ("t", XRAIL_TOP_P))]
        if "RM" in clenove and "XM_top" in clenove:                                          # u stredni zadni stojky (panel uz nevisi pred stojkou, sedi mezi stojkami)
            pary.append(("M", "RM", "XM_top"))
        pary = [x for x in pary if x[1] in clenove and x[2] in clenove]
        kl_vse = list(clenove) + list(spojky)
        bb_vse = np.array([_bb_clenu(clenove[k]) if k in clenove else _bb_clenu(spojky[k]) for k in kl_vse], float)
        kl_vse, bb_vse = _hpol().pro_vzpery(hpolice_info, kl_vse, bb_vse, clenove, spojky)          # sikma horni police: obalky naklonenych dilu a konzol v definitivni poloze (vzpera se jim prizpusobi)
        pary_d = []
        for jm, k_post, k_arm in pary:
            i_po, i_ar = kl_vse.index(k_post), kl_vse.index(k_arm)
            pary_d.append({"x_p": float(bb_vse[i_po][0][0]), "y_a": float(bb_vse[i_ar][0][1]), "z": float(clenove[k_post]["pos"][2]), "bb_post": bb_vse[i_po], "bb_arm": bb_vse[i_ar],
                           "ostatni": [i for i in range(len(kl_vse)) if i not in (i_po, i_ar)]})
        # delka vzpery = delka PROFILU; horni mez dava rameno LED (spojka cela pod ramenem), vyska stojky a dily v okoli: spocita se nejvetsi PLATNA delka (po 10 mm) a pozadovana se
        # na ni orizne (stejne jako pocet polic); `vzpera_meze` jde do odpovedi (jezdec ma skutecne meze)
        L_pozad = float(p["vzpera_delka"])
        pozad_ok = _vzpera_plati(L_pozad, pary_d, bb_vse)
        if meze or not pozad_ok:                      # uplne hledani platnych delek (sken po 10 mm) jen kdyz je treba: pozadovana se nevejde (orez), nebo se maji vratit meze pro jezdec
            klic_c = (_SYSTEM.get(), bb_vse.round(3).tobytes(), tuple((round(q["x_p"], 3), round(q["y_a"], 3), round(q["z"], 3), tuple(q["ostatni"])) for q in pary_d))
            platne = _VZPERA_CACHE.get(klic_c)
            if platne is None:                                           # stejna geometrie okoli (odpoved() sestavuje stul mnohokrat) = stejne platne delky
                platne = [float(L) for L in range(int(ROZSAH["vzpera_delka"][0]), int(ROZSAH["vzpera_delka"][1]) + 1, 10) if _vzpera_plati(float(L), pary_d, bb_vse)]
                if len(_VZPERA_CACHE) > 64:
                    _VZPERA_CACHE.pop(next(iter(_VZPERA_CACHE)))
                _VZPERA_CACHE[klic_c] = platne
            if platne:
                if not pozad_ok:
                    nizsi = [L for L in platne if L <= L_pozad]
                    p["vzpera_delka"] = nizsi[-1] if nizsi else platne[0]
                vz_meze = {"hodnota": float(p["vzpera_delka"]), "min": platne[0], "max": platne[-1], "vejde": True}
            else:
                vz_meze = {"hodnota": L_pozad, "min": L_pozad, "max": L_pozad, "vejde": False}
        else:
            vz_meze = {"hodnota": L_pozad, "vejde": True}
        for (jm, k_post, k_arm), pd in zip(pary, pary_d):
            sada = _vzpera_sada(pd["x_p"], pd["y_a"], pd["z"], p["vzpera_delka"])
            k_prof = ("vz", jm, "prof")
            clenove[k_prof] = _clen(_sd()["profil"], sada["q_prof"], [1.0, p["vzpera_delka"] / 1000.0, 1.0], sada["stred"], "profil", src=None)
            for n_s, (pivot, q_s) in enumerate(sada["spojky"]):
                spojky[("vz", jm, n_s)] = {"part_id": _sd()["vzpera_spojka"], "quaternion": q_s, "scale": [1.0, 1.0, 1.0], "pos": pivot,
                                           "vlastnici": (k_prof, k_post if n_s == 0 else k_arm), "attached_to_klic": None, "attached_to": None, "color": None, "used_conn": None}
            vz_info.append({"jm": jm, "prof": k_prof, "post": k_post, "arm": k_arm, "dole": ("vz", jm, 0), "nahore": ("vz", jm, 1)})

    # ----- 3b) zaslepky na VOLNE KONCE profilu (Robert 2026-10-06; viz _volne_konce): az po vsech clenech a spojkach, aby se hodnotil skutecny dotyk -----
    for k_prof, znak, bod, dvn in _volne_konce(clenove, spojky):
        clenove[("zasl", k_prof, "+" if znak > 0 else "-")] = _clen(_sd()["zaslepka"], _q_zaslepky(-dvn), [1.0, 1.0, 1.0], bod + dvn * _sd()["zaslepka_vyska"], "prisl", src=None)

    # ----- 4) ocekavane dosednuti koncu (z geometrie sablony) -----
    konce_sab = _konce_sablony(sab)
    for klic, c in clenove.items():
        if c["druh"] != "profil":
            continue
        src = c["src"]
        if c.get("konce") is not None:
            konce_ocek[klic] = tuple(c["konce"])                           # horni police: konce podle role profilu (api/stul_hpolice.py)
        elif _je_vz(klic):
            konce_ocek[klic] = (False, False)             # konce vzpery nedosedaji na profil - nese je sikma spojka (kontrola `vzpera_kolize`)
        elif klic[0] == "bok" and klic[2] == "dno":
            konce_ocek[klic] = (False, True)               # stredni noha bocnice (system 45): dole na podlaze / kolecku, nahore pod nejnizsi bocni pricku
        elif klic[0] in ("bok", "podpera", "podpera_d", "ram", "panrail", "zmid"):
            konce_ocek[klic] = (True, True)
        elif klic in (("t", NOHA_ZL), ("t", NOHA_ZP), "RM"):
            konce_ocek[klic] = (False, bool((p["led"] and p["stojky"])))        # horni konec zadni nohy lezi pod hornim ramem (LED)
        elif klic == "FM":
            konce_ocek[klic] = (False, False)
        elif klic == "XM_top":
            konce_ocek[klic] = konce_sab[XRAIL_TOP_L]
        elif klic[0] == "polvyr":
            konce_ocek[klic] = (True, True) if klic[2] == "nos" else (False, True)       # nosny profil dosedá oběma konci na závěsy; závěs horním koncem pod rám
        else:
            konce_ocek[klic] = konce_sab[src]

    # ----- 5) vystup: poradi, indexy, lic_peers -----
    _hpol().pridej_konzoly(hpolice_info, clenove)                  # sikma horni police: naklapeci konzole az po zaslepkach volnych koncu (jinak by se dotykaly koncu profilu v plochem stavu)
    _oznac_desky(clenove, zm)                                  # kazdy kus desky ví, ke které desce patří (deska_id): výrobní výpis, cena, 3D části
    poradi = ([k for k in clenove if not _je_vz(k) and not _je_zasl(k)] + [k for k in spojky if not _je_vz(k)]
              + [k for k in clenove if _je_vz(k)] + [k for k in spojky if _je_vz(k)]          # sikme vzpery (profil + 2 spojky) na konec - zlaty test #577
              + [k for k in clenove if _je_zasl(k)])                                          # zaslepky volnych koncu profilu jeste za nimi: indexy vsech ostatnich dilu zustavaji
    # spojky maji byt PO profilech/deskach/prislusenstvi jako v sablone (zlaty test) - vlozene jsou uz na konci
    idx = {k: n for n, k in enumerate(poradi)}
    dily = []
    for k in poradi:
        c = clenove.get(k) or spojky[k]
        pos_c, q_c = c["pos"], c["quaternion"]
        if hpolice_info and hpolice_info.get("rotace") and _hpol().v_rotaci(k, c, clenove):
            pos_c, q_c = _hpol().rotuj(hpolice_info["rotace"], pos_c, q_c)          # sikma horni police: ram se postavil PLOCHY, tady se tuhe otoci kolem osy zadni pricky
        dily.append({"part_id": c["part_id"], "position": [round(float(v), 4) for v in pos_c],
                     "quaternion": [round(float(v), 6) for v in q_c],
                     "scale": [round(float(v), 6) for v in c["scale"]]})
        if c.get("celek"):
            dily[-1]["deska_celek"] = c["celek"]          # prvni kus rozrezane desky nese rozmer CELE desky (cena)
            dily[-1]["deska_vyrezu"] = c.get("vyrezu", len(vyrezy))        # a pocet vyrezu (cena za vyrez - pravidlo `cena_vyrez`; vyrez desky police pro svisly profil rámu se nepocita)
        if c.get("kus"):
            dily[-1]["deska_kus"] = True                  # dalsi kusy te desky se do ceny nepocitaji
        if c.get("deska_id"):
            dily[-1]["deska_id"] = c["deska_id"]          # deska, do ktere dil patri (pracovni deska / police / police pod vyrezem; leva / prava cast u stredni opory)
    for k, s in spojky.items():
        d = dily[idx[k]]
        if s["attached_to"] and s["attached_to_klic"] in idx:
            s["attached_to"]["prof"] = idx[s["attached_to_klic"]]
            d["attached_to"] = s["attached_to"]
        if s.get("color"):
            d["color"] = s["color"]
        if s.get("used_conn") is not None:
            d["used_conn"] = s["used_conn"]
    # lic_peers: dvojice profil-profil z GEOMETRIE (definice spoje), drzi je nizsi index; spojky maji oba vlastnici
    bb = [_aabb(d) for d in dily]
    prof_idx = [idx[k] for k, c in clenove.items() if c["druh"] == "profil"]
    prof_zakl = [idx[k] for k, c in clenove.items() if c["druh"] == "profil" and not _je_vz(k) and not c.get("hp_rot")]      # sikma vzpera a naklonena horni police nemaji celni dotyk (AABB sikmeho profilu je velka)
    peers = {i: set() for i in prof_idx}
    for ai, i in enumerate(prof_zakl):
        for j in prof_zakl[ai + 1:]:
            if _dotyk_cela(bb[i], bb[j]):
                peers[min(i, j)].add(max(i, j))
    for k, s in spojky.items():
        for vl in s["vlastnici"]:
            peers[idx[vl]].add(idx[k])
    for ka_, kb_ in ((hpolice_info or {}).get("pary") or ()):      # sikma horni police: spoje profil - profil (AABB naklonenych profilu spoj nepozna)
        if ka_ in idx and kb_ in idx:
            peers[min(idx[ka_], idx[kb_])].add(max(idx[ka_], idx[kb_]))
    for vi in vz_info:                                      # vzpera drzi na stojce a na rameni pres sikme spojky: 2 spoje (kazdy konec jeden), pocitaji se jako spoje profilu
        for kf in (vi["post"], vi["arm"]):
            a_, b_ = idx[kf], idx[vi["prof"]]
            peers[min(a_, b_)].add(max(a_, b_))
    for i in prof_idx:
        if peers[i]:
            dily[i]["lic_peers"] = sorted(peers[i])

    # uchopovaci znacka stredni nohy (tazeni mysi v 3D): predni stredni noha, pod rámem desky; rozsah osy nohy mezi krajnimi
    vodici = None
    if stredni:
        # zakazana pasma osy stredni nohy (tazeni mysi se zastavi ODSTUP_PRI_TAZENI pred kolizi). Hybe se CELA stredova osa: obe stredni
        # nohy, jejich pricky, kolecka a hlavne SPOJKY (uhelniky) - ty sahaji do strany dal nez noha (+-42 mm proti +-15 mm) a kolecko je
        # nesymetricke, takze se mezera (ODSTUP_PRI_TAZENI) meri od SKUTECNYCH obrysu hybnych dilu, ne od 30 mm profilu (Robert: "pri kolizi
        # uhelniku s cimkoliv se musi vratit, aby byla mezera centimetr od uhelniku"). Prekazky: komponenty a prislusenstvi (box, panely, LED,
        # elektrozlab, drzak PET, desky), pricky boxu a jejich spojky; kazda prekazka, ktera se prekryva s pudorysem a vyskou nektereho hybneho
        # dilu, blokuje pasmo stredu nohy [prek_lo - hyb_hi_rel - odstup, prek_hi - hyb_lo_rel + odstup].
        pohyb_k = ([k for k in ("FM", "RM", "XM_prac", "XM_pol", "XM_top", "kolecko_FM", "kolecko_RM", ("konec", "FM"), ("konec", "RM"),
                                                                                       ("konec", "FM", "navlek"), ("konec", "RM", "navlek"), ("konec", "FM", "zasl"), ("konec", "RM", "zasl")) if k in clenove]
                   + [k for k in clenove if _je_vz(k) and k[1] == "M"]              # stredni vzpera (u stredni zadni stojky) jede se stredni nohou
                   + [k for k in clenove if isinstance(k, tuple) and (k[0] == "ram" or (k[0] == "polic" and k[2] == "XM_pol"))])      # svisle profily vestaveneho ramu a stredni pricky vyssich polic
        pohyb_i = [idx[k] for k in pohyb_k] + [idx[sk] for sk, sp in spojky.items() if any(v in pohyb_k for v in sp["vlastnici"])]
        klice_boxu = (("t", XRAIL_BOX1), ("t", XRAIL_BOX2))
        prekazky = []
        for kk, cc in clenove.items():
            if kk in pohyb_k or (isinstance(kk, str) and kk.startswith("kolecko")) or (kk[0] == "t" and kk[1] in KOLECKA) or kk[0] in ("loz", "konec", "zasl"):
                continue                                                      # zaslepky volnych koncu profilu (3 mm) nejsou prekazka tazeni
            if rezim == "noha" and (kk in panely_klice or kk == ("t", ELZLAB)):
                continue                                                      # panel se stredi v useku mezi stojkami (hybe se se stredni nohou napul) a elektrozlab s nim: misto 10 mm mezery plati kapacita useku (nize)
            if cc["druh"] == "profil" and kk not in klice_boxu and kk[0] != "polvyr":
                continue
            prekazky.append(idx[kk])
        for sk, sp in spojky.items():
            if any(v in klice_boxu for v in sp["vlastnici"]) and not any(v in pohyb_k for v in sp["vlastnici"]):
                prekazky.append(idx[sk])
        zakazano = []
        for pj in prekazky:
            klo, khi = bb[pj]
            for mi in pohyb_i:
                mlo, mhi = bb[mi]
                if min(khi[0], mhi[0]) - max(klo[0], mlo[0]) > TOL_PRUNIK_MM and min(khi[1], mhi[1]) - max(klo[1], mlo[1]) > TOL_PRUNIK_MM:
                    zakazano.append([float(klo[2] - (mhi[2] - zm) - ODSTUP_PRI_TAZENI), float(khi[2] - (mlo[2] - zm) + ODSTUP_PRI_TAZENI)])
        # panely mezi stojkami (rezim `noha`): stredni noha deli zadni stranu na dva useky; polohy, kdy by se pozadovane panely do useku nevesly (usek < panel + 2 x 1 mm), jsou zakazane,
        # aby se tazenim panel nevypnul ani neprehodil (u `auto` by se jinak konstrukce prepnula na vestaveny ram). Jeden panel potrebuje jeden usek, dva panely vedle sebe oba
        if rezim == "noha" and panely_info["pocet"] > 0 and panely_info.get("rad_max"):
            useku = -(-panely_info["pocet"] // panely_info["rad_max"])
            s_min = _panel_geometrie(delka_panelu)["s"] + 2 * PANEL_MEZERA
            z_a, z_b = float(zl + 2 * _H() + s_min), float(zr - 2 * _H() - s_min)       # levy usek se vejde od z_a, pravy do z_b (z = osa stredni nohy)
            if useku >= 2:
                zakazano += [[float(zl) - 100.0, z_a], [z_b, float(zr) + 100.0]]
            elif z_b < z_a:
                zakazano.append([z_b, z_a])
        zakazano.sort()
        slite = []
        for a, b in zakazano:
            if slite and a <= slite[-1][1]:
                slite[-1][1] = max(slite[-1][1], b)
            else:
                slite.append([a, b])
        zakazano = slite
        y_znacky = float(max(dolni + 60.0, dolni + 0.25 * (horni_pred - dolni)))     # spodni cast nohy, nad kolecky
        if navlek_vrch is not None:
            y_znacky = float(max(y_znacky, navlek_vrch + 30.0))                      # s navlekem: znacka na viditelne casti nohy nad jeklem
        x_znacky = float(xf)
        if rezim == "ram":                                                           # vestaveny ram: znacka na predni svisle profil (uprostred prvni mezery mezi policí a pracovnim ramem)
            x_znacky, y_znacky = float(x_pred_f), float((hladiny[0] + yw) / 2.0)
        vodici = {"stredni_noha": {"x": x_znacky, "y": y_znacky, "z": float(zm), "z_levy": float(zl), "z_pravy": float(zr), "rezim": rezim,
                                   "min": float(zl + zm_min), "max": float(zl + zm_max),
                                   "zakazano": zakazano}}
    problemy = _zkontroluj(dily, bb, clenove, spojky, idx, konce_ocek, (xf, xr, zl, zr))
    problemy += _hpol().zkontroluj(hpolice_info, dily, bb, idx, clenove, spojky)          # sikma horni police: presna kontrola kolizi naklonenych dilu
    led_info = {"delka": int(round(float(p["led_delka"]))), "typy": [], "pocet": 1, "max": 1, "polohy": [], "auto": [], "meze": [], "pridat": None, "odebrat": []}          # delky svitidel LED, pocet, polohy a meze (vztazene k OSE STOLU, mm)
    if p["led"] and p["stojky"] and p["led_svetlo"] and led_stav:
        wout = float(zr - zl + 2 * _H())
        dp_led = 1000.0 * clenove[("t", ZRAIL_TOP)]["scale"][1] if ("t", ZRAIL_TOP) in clenove else None
        n_led = led_stav["n"]
        for d_led in LED_DELKY:
            try:
                telo_l, presne_l = led_telo_dilu(LED_TYPY[d_led]), _led_telo_presne(LED_TYPY[d_led])
            except StulChyba:
                continue                                                           # GLB teto delky v katalogu chybi: delka se nenabizi
            n_t = led_max_pocet(p["sirka"], telo_l)
            presah_t = (n_t - 1) * telo_l + presne_l - wout                        # nejvyssi pocet svitidel teto delky tesne vedle sebe: vejde se, kdyz soucet delek nepresahne sirku + LED_PREVIS (jako dosud)
            led_info["typy"].append({"delka": d_led, "telo": telo_l, "pocet": n_t, "min_sirka": int(math.ceil(telo_l - LED_PREVIS)),
                                     "vejde": bool(presah_t <= LED_PREVIS + 1.0 and (dp_led is None or dp_led >= MIN_PODIL_PROFILU_LED * n_t * telo_l - 0.01))})
        zc_l, s_l = led_stav["zc"], led_stav["telo"]
        meze_abs = led_meze(led_stav["v"], s_l, led_stav["z_lo"], led_stav["z_hi"], led_stav["rozpeti"]) if led_stav["proveditelne"] else [(v_ - 1e6, v_ + 1e6) for v_ in led_stav["v"]]
        led_info.update({"pocet": n_led, "max": led_stav["n_max"], "telo": s_l, "osa": round(zc_l, 1),
                         "polohy": [round(v_ - zc_l, 1) for v_ in led_stav["v"]], "auto": [round(a_ - zc_l, 1) for a_ in led_stav["auto"]],
                         "meze": [[round(lo_ - zc_l, 1), round(hi_ - zc_l, 1)] for lo_, hi_ in meze_abs], "okraj": [round(led_stav["z_lo"] - zc_l, 1), round(led_stav["z_hi"] - zc_l, 1)],
                         "stred": [round(led_stav["stred_meze"][0] - zc_l, 1), round(led_stav["stred_meze"][1] - zc_l, 1)],
                         "pridat": led_pridat(led_stav) if led_stav["proveditelne"] else None,
                         "odebrat": [led_odebrat(led_stav, k_) for k_ in range(n_led)] if (led_stav["proveditelne"] and n_led > 1) else []})
    problemy += _zkontroluj_vzpery(dily, bb, idx, vz_info)
    problemy += _zkontroluj_navlek(dily, bb, clenove, idx, p, navlek_meze, navlek_vrch)
    if not police_meze["ok"]:
        problemy.append({"kod": "police_vyska", "dily": [], "text": "Výška polic: " + police_meze["problem"] + "."})
    if pet_noha_chybi:
        problemy.append({"kod": "pet_noha", "dily": [idx[("t", PET)]], "text": f"Držák PET lahve nemůže viset na {PET_NOHY_NAZVY[p['pet_noha']]} noze – stůl ji nemá (střední nohy jsou jen u širšího stolu)."})
    pet_meze = _pet_meze(bb, idx, float(p["pet_posun"]), dily) if (p["drzak_pet"] and ("t", PET) in clenove) else None
    if pet_meze and not (pet_meze["min"] <= pet_meze["hodnota"] <= pet_meze["max"]) and not any(idx[("t", PET)] in (x.get("dily") or []) for x in problemy):
        problemy.append({"kod": "pet_mimo_nohu", "dily": [idx[("t", PET)]], "text": "Držák PET lahve je posunutý mimo nohu – posuň ho zpět (výška držáku PET lahve)."})
    if p["panely"] and p["stojky"] and not panely_info["pocet"]:
        if panely_info["sloupcu"] == 0:
            text_pn = (f"Perforovaný panel ({delka_panelu:.0f} mm) se nevejde mezi zadní stojky – nejmenší šířka stolu s panelem je {panely_info['min_sirka']} mm"
                       + (" (se střední nohou uprostřed až od dvou panelů vedle sebe)." if rezim == "noha" else "."))
        else:
            text_pn = f"Perforovaný panel se nevejde na zadní stojky – jsou příliš nízké (potřebují aspoň {panely_info['min_stojky']} mm nad deskou)."
        problemy.append({"kod": "panel_nevejde", "dily": [], "text": text_pn})
    if hpolice_info and hpolice_info.get("problem") == "misto":
        problemy.append({"kod": "hpolice_nevejde", "dily": [],
                         "text": "Police mezi zadními stojkami se sem nevejde – mezi panely (nebo deskou) a ramenem LED není dost místa (zvyšte zadní stojky, snižte počet panelů, nebo ji vypněte)."})
    elif hpolice_info and hpolice_info.get("problem") == "sirka":
        problemy.append({"kod": "hpolice_nevejde", "dily": [], "text": "Police mezi zadními stojkami se sem nevejde – mezi zadní stojky potřebuje stůl širší."})
    elif hpolice_info and hpolice_info.get("problem") == "hloubka":
        problemy.append({"kod": "hpolice_nevejde", "dily": [], "text": "Police mezi zadními stojkami se sem nevejde – stůl je málo hluboký pro tento typ police (vyberte jiný typ, nebo ji vypněte)."})
    elif hpolice_info and hpolice_info.get("problem") == "sekce":
        problemy.append({"kod": "hpolice_nevejde", "dily": [], "text": "Šikmá police mezi zadními stojkami zatím nejde u stolu se střední zadní nohou (na jednu stojku by se nevešly dvě konzole) – zvolte vestavěný rám, nebo jiný typ police."})
    if panely_info.get("elzlab_bez_opory") and ("t", ELZLAB) in clenove:
        problemy.append({"kod": "elzlab_bez_opory", "dily": [idx[("t", ELZLAB)]], "text": "Elektrožlab se musí dotýkat panelu nebo profilu – posuň ho zpět k panelu."})
    if p["vzpery"] and not _sd()["vzpery"]:
        problemy.append({"kod": "vzpery_potreba", "dily": [],
                         "text": f"Šikmé vzpěry ramen LED zatím nejsou v systému {p['system']} k dispozici (šikmá spojka 45° pro profil {_P():.0f}×{_P():.0f} není zpracovaná)."})
    elif p["vzpery"] and not (p["stojky"] and p["led"]):
        problemy.append({"kod": "vzpery_potreba", "dily": [],
                         "text": "Šikmé vzpěry ramen LED se montují mezi zadní stojky a ramena LED – bez zadních stojek a LED osvětlení je nelze zapnout."})
    if not p["stojky"] and (p["panely"] or p["led"] or p["elektrozlab"]):
        problemy.append({"kod": "stojky_potreba", "dily": [],
                         "text": "Perforované panely, LED osvětlení a elektrožlab se montují na zadní stojky – bez nich je nelze zapnout."})
    elif not p["stojky"] and p["hpolice"]:
        problemy.append({"kod": "stojky_potreba", "dily": [], "text": "Police mezi zadními stojkami se montuje na zadní stojky – bez nich ji nelze zapnout."})
    elif p["elektrozlab"] and not p["panely"]:
        problemy.append({"kod": "elektrozlab_bez_panelu", "dily": [],
                         "text": "Elektrožlab se montuje na perforovaný panel – bez panelu ho nelze zapnout."})
    # vyrezy: otvory se nesmi prekryvat ani se priblizit na mene nez VYREZ_MEZERA (pruh desky mezi nimi by se ulomil)
    for ai, a in enumerate(vyrezy):
        for b in vyrezy[ai + 1:]:
            if not (a["x1"] + VYREZ_MEZERA <= b["x0"] or b["x1"] + VYREZ_MEZERA <= a["x0"]
                    or a["z1"] + VYREZ_MEZERA <= b["z0"] or b["z1"] + VYREZ_MEZERA <= a["z0"]):
                problemy.append({"kod": "vyrez_prekryv", "dily": [], "vyrez": b["n"],
                                 "text": f"Výřezy {a['n']} a {b['n']} se překrývají nebo jsou blíž než {VYREZ_MEZERA:.0f} mm od sebe."})
    for n in polvyr_nizka:
        problemy.append({"kod": "police_vyrez_nizka", "dily": [], "vyrez": n, "polvyr": n,
                         "text": f"Police pod výřezem {n} se nevejde pod stůl (nízká pracovní deska)."})
    if loz_info and loz_info["moc"]:
        problemy.append({"kod": "loz_moc", "dily": [],
                         "text": f"Ložiskových jednotek by bylo {loz_info['navrh']} (nejvíc {MAX_LOZ}) – zvětši rozteč nebo vzdálenost od okraje."})
    spoje = sorted((i, j) for i in prof_idx for j in peers[i] if j in set(prof_idx))
    suplik_meze = _suplik_meze(bb, clenove, spojky, idx, float(posun_fyz), bool(p["suplik_vlevo"]), float(suplik_K)) if (p["suplik"] and ("t", BOX) in clenove) else None
    return {
        "vzpera_meze": vz_meze,
        "navlek_meze": navlek_meze,
        "suplik_meze": suplik_meze,
        "pet_meze": pet_meze,
        "police_meze": police_meze,
        "panely_info": panely_info,
        "hpolice_info": hpolice_info,
        "led_info": led_info,
        "stojky_meze": {"hodnota": float(nast), "min": float(stojky_min), "max": float(ROZSAH["stojky_vyska"][1])} if p["stojky"] else None,
        "vyrezy": vyrezy,
        "loz": loz_info,
        "parametry": p,
        "dily": dily,
        "problemy": problemy,
        "rozmery": _rozmery([b for b, k in zip(bb, poradi) if not _je_zasl(k)]),          # vnejsi rozmery stolu BEZ zaslepek volnych koncu (3 mm priruby nesmi menit rozmer ani vysku stolu)
        "vodici_scena": vodici,
        "max_polic": n_max,
        "info": ([{"kod": "police_podpery", "podpery": len(z_podpery), "kraceni_mm": bok_kraceni_desky(), "urovni": n_pol, "hloubka_mm": int(prah_hloubky())}] if (bocni_profil and p["police"] and ("t", DESKA_POLICE) in clenove) else [])
                + ([{"kod": "deska_podpery", "podpery": len(z_podpery_d), "suplik": bool(("t", XRAIL_BOX1) in clenove), "hloubka_mm": int(prah_hloubky())}] if (bocni_profil and ("t", DESKA_PRAC) in clenove) else [])
                + ([{"kod": "stredni_rada_noh", "hloubka_mm": int(prah_hloubky_noha()), "pricek": len(urovne_rady)}] if rada_noh else []),
        "spoje": [list(x) for x in spoje],
        "pocet_spoju": len(spoje),
        "klice": [list(k) if isinstance(k, tuple) else k for k in poradi],
    }


# ---------------------------------------------------------------------------------------------------------------------
# automaticke odebrani prislusenstvi, ktere se nevejde / koliduje (Robert 2026-10-02: zuzi-li se deska a jakykoli komponent, napr. suplik,
# jde do kolize s nohama, musi se takovy komponent AUTOMATICKY ODSTRANIT)
# ---------------------------------------------------------------------------------------------------------------------
# dil -> prepinac, ktery ho vytvari
PREPINAC_DILU = {"product_3251": "patky", "product_3283": "patky", **{pid_: "suplik" for pid_ in SUPLIK_PARTY_VSE}, **{pid_: "panely" for pid_ in PANEL_PARTY}, **{pid_: "led" for pid_ in LED_PARTY}, "product_4932": "elektrozlab",
                 "product_4928": "drzak_pet", "product_4916": "kolecka", VZPERA_SPOJKA: "vzpery", "product_3220": "vzpery", NAVLEK_PART: "navlek", NAVLEK_ZASLEPKA: "navlek"}
# jekl a zaslepka navleku odpovidaji prepinaci "navlek" (zanoreni jineho dilu do jeklu u moc nizkeho stolu = navlek se nevejde, odebere se); vyjimka: je-li pricinou rucne zadana vyska police
# (problem `police_vyska`), navlek se NEODEBERE a chyba zustane - viz _co_odebrat (kontrola 2026-10-05: tiche odebrani navleku s nepravdivym duvodem pri rucne nastavene police)
# poradi odebirani (prvni se odebere nejdriv): drobnosti, pak vetsi celky; kolecka az nakonec. Vzpery ramen LED stoji a padaji s LED a stojkami (odebiraji se uplne prvni)
PORADI_ODEBRANI = ("vzpery", "hpolice", "drzak_pet", "elektrozlab", "suplik", "led", "panely", "patky", "kolecka", "navlek")
NAZVY_PREPINACU = {"patky": "Stavitelné patky", "suplik": "Šuplíky", "panely": "Perforované panely", "led": "LED osvětlení", "elektrozlab": "Elektrožlab",
                   "drzak_pet": "Držák PET lahve", "kolecka": "Kolečka", "vzpery": "Šikmé vzpěry ramen LED", "navlek": "Návlek nohou", "hpolice": "Police mezi zadními stojkami"}


def _problem_police_vyrez(r, pr):
    """Cislo vyrezu (1-3), jehoz police pod otvorem se tyka problem `pr` (nektery z jejich dilu patri k ni), jinak None."""
    if pr.get("polvyr"):
        return pr["polvyr"]
    for i in pr.get("dily") or []:
        k = r["klice"][i] if 0 <= i < len(r["klice"]) else None
        if isinstance(k, list) and k and k[0] == "polvyr":
            return k[1]
    return None


def _co_odebrat(r, p):
    """Prepinace (z PORADI_ODEBRANI), jejichz prislusenstvi zpusobuje problem v sestave `r`: vraci [(prepinac, text problemu)]."""
    if _je_sse(p):
        return _sse().co_odebrat(r, p)
    kandidati = {}
    police_vyska = any(pr["kod"] == "police_vyska" for pr in r["problemy"])               # rucne zadana vyska police pod navlekem: navlek za to nemuze (nema se potichu odebrat)
    for pr in r["problemy"]:
        if pr["kod"] in ("navlek_vyska", "navlek_potreba") and p["navlek"]:
            return [("navlek", pr["text"])]                  # navlek se nevejde / neni v systemu: nejdriv pryc on (ostatni kolize jsou jen jeho nasledek), az pak prislusenstvi
    for pr in r["problemy"]:
        kod = pr["kod"]
        if kod == "hpolice_nevejde":
            if p["hpolice"]:
                kandidati.setdefault("hpolice", pr["text"])
            continue
        if kod == "stojky_potreba":
            for k in ("panely", "led", "elektrozlab", "hpolice"):
                if p[k]:
                    kandidati.setdefault(k, pr["text"])
            continue
        if kod == "elektrozlab_bez_panelu":
            kandidati.setdefault("elektrozlab", pr["text"])
            continue
        if kod == "panel_nevejde":
            if p["panely"]:
                kandidati.setdefault("panely", pr["text"])
            continue
        if kod in ("vzpery_potreba", "vzpera_kolize"):
            if p["vzpery"]:
                kandidati.setdefault("vzpery", pr["text"])
            continue
        if kod == "kratka_noha" and (p["kolecka"] or p["patky"]):
            kandidati.setdefault("kolecka" if p["kolecka"] else "patky", pr["text"])
            continue
        if kod in ("navlek_vyska", "navlek_potreba") or (kod == "kratka_noha" and p["navlek"]):
            if p["navlek"]:
                kandidati.setdefault("navlek", pr["text"])              # navlek se nevejde pod stul / neni v systemu: odebere se (kolecka ani patky se nevraci - zustanou zaslepky)
            continue
        if _problem_police_vyrez(r, pr):
            continue                                  # kolize police pod vyrezem se resi odebranim TE police (nabidka), ne prislusenstvi
        for i in pr.get("dily") or []:
            tg = PREPINAC_DILU.get(r["dily"][i]["part_id"]) if 0 <= i < len(r["dily"]) else None
            kl_i = r["klice"][i] if 0 <= i < len(r["klice"]) else None
            if isinstance(kl_i, list) and kl_i and kl_i[0] == "panrail":
                tg = "panely"                                   # profily nad/pod panelem stoji a padaji s panely
            if isinstance(kl_i, (list, tuple)) and kl_i and kl_i[0] == "hpol":
                tg = "hpolice"                                  # vsechny dily horni police stoji a padaji s ni
            if tg == "navlek" and police_vyska:
                continue                                        # zanoreni jeklu a police zpusobila rucne zadana vyska police (chyba `police_vyska`), ne vyska stolu
            if tg and p[tg]:
                kandidati.setdefault(tg, pr["text"])
    return [(k, kandidati[k]) for k in PORADI_ODEBRANI if k in kandidati]


def _kolizi_zpusobuje_posun(p, tg):
    """True, kdyz je kolize prislusenstvi `tg` zpusobena POSUNEM (posun supliku, poloha stredni nohy): pri vychozich polohach
    by prislusenstvi nekolidovalo. Pak se neodebira samo, ale uzivateli se NABIDNE smazani (Robert)."""
    if _je_sse(p):
        return False                                                    # SSE: poloha supliku se orizne na dostupne rozpeti, kolize posunem nevznika
    if (p["suplik_posun"] == 0 and p["stredni_noha"] is None and not p["suplik_vlevo"] and p["pet_posun"] == 0 and p["pet_noha"] == "PL" and p["pet_strana"] == "vpravo"
            and p["panely_posun"] == 0 and p["panely_z"] == 0 and p["elzlab_y"] == 0 and p["elzlab_z"] == 0 and p["hpolice_vyska"] is None):
        return False
    ref = dict(p)
    ref["panely_posun"], ref["panely_z"], ref["elzlab_y"], ref["elzlab_z"] = 0.0, 0.0, 0.0, 0.0           # posun panelu / elektrozlabu si zvolil zakaznik: kolize se NABIDNE odebrat, dil se sam neodebere
    ref["suplik_posun"] = 0.0
    ref["hpolice_vyska"] = None                                         # vysku horni police si zvolil zakaznik: kolize se NABIDNE odebrat, police se sama neodebere
    ref["suplik_vlevo"] = False
    ref["pet_posun"] = 0.0
    ref["pet_noha"], ref["pet_strana"] = "PL", "vpravo"                 # umisteni drzaku PET si zvolil zakaznik: kolize se NABIDNE odebrat, drzak se sam neodebere
    ref["stredni_noha"] = None
    r0 = _sestav_jadro(ref)
    return tg not in [t for t, _ in _co_odebrat(r0, ref)]


def sestav_stul(**vstup):
    """Vytvori dily stolu pro dane parametry (viz modul). Vraci dict:
      parametry (EFEKTIVNI - po automatickem odebrani), dily, problemy, rozmery, spoje, pocet_spoju, odebrano, nabidky_odebrani, ...
    Prislusenstvi (suplik, panely, LED, elektrozlab, drzak PET, kolecka), ktere se pri danych ROZMERECH nevejde nebo koliduje s nohama/dily,
    se AUTOMATICKY ODEBERE (po jednom, poradi PORADI_ODEBRANI) a vypocet se zopakuje; co se odebralo, je v `odebrano`
    [{"volba", "nazev", "text"}]. Kolize zpusobena POSUNEM (posun supliku, poloha stredni nohy) se neodebira samo: zustane v `problemy`
    a uzivateli se NABIDNE smazani prislusenstvi (`nabidky_odebrani`). Vyhodi StulChyba jen u neplatneho vstupu; ostatni porusena
    pravidla jdou do `problemy`.
    """
    p = _norm_parametry(vstup)
    odebrano = []
    nabidky = []
    suplik_pozadovano = int(p["suplik_pocet"])
    for _ in range(len(PORADI_ODEBRANI) + 1 + len(SUPLIK_POCTY)):
        r = _sestav_jadro(p)
        p = dict(r["parametry"])
        co = _co_odebrat(r, p)
        nabidky = []
        auto = []
        for tg, text in co:
            if _kolizi_zpusobuje_posun(p, tg):
                nabidky.append({"volba": tg, "nazev": NAZVY_PREPINACU[tg], "text": text})
            else:
                auto.append((tg, text))
        if not auto:
            break
        tg, text = auto[0]
        if tg == "suplik" and int(p["suplik_pocet"]) > SUPLIK_POCTY[0]:
            p["suplik_pocet"] = int(p["suplik_pocet"]) - 1          # box s tolika supliky se nevejde (vyssi box pod deskou, police...): zkusi se mensi (jako pocet panelu), az nakonec se box odebere
            continue
        p[tg] = False
        odebrano.append({"volba": tg, "nazev": NAZVY_PREPINACU[tg], "text": text})
    videno = set()
    for pr in r["problemy"]:
        if pr["kod"] == "vyrez_prekryv":
            n = pr["vyrez"]
            nabidky.append({"volba": f"vyrez{n}", "nazev": f"Výřez {n}", "text": pr["text"]})
            continue
        n = _problem_police_vyrez(r, pr)
        if n and n not in videno:
            videno.add(n)
            nabidky.append({"volba": f"vyrez{n}_police", "nazev": f"Police pod výřezem {n}", "text": pr["text"]})
    r["odebrano"] = odebrano
    r["nabidky_odebrani"] = nabidky
    r["suplik_orez"] = ({"pozadovano": suplik_pozadovano, "pocet": int(p["suplik_pocet"])}
                        if (p["suplik"] and int(p["suplik_pocet"]) < suplik_pozadovano) else None)           # pozadovany pocet supliku byl snizen (vyssi box se nevejde)
    return r


def vzpera_meze(**vstup):
    """PRESNE meze delky sikme vzpery (profilu) pro dane (EFEKTIVNI) parametry: {"hodnota", "min", "max", "vejde"} nebo None, kdyz vzpery nejsou zapnute. Horni mez dava rameno LED,
    vyska stojky a dily v okoli (nejvetsi platna delka po 10 mm; mene nez spodni mez 100 mm se nevejde nic). Pro jezdec delky v UI (staff odpoved, verejne options.bracelen)."""
    p = _norm_parametry(vstup)
    if not (p["vzpery"] and p["stojky"] and p["led"]):
        return None
    return _sestav_jadro(p, meze=True)["vzpera_meze"]


def _zustane(p, k):
    """Zustane prepinac `k` zapnuty pri parametrech `p` (jeden pruchod jadrem: neni mezi kandidaty na odebrani)? Rychle (bez smycky odebirani)."""
    try:
        r = _sestav_jadro(p)
    except StulChyba:                      # varianta, kterou generator odmitne (napr. pevna poloha stredni nohy, ktera se u sirsiho stolu uz nevejde do tabule), se nenabizi
        return False
    return k not in [t for t, _ in _co_odebrat(r, r["parametry"])]


def _min_hodnota(p, k, par, hodnoty):
    """Nejmensi hodnota posuvniku `par` (z vzestupneho seznamu), pri ktere prepinac `k` zustane zapnuty; None, kdyz ani nejvetsi nestaci."""
    if not hodnoty:
        return None
    def ok(v):
        return _zustane({**p, par: v, k: True}, k)
    if not ok(hodnoty[-1]):
        return None
    lo, hi = 0, len(hodnoty) - 1
    while lo < hi:
        mid = (lo + hi) // 2
        if ok(hodnoty[mid]):
            hi = mid
        else:
            lo = mid + 1
    return hodnoty[lo]


def nabidky_police(**vstup):
    """Kdyz se DALSI spodni police uz nevejde (dosazen max_polic): co by ji umoznilo. Vraci {"cil": n+1, "vyska": mm | None, "bez_supliku": bool}
    (vyska = nejnizsi vyska pracovni desky po 10 mm, pri ktere se vejde; bez_supliku = vejde se, kdyz se odeberou supliky) nebo None, kdyz se
    dalsi police vejde, nebo uz je nejvyssi zadatelny pocet. (Robert: pocet polic ma jit libovolne zvysovat - tlacitko + nabidne zvyseni stolu/odebrani supliku.)"""
    if _je_sse(vstup):
        return None                                                              # SSE: jedna spodni police, dalsi nejsou
    r = sestav_stul(**vstup)
    p = r["parametry"]
    cil = p["police"] + 1
    if cil > MAX_POLIC or r["max_polic"] >= cil:
        return None
    out = {"cil": cil, "vyska": None, "bez_supliku": False}
    if p["suplik"] and sestav_stul(**{**p, "suplik": False})["max_polic"] >= cil:
        out["bez_supliku"] = True
    hodnoty = list(range(int(p["vyska"]) // 10 * 10 + 10, int(ROZSAH["vyska"][1]) + 1, 10))
    if hodnoty and sestav_stul(**{**p, "vyska": float(hodnoty[-1])})["max_polic"] >= cil:
        lo, hi = 0, len(hodnoty) - 1
        while lo < hi:                                  # max_polic s vyskou neklesa
            mid = (lo + hi) // 2
            if sestav_stul(**{**p, "vyska": float(hodnoty[mid])})["max_polic"] >= cil:
                hi = mid
            else:
                lo = mid + 1
        out["vyska"] = hodnoty[lo]
    return out


def nabidky_roztazeni(**vstup):
    """Pro kazdy VYPNUTY prepinac, ktery by se po zapnuti hned automaticky odebral, najde nejmensi roztazeni stolu (nohou), pri kterem se
    vejde: {prepinac: {"sirka": mm} | {"hloubka": mm} | None}. Sirka: v krocich 10 mm od aktualni vyse; kdyz sama sirka nestaci, zkusi hloubku.
    (Robert: opetovne zapnuti komponentu, na ktery je mezi nohama malo mista, nabidne roztazeni nohou na minimalni delku komponentu + 30 mm
    z kazde strany.) None = roztazeni nepomuze (napr. vyska, chybejici zadni stojky)."""
    if _je_sse(vstup):
        return {}                                                                # SSE: supliky se vejdou nebo ne podle hloubky/sirky, jine volby nema
    p = sestav_stul(**vstup)["parametry"]
    out = {}
    for k in PREPINACE + ("vzpery",):
        if p[k] or k == "stojky" or k == "navlek" or (k in ("kolecka", "patky") and p["navlek"]):
            continue                                                             # navlek (a kolecka / patky pri navleku) se roztazenim stolu nezachrani
        if k == "vzpery" and not SYSTEMY[p["system"]]["vzpery"]:
            continue                                                             # system bez sikmych vzper (40): roztazeni nepomuze
        pk = {**p, "stojky": True, "led": True} if k == "vzpery" else p        # vzpery zapnou stojky i LED samy (stranka) - nabidka se pocita pro stav s nimi
        if _zustane({**pk, k: True}, k):
            continue
        nab = {}
        w = _min_hodnota(pk, k, "sirka", [float(v) for v in range(int(pk["sirka"]) + 10, int(ROZSAH["sirka"][1]) + 1, 10)])
        if w is not None:
            nab = {"sirka": int(w)}
        else:
            d = _min_hodnota(pk, k, "hloubka", [float(v) for v in range(int(pk["hloubka"]) + 10, int(_rozsahy(pk["system"])["hloubka"][1]) + 1, 10)])
            nab = {"hloubka": int(d)} if d is not None else {}
        if not nab and k in ("panely", "hpolice"):                                 # panel / horni police se nevejde na nizke zadni stojky: nabidka je zvysit stojky
            hv = _min_hodnota(pk, k, "stojky_vyska", [float(v) for v in range(int(pk["stojky_vyska"]) + 10, int(ROZSAH["stojky_vyska"][1]) + 1, 10)])
            nab = {"stojky_vyska": int(hv)} if hv is not None else {}
        if k == "vzpery" and pk["panely"] and _zustane({**pk, "vzpery": True, "panely": False, "elektrozlab": False}, "vzpery"):
            nab["vypnout"] = ["panely", "elektrozlab"]                           # u uzsiho stolu vzpery zakryvaji panely: druha cesta = panely (a elektrozlab) vypnout
        out[k] = nab or None
    return out


# ---------------------------------------------------------------------------------------------------------------------
# kontrola
# ---------------------------------------------------------------------------------------------------------------------
_AABB_MEMO = {}          # (dil, otoceni, meritko, poloha) -> (lo, hi): sestav_stul se v odpovedi vola desitky krat (sondy, nabidky) nad temi samymi dily; pole jsou jen ke cteni


def _aabb(cast):
    q, sc, pos = cast["quaternion"], cast["scale"], cast["position"]
    klic = (cast["part_id"], len(BBOX_PREPIS), q[0], q[1], q[2], q[3], sc[0], sc[1], sc[2], pos[0], pos[1], pos[2])
    r = _AABB_MEMO.get(klic)
    if r is None:
        lo, hi = glb_bbox(cast["part_id"])
        Rm = kvat_na_matici(q)
        s = np.array(sc, float)
        rohy = np.array([[x, y, z] for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])])
        w = (rohy * s) @ Rm.T + np.array(pos, float)
        lo_w, hi_w = w.min(axis=0), w.max(axis=0)
        lo_w.setflags(write=False)
        hi_w.setflags(write=False)
        if len(_AABB_MEMO) > 40000:                                   # ~20 MB na worker; plne se vyprazdni (jednoduche, bez LRU)
            _AABB_MEMO.clear()
        r = _AABB_MEMO[klic] = (lo_w, hi_w)
    return r


def _rozmery(bb):
    lo = np.min([b[0] for b in bb], axis=0)
    hi = np.max([b[1] for b in bb], axis=0)
    ext = hi - lo
    return {"x_min": float(lo[0]), "x_max": float(hi[0]), "y_min": float(lo[1]), "y_max": float(hi[1]),
            "z_min": float(lo[2]), "z_max": float(hi[2]),
            "hloubka_mm": float(ext[0]), "vyska_mm": float(ext[1]), "sirka_mm": float(ext[2])}


def _dotyk_cela(a, b):
    """Stejny test jako dimension_match_fbx._profiles_touch: na jedne ose mezera <= 1,5 mm (dotyk celem) a na
    OBOU zbylych osach prekryv >= mensi rozmer - 0,5 mm (cela plocha cela lezi na druhem profilu)."""
    for k in range(3):
        mezera = max(a[0][k] - b[1][k], b[0][k] - a[1][k])
        if mezera > TOL_SPOJ_MM:
            continue
        ok = True
        for o in range(3):
            if o == k:
                continue
            prek = min(a[1][o], b[1][o]) - max(a[0][o], b[0][o])
            mensi = min(a[1][o] - a[0][o], b[1][o] - b[0][o])
            if prek < mensi - TOL_PREKRYV_MM:
                ok = False
                break
        if ok:
            return True
    return False


def _konec_dosedá(bb, i, e, sg, k, plocha_i, profily_bb):
    """Dosedá konec `e` (-1/+1 po ose profilu) profilu i celou plochou na nejaky jiny profil?"""
    lo_i, hi_i = bb[i]
    P = (lo_i[k] if (e * sg) < 0 else hi_i[k])
    for j, (lo, hi) in profily_bb.items():
        if j == i:
            continue
        if not (lo[k] - TOL_SPOJ_MM <= P <= hi[k] + TOL_SPOJ_MM):
            continue
        ok = True
        for o in range(3):
            if o == k:
                continue
            prek = min(hi_i[o], hi[o]) - max(lo_i[o], lo[o])
            if prek < (hi_i[o] - lo_i[o]) - TOL_PREKRYV_MM:
                ok = False
                break
        if ok:
            return True
    return False


_KONCE_SAB = {}            # system -> {index profilu: (dosedá konec -, dosedá konec +)}


def _konce_sablony(sab):
    """{index profilu sablony: (dosedá konec -, dosedá konec +)} podle GEOMETRIE sablony AKTIVNIHO systemu (po ose profilu)."""
    s = _SYSTEM.get()
    if s not in _KONCE_SAB:
        bb = {i: _aabb(sab[i]) for i in PROFILY}
        out = {}
        for i in PROFILY:
            k, sg = _osa(sab[i]["quaternion"])
            out[i] = tuple(_konec_dosedá(bb, i, e, sg, k, None, bb) for e in (-1, +1))
        _KONCE_SAB[s] = out
    return _KONCE_SAB[s]


_NAZVY = {"Object_7": "profil 30×30", "Object_11": "profil 40×40", "profil_35x35": "profil 35×35", "product_3090": "záslepka profilu 35×35", "product_3176": "rohová spojka 40×40", "product_3091": "záslepka profilu 40×40", "product_3283": "stavitelná patka M10", "product_4933": "laminodeska", "product_4930": "šuplíkový box",
          "product_4931": "perforovaný panel", "product_4929": "LED osvětlení", "product_4932": "elektrožlab",
          "product_4928": "držák PET lahve", "product_4916": "kolečko", "product_3158": "rohová spojka", "product_3254": "šikmá spojka 45° (30)", "product_3220": "šikmá spojka 45° (40)", "product_3025": "ložisková jednotka", "product_3071": "záslepka profilu", "product_3251": "stavitelná patka",
          NAVLEK_PART: f"návlek nohy – jekl 40×40×2, {NAVLEK_BARVA} lesk", NAVLEK_ZASLEPKA: "záslepka jeklu 40×40"}
_NAZVY.update({"product_4956": "šuplíkový box (1 šuplík)", "product_4957": "šuplíkový box (3 šuplíky)"})
_NAZVY.update({"product_3323": "úhlová naklápěcí konzola (drážka 8)", "product_3324": "úhlová naklápěcí konzola (drážka 10)"})             # sikma horni police (2. kolo)
_NAZVY.update({"product_3939": "MDF deska 8 mm (police)", "product_3539": "překližka PR10 10 mm (police)", "product_3045": "úhelníková spojka 30×30", "product_3207": "úhelníková spojka 40×40",
               "product_5360": "laminovaná dřevotříska 12 mm (police)"})                            # horní police (Robert 2026-10-07); 5360 = karta desky 12 mm (cislo doplni nasazeni)
_NAZVY.update({pid_: f"LED osvětlení {d_} mm" for d_, pid_ in LED_TYPY.items() if pid_ != LED_PART})        # delka v nazvu: kusovnik / nabidka rozlisi delky (LED 1200 beze zmeny)
_NAZVY.update({pid_: f"perforovaný panel {d_} mm" for d_, pid_ in PANEL_TYPY.items() if pid_ != PANEL_PART})        # delka v nazvu: kusovnik / nabidka rozlisi delky (panel 1190 beze zmeny)
_NAZVY.update({SSE_JEKL_PART: "jekl 40×40 (noha SSE)", SSE_PROFIL_PART: "vnitřní profil 35×35 (noha SSE)", SSE_PLECH_PART: "plechová patka 150×40×6 (noha SSE)", SSE_PATKA_PART: "záslepka vnitřního profilu 35×35 (noha SSE)"})          # box s 1 a 3 supliky (karty #4956, #4957); dvojsuplik 4930 zustava "šuplíkový box"


# SPOJOVACI MATERIAL KE SPOJKAM (Robert 2026-10-04: "k rohovym prvkum je potreba pripocitavat do kusovniku imbusove srouby s valcovou hlavou (M6x12 mm 2ks 2.1.21.0612) a otocne matice
# 2ks 2.1.001.08.06; k uhelnikum zapustne imbusove srouby, pocita se delka vcetne hlavy (M6x14 mm 2ks) a otocne matice 2ks 2.1.001.08.06"). Klic = part_id spojky, hodnota = [(SKU, ks na
# JEDNU spojku, nazev)]. Rohova spojka 30x30 = "rohovy prvek" (product_3158), Spojka uhel 45 st. = "uhelnik" (product_3254) - PREDPOKLAD vykladu Robertovych slov, ke kontrole.
# SKU zapustneho sroubu M6x14 Robert nezadal -> None (radek v kusovniku je, bez karty a ceny, dokud SKU nepribude).
SPOJOVACI_MATERIAL = {
    "product_3158": [("2.1.21.0612", 2, "Šroub imbus s válcovou hlavou M6×12"), ("2.1.001.08.06", 2, "Otočná matice M6 (drážka 8)")],
    "product_3254": [(None, 2, "Šroub imbus se zápustnou hlavou M6×14 (délka včetně hlavy)"), ("2.1.001.08.06", 2, "Otočná matice M6 (drážka 8)")],
    # SYSTEM 40 (bot10, 2026-10-04): rohova spojka 3176 (plech 7,25 mm misto 4 mm) - sroub M6x16 (2.1.21.0616, karta 4945) je NAVRH: stejne zavitu v matici jako M6x12 u 3158 (16 - 7,25 = 8,75 mm
    # proti 12 - 4 = 8 mm); otocna matice do drazky 10 (2.1.001.10.06, karta 3582). DELKU SROUBU OVERIT u karty spojky / Robertem.
    "product_3176": [("2.1.21.0616", 2, "Šroub imbus s válcovou hlavou M6×16"), ("2.1.001.10.06", 2, "Otočná matice M6 (drážka 10)")],
    # sikma spojka 3220 (vzpery ve 40): delku a SKU zapustneho sroubu urci Robert (jako u 3254 - SKU None = radek v kusovniku bez karty a ceny), matice do drazky 10
    "product_3220": [(None, 2, "Šroub imbus se zápustnou hlavou M6 (délka včetně hlavy – určí Robert)"), ("2.1.001.10.06", 2, "Otočná matice M6 (drážka 10)")],
    # HORNI POLICE (Robert 2026-10-07): Uhelnikova spojka 30x30 (#3045, drazka 8) / 40x40 (#3207, drazka 10) kotvi prepazku / lem k profilu: 1 sroub M6 + 1 otocna matice do drazky (NAVRH, Robert upresni)
    "product_3045": [("2.1.21.0612", 1, "Šroub imbus s válcovou hlavou M6×12"), ("2.1.001.08.06", 1, "Otočná matice M6 (drážka 8)")],
    "product_3207": [("2.1.21.0616", 1, "Šroub imbus s válcovou hlavou M6×16"), ("2.1.001.10.06", 1, "Otočná matice M6 (drážka 10)")],
    # NAKLAPECI KONZOLE sikme police (2. kolo; NAVRH, Robert upresni): 2 sroubky + 2 matice do drazky na list P1 (stojka) a 2 + 2 na desku P2 (kloub + obloukova drazka v sikmem profilu) = 4 + 4 na konzolu
    "product_3323": [("2.1.21.0612", 4, "Šroub imbus s válcovou hlavou M6×12"), ("2.1.001.08.06", 4, "Otočná matice M6 (drážka 8)")],
    "product_3324": [("2.1.21.0616", 4, "Šroub imbus s válcovou hlavou M6×16"), ("2.1.001.10.06", 4, "Otočná matice M6 (drážka 10)")],
}


def spojovaci_material(dily, nazvy_karet=None):
    """[{sku, nazev, mnozstvi, pro}] - spojovaci material ke spojkam stolu (SPOJOVACI_MATERIAL), sloucene podle SKU / nazvu, v poradi vyskytu. Cista funkce dilu.
    NAZEV je vzdy nazev KARTY z katalogu (`nazvy_karet` = {sku: nazev}, Robert 2026-10-04: "nazvy jsou prece dany v kartach"); text v tabulce je jen nahrada pro SKU bez karty."""
    out = OrderedDict()
    for d in dily:
        for sku, ks, nazev in SPOJOVACI_MATERIAL.get(d["part_id"], []):
            nazev = (nazvy_karet or {}).get(sku) or nazev
            q = out.setdefault((sku, nazev), {"sku": sku, "nazev": nazev, "mnozstvi": 0, "pro": set()})
            q["mnozstvi"] += ks
            q["pro"].add(_NAZVY.get(d["part_id"], d["part_id"]))
    return [{"sku": q["sku"], "nazev": q["nazev"], "mnozstvi": q["mnozstvi"], "pro": sorted(q["pro"])} for q in out.values()]


def _jmeno(cast, i):
    """Srozumitelný název dílu pro text problému: 'profil 30×30 #7'."""
    return f"{_NAZVY.get(cast['part_id'], cast['part_id'])} #{i}"


def _zkontroluj_navlek(dily, bb, clenove, idx, p, navlek_meze, navlek_vrch):
    """NAVLEK NOHOU (Robert 2026-10-05): (a) jen v systemech s navlekem, (b) vejde se pod stul dane vysky (delka aspon 200 mm, nad nim NAVLEK_MEZERA_NAD (3 mm) volneho mista a pak spodek rámu), (c) V UROVNI NAVLEKU
    ZADNY JINY KOMPONENT: nic krome nohou (zasunute v jeklu), jeklu a zaslepek nesmi mit spodek pod hornim koncem jeklu + NAVLEK_MEZERA_NAD (police, drzak PET, supliky, police pod vyrezem...)."""
    out = []
    if p.get("navlek") and _SYSTEM.get() not in NAVLEK_SYSTEMY:
        out.append({"kod": "navlek_potreba", "dily": [],
                    "text": f"Návlek nohou je jen v systému 35 (profil 35×35 se vejde do jeklu 40×40×2) – v systému {p['system']} ho nelze zapnout."})
        return out
    if not navlek_meze:
        return out
    if not navlek_meze["vejde"]:
        out.append({"kod": "navlek_vyska", "dily": [],
                    "text": (f"Návlek nohou (nejméně {navlek_meze['min']:.0f} mm) se pod tak nízký stůl nevejde: nad jeho horním koncem musí zůstat {NAVLEK_MEZERA_NAD:.0f} mm volného místa "
                             f"a pak spodek rámu (u stolu s policí i police) – stůl by musel být aspoň o {navlek_meze['chybi_mm']:.0f} mm vyšší.")})
        return out
    hrana = navlek_vrch + NAVLEK_MEZERA_NAD
    vlastni = {idx[k] for k in clenove if k in NOHY_KLICE or (isinstance(k, tuple) and k[0] == "konec" and len(k) == 3)}
    zasah = [i for i in range(len(dily)) if i not in vlastni and float(bb[i][0][1]) < hrana - 0.01]
    if zasah:
        jmena = ", ".join(_jmeno(dily[i], i) for i in zasah[:4]) + (" …" if len(zasah) > 4 else "")
        out.append({"kod": "navlek_kolize", "dily": zasah,
                    "text": f"V úrovni návleku (do výšky {navlek_meze['horni_mm'] + NAVLEK_MEZERA_NAD:.0f} mm nad podlahou) nesmí být žádný jiný komponent: {jmena}. "
                            f"Zkrať návlek, zvyš stůl nebo komponent přesuň výš."})
    return out


def _zkontroluj_vzpery(dily, bb, idx, vz_info):
    """Kontrola sikmych vzper (PRESNA - obecna AABB kontrola `_zkontroluj` je pro sikmy profil nepouzitelna): profil vzpery (OBB) se nesmi protinat se stojkou ani ramenem
    ani s zadnym jinym dilem, spojky (AABB) s zadnym dilem krome stojky/ramene, na ktere lezi (zasahuji do jejich T-drazky), a spojka u ramene musi cela lezet pod ramenem.
    Vraci problemy s kodem `vzpera_kolize` (stul s takovou vzperou se nenabizi - vzpery se automaticky odeberou)."""
    problemy = []
    vsechny_vz = {idx[k] for vi in vz_info for k in (vi["prof"], vi["dole"], vi["nahore"])}
    for vi in vz_info:
        i_prof, i_d, i_n = idx[vi["prof"]], idx[vi["dole"]], idx[vi["nahore"]]
        i_post, i_arm = idx[vi["post"]], idx[vi["arm"]]
        d = dily[i_prof]
        Rm = kvat_na_matici(d["quaternion"])
        c = np.array(d["position"], float)
        h = np.array([_H(), 500.0 * d["scale"][1], _H()])
        vlastni = {i_prof, i_d, i_n}
        # profil vs. stojka a rameno: bez pruniku (vzpera lezi v rohu s odstupem, jejich spojeni dela jen spojka)
        for nazev, j in (("zadní stojkou", i_post), ("ramenem LED", i_arm)):
            hl = _sat_obb_aabb(c, Rm, h, bb[j][0], bb[j][1])
            if hl > TOL_PRUNIK_MM:
                problemy.append({"kod": "vzpera_kolize", "dily": [i_prof, j], "text": f"Vzpěra ramene LED se protíná se {nazev} o {hl:.1f} mm."})
        for j in range(len(dily)):
            if j in vlastni or j in (i_post, i_arm):
                continue
            hl = _sat_obb_aabb(c, Rm, h, bb[j][0], bb[j][1])
            if hl > TOL_PRUNIK_MM:
                problemy.append({"kod": "vzpera_kolize", "dily": [i_prof, j], "text": f"Vzpěra ramene LED koliduje s dílem {_jmeno(dily[j], j)} (o {hl:.1f} mm)."})
            for i_s in (i_d, i_n):
                pr = np.minimum(bb[i_s][1], bb[j][1]) - np.maximum(bb[i_s][0], bb[j][0])
                if np.all(pr > 0) and float(pr.min()) > TOL_PRUNIK_MM:
                    problemy.append({"kod": "vzpera_kolize", "dily": [i_s, j], "text": f"Šikmá spojka vzpěry koliduje s dílem {_jmeno(dily[j], j)} (o {float(pr.min()):.1f} mm)."})
        # spojka u ramene cela pod ramenem (jeji plocha lezi na spodku ramene), spojka u stojky nad spodkem stojky
        if bb[i_n][0][0] < bb[i_arm][0][0] - VZPERA_REZERVA_RAMENE - 0.01:
            problemy.append({"kod": "vzpera_kolize", "dily": [i_n, i_arm],
                             "text": f"Vzpěra ({1000.0 * d['scale'][1]:.0f} mm) se nevejde pod rameno LED – rameno je příliš krátké (spojka by přesahovala jeho přední konec)."})
        if bb[i_d][0][1] < bb[i_post][0][1] + _P():
            problemy.append({"kod": "vzpera_kolize", "dily": [i_d, i_post], "text": "Vzpěra sahá příliš nízko na zadní stojce."})
    return problemy


def _zkontroluj(dily, bb, clenove, spojky, idx, konce_ocek, kotvy):
    xf, xr, zl, zr = kotvy
    problemy = []
    # (0) obrys: prislusenstvi se musi vejit na stul (jinak by couhalo ven / viselo ve vzduchu)
    z_vnejsi = (zl - _H(), zr + _H())
    for k, c in clenove.items():
        if c["druh"] != "prisl":
            continue
        i = idx[k]
        lo, hi = bb[i]
        role = c["src"]
        if role == BOX and not (lo[0] >= xf - _H() - 3.0 and hi[0] <= xr - _H() - odstup_od_nohou() + 0.01 and lo[2] >= zl + _H() + odstup_od_nohou() - 0.01 and hi[2] <= zr - _H() - odstup_od_nohou() + 0.01):
            problemy.append({"kod": "mimo_obrys", "dily": [i],
                             "text": f"Šuplíkový box se nevejde mezi nohy a do hloubky stolu (X {lo[0]:.0f}…{hi[0]:.0f}, Z {lo[2]:.0f}…{hi[2]:.0f}; "
                                     f"povoleno X {xf - _H() - 3.0:.0f}…{xr - _H() - odstup_od_nohou():.0f}, Z {zl + _H() + odstup_od_nohou():.0f}…{zr - _H() - odstup_od_nohou():.0f})"})
        elif role in (PANEL_D, PANEL_H) and not (lo[2] >= z_vnejsi[0] - 10.0 and hi[2] <= z_vnejsi[1] + 10.0):
            problemy.append({"kod": "mimo_obrys", "dily": [i],
                             "text": f"Perforovaný panel #{i} ({hi[2] - lo[2]:.0f} mm) je širší než stůl (Z {lo[2]:.0f}…{hi[2]:.0f}, stůl {z_vnejsi[0]:.0f}…{z_vnejsi[1]:.0f})"})
        elif role == ELZLAB and not (lo[2] >= z_vnejsi[0] and hi[2] <= z_vnejsi[1]):
            problemy.append({"kod": "mimo_obrys", "dily": [i],
                             "text": f"Elektrožlab (600 mm) se nevejde na šířku stolu (Z {lo[2]:.0f}…{hi[2]:.0f})"})
    # (0b) suplikovy box ma mit od KAZDE nohy (i stredni) aspon ODSTUP_KOMPONENTU_OD_NOHOU z obou stran (Robert); krajni nohy hlida uz kontrola obrysu vyse
    for k, c in clenove.items():
        if c["druh"] != "prisl" or c["src"] != BOX:
            continue
        i = idx[k]
        lo, hi = bb[i]
        for kn in ["FM", "RM"] + [k_ for k_ in clenove if isinstance(k_, tuple) and k_[0] == "ram"]:          # stredni nohy a svisle profily vestaveneho ramu
            if kn not in clenove:
                continue
            lo_n, hi_n = bb[idx[kn]]
            if min(hi[0], hi_n[0]) - max(lo[0], lo_n[0]) > TOL_PRUNIK_MM and min(hi[1], hi_n[1]) - max(lo[1], lo_n[1]) > TOL_PRUNIK_MM:
                mezera = max(lo_n[2] - hi[2], lo[2] - hi_n[2])
                if mezera < odstup_od_nohou() - 0.01:
                    problemy.append({"kod": "mimo_obrys", "dily": [i, idx[kn]],
                                     "text": f"Šuplíkový box je od střední nohy {mezera:.0f} mm (musí být aspoň {odstup_od_nohou():.0f} mm)"})
    led_idx = [idx[k] for k, c in clenove.items() if c["druh"] == "prisl" and c["src"] == LED]
    led_idx_n = len(led_idx)
    if led_idx:
        lo_z = min(bb[i][0][2] for i in led_idx)
        hi_z = max(bb[i][1][2] for i in led_idx)
        presah = (z_vnejsi[0] - lo_z) + (hi_z - z_vnejsi[1])
        if presah > LED_PREVIS + 1.0:
            problemy.append({"kod": "mimo_obrys", "dily": led_idx,
                             "text": f"LED osvětlení přesahuje stůl o {presah:.0f} mm (povoleno {LED_PREVIS:.0f} mm)"})
    # (0c) FORMAT TABULE laminodesky (Robert 2026-10-05): kazda deska (pracovni, police, police pod vyrezem; leva / prava cast u stredni opory) se musi vejit do tabule (2070 x 2800 mm, v obou
    #      orientacich). Pri vychozi tabuli to hlida horni mez prahu sirky (`prah_sirky`) a meze polohy stredni nohy (`stredni_noha_meze`); problem vznika az u mensi tabule nastavene na karte.
    kusy_desek = {}
    for k, c in clenove.items():
        if c["druh"] == "deska" and c.get("deska_id"):
            kusy_desek.setdefault(c["deska_id"], []).append(idx[k])
    for did, ids_ in kusy_desek.items():
        lo_d = np.min([bb[i][0] for i in ids_], axis=0)
        hi_d = np.max([bb[i][1] for i in ids_], axis=0)
        hloubka_d, sirka_d = float(hi_d[0] - lo_d[0]), float(hi_d[2] - lo_d[2])
        if not deska_se_vejde_do_tabule(hloubka_d, sirka_d):
            kr_, dl_ = tabule()
            problemy.append({"kod": "deska_mimo_tabuli", "dily": ids_, "deska": did, "rozmer": "sirka" if sirka_d - 1e-6 > dl_ or (sirka_d > kr_ and hloubka_d <= kr_) else "hloubka",
                             "text": f"Deska ({_popis_desky(did, bool(kusy_desek.get('prac_1')))}) {max(hloubka_d, sirka_d):.0f} × {min(hloubka_d, sirka_d):.0f} mm se nevejde do tabule laminodesky {dl_:.0f} × {kr_:.0f} mm"})
    # (1) zanoreni dilu (mimo spojky, ktere se do profilu zasouvaji)
    vz_vse = {idx[k] for k in list(clenove) + list(spojky) if _je_vz(k)}          # sikme vzpery se kontroluji presne v _zkontroluj_vzpery
    sk_vse = {idx[k] for k, c in list(clenove.items()) + list(spojky.items()) if _hpol().v_skupine(k, c, clenove)}          # sikma horni police: presna kontrola OBB x AABB (stul_hpolice.zkontroluj)
    nep = [i for i, d in enumerate(dily) if d["part_id"] not in SPOJKY_PARTS + KONCE_PARTS + NAVLEK_PARTS and i not in vz_vse and i not in sk_vse]          # navlek a jeho zaslepka kryji nohu (viz _zkontroluj_navlek)
    vyrez = set()
    desky_polic = [idx[k] for k, c in clenove.items() if c["druh"] == "deska" and k != ("t", DESKA_PRAC) and k[0] not in ("kus", "polvyr")]
    boky = [idx[k] for k in clenove if k[0] == "bok"]
    vyrez = set()             # drivejsi vyjimka desky_polic x boky (rohovy vyrez 30 x 30 mm) je pryc: deska police se pri hloubce > 900 zkracuje o 31 mm z kazde strany, kolize se HLIDA doopravdy
    for k_, c_ in clenove.items():              # deska zasazena do DRAZKY profilu (horni police): jeji obalka zasahuje do profilu o sirku drazky - to je zamer, ne zanoreni
        for kk_ in c_.get("zasazeno_do") or ():
            if k_ in idx and kk_ in idx:
                vyrez.add((min(idx[k_], idx[kk_]), max(idx[k_], idx[kk_])))
    # vektorove: prunik vsech dvojic (n x n x 3); dotyk (< TOL_PRUNIK_MM) se nepocita
    lo = np.array([bb[i][0] for i in nep])
    hi = np.array([bb[i][1] for i in nep])
    pres = np.minimum(hi[:, None, :], hi[None, :, :]) - np.maximum(lo[:, None, :], lo[None, :, :])
    maska = np.all(pres > 0, axis=2) & (pres.min(axis=2) > TOL_PRUNIK_MM)
    maska &= np.triu(np.ones_like(maska, dtype=bool), 1)
    for a, b in zip(*np.nonzero(maska)):
        i, j = nep[a], nep[b]
        if (i, j) in vyrez:
            continue
        problemy.append({"kod": "zanoreni", "dily": [i, j],
                         "text": f"{_jmeno(dily[i], i)} a {_jmeno(dily[j], j)} se překrývají o {pres[a, b].min():.1f} mm"})
    # (1a) uhelniky (spojky) se zasouvaji jen do profilu: s komponentou (box, panel, LED, elektrozlab, drzak PET, deska) se nesmi prekryvat
    # (Robert: "pri kolizi uhelniku s cimkoliv ..."); drive se spojky nekontrolovaly vubec
    spoj_i = [i for i, d in enumerate(dily) if d["part_id"] in SPOJKY_PARTS and i not in sk_vse]
    komp_i = [idx[k] for k, c in clenove.items() if c["druh"] in ("prisl", "deska") and not _je_zasl(k) and idx[k] not in sk_vse]          # zaslepka volneho konce profilu neni komponenta (jeji plast je v profilu; AABB spojky u konce by dala falesne zanoreni)
    if spoj_i and komp_i:
        slo, shi = np.array([bb[i][0] for i in spoj_i]), np.array([bb[i][1] for i in spoj_i])
        klo, khi = np.array([bb[i][0] for i in komp_i]), np.array([bb[i][1] for i in komp_i])
        pr = np.minimum(shi[:, None, :], khi[None, :, :]) - np.maximum(slo[:, None, :], klo[None, :, :])
        mk = np.all(pr > 0, axis=2) & (pr.min(axis=2) > TOL_PRUNIK_MM)
        for a, b in zip(*np.nonzero(mk)):
            i, j = spoj_i[a], komp_i[b]
            problemy.append({"kod": "zanoreni", "dily": [i, j],
                             "text": f"{_jmeno(dily[i], i)} a {_jmeno(dily[j], j)} se překrývají o {pr[a, b].min():.1f} mm"})
    # (1b) profil nad LED (podelny, drzi svetlo): delka dana mezerou mezi nohami, nejkratsi mozna = 90 % delky svetla (skupiny svetel)
    if ("t", ZRAIL_TOP) in clenove and led_idx_n:
        delka_profilu = 1000.0 * clenove[("t", ZRAIL_TOP)]["scale"][1]
        led_z_ = [float(c["pos"][2]) for c in clenove.values() if c["druh"] == "prisl" and c["src"] == LED]
        delka_svetla = (max(led_z_) - min(led_z_)) + led_telo_dilu(next(c["part_id"] for c in clenove.values() if c["druh"] == "prisl" and c["src"] == LED))          # ROZPETI skupiny svitidel (od nejlevejsiho kraje po nejpravejsi; u svitidel tesne vedle sebe soucet delek)
        if delka_profilu < MIN_PODIL_PROFILU_LED * delka_svetla - 0.01:
            problemy.append({"kod": "profil_led_kratky", "dily": [idx[("t", ZRAIL_TOP)]],
                             "text": f"Profil nad LED osvětlením ({delka_profilu:.0f} mm) je kratší než {MIN_PODIL_PROFILU_LED * 100:.0f} % délky světla ({MIN_PODIL_PROFILU_LED * delka_svetla:.0f} mm)."})
    # (2) delky profilu
    for k, c in clenove.items():
        if c["druh"] != "profil":
            continue
        i = idx[k]
        delka = 1000.0 * c["scale"][1]
        noha = k in (("t", NOHA_PL), ("t", NOHA_PP), ("t", NOHA_ZL), ("t", NOHA_ZP), "FM", "RM")
        if noha and delka < min_delka_nohy() - 0.01:
            problemy.append({"kod": "kratka_noha", "dily": [i],
                             "text": f"Noha ({_jmeno(dily[i], i)}) by měla délku {delka:.0f} mm (nejméně {min_delka_nohy():.0f} mm)"})
        elif delka < MIN_DELKA_PROFILU - 0.01:
            problemy.append({"kod": "kratky_profil", "dily": [i],
                             "text": f"{_jmeno(dily[i], i)} by měl délku {delka:.1f} mm (nejméně {MIN_DELKA_PROFILU:.0f} mm)"})
        elif delka > MAX_DELKA_PROFILU + 0.01:
            problemy.append({"kod": "dlouhy_profil", "dily": [i],
                             "text": f"{_jmeno(dily[i], i)} by měl délku {delka:.0f} mm (nejdelší tyč je {MAX_DELKA_PROFILU:.0f} mm)"})
    # (3) napojeni koncu: co v sablone dosedalo, musi dosedat i ted
    profily_bb = {idx[k]: bb[idx[k]] for k, c in clenove.items() if c["druh"] == "profil"}
    for k, c in clenove.items():
        if c["druh"] != "profil":
            continue
        i = idx[k]
        kos, sg = _osa(c["quaternion"])
        for n, e in enumerate((-1, +1)):
            if konce_ocek[k][n] and not _konec_dosedá(bb, i, e, sg, kos, None, profily_bb):
                problemy.append({"kod": "volny_konec", "dily": [i],
                                 "text": f"{_jmeno(dily[i], i)}: {'dolní/přední' if n == 0 else 'horní/zadní'} konec nedosedá na žádný profil (není napojen)"})
    # (4) spojky sedi na svem spoji (prekryvaji oba vlastniky)
    for k, s in spojky.items():
        i = idx[k]
        for vl in s["vlastnici"]:
            j = idx[vl]
            pres = np.minimum(bb[i][1], bb[j][1]) - np.maximum(bb[i][0], bb[j][0])
            if not np.all(pres > 0):
                problemy.append({"kod": "spojka_mimo_spoj", "dily": [i, j],
                                 "text": f"{_jmeno(dily[i], i)} nesedí na profilu {_jmeno(dily[j], j)}"})
    return problemy


# ---------------------------------------------------------------------------------------------------------------------
# dostupnost voleb (pro panel: ktery prepinac lze zapnout a proc ne)
# ---------------------------------------------------------------------------------------------------------------------
def dostupnost(**vstup):
    """Pro kazdy VYPNUTY prepinac zkusi, jestli by zustal zapnuty: kdyz by se hned automaticky odebral (nevejde se / koliduje),
    vrati text duvodu. Vraci {prepinac: None (lze zapnout) | text duvodu}. Zapnute prepinace jdou vzdy vypnout (None)."""
    if _je_sse(vstup):
        return _sse().dostupnost(vstup)
    p = sestav_stul(**vstup)["parametry"]
    out = {}
    for k in PREPINACE + ("vzpery",):
        if p[k]:
            out[k] = None
            continue
        if k == "patky" and p["kolecka"]:
            out[k] = "Stavitelné patky jdou jen u stolu bez koleček."
            continue
        if k == "navlek" and p["system"] not in NAVLEK_SYSTEMY:
            out[k] = "Návlek nohou (jekl 40×40×2) je jen v systému 35."
            continue
        if k in ("kolecka", "patky") and p["navlek"]:
            out[k] = "Návlek nahrazuje kolečka, záslepky i patky – nejdřív ho vypni."
            continue
        r = sestav_stul(**{**p, k: True})
        if r["parametry"][k]:
            out[k] = None
        else:
            hit = [o["text"] for o in r["odebrano"] if o["volba"] == k]
            out[k] = hit[0] if hit else "Nelze zapnout."
    return out


# ---------------------------------------------------------------------------------------------------------------------
# vstup/vystup pro API (bez Flasku - testovatelne bez DB; routa je v api/stul_api.py)
# ---------------------------------------------------------------------------------------------------------------------
_CISLA = ("sirka", "hloubka", "vyska", "presah", "led_rameno", "loz_rozteca", "loz_okraj", "vzpera_delka", "panely_pocet", "suplik_pocet", "stojky_vyska", "navlek_delka", "panely_delka", "led_delka", "led_pocet", "hpolice_hloubka", "hpolice_sklon") + VYREZY_CISLA
_DESETINNA = ("suplik_posun", "stredni_noha", "pet_posun", "panely_posun", "panely_z", "elzlab_y", "elzlab_z", "hpolice_vyska") + tuple(f"police_h{j}" for j in range(1, 11)) + LED_PARAMETRY_Z


def _bool(v):
    s = str(v).strip().lower()
    if s in ("1", "true", "ano", "yes", "on"):
        return True
    if s in ("0", "false", "ne", "no", "off", ""):
        return False
    raise StulChyba(f"neplatna hodnota prepinace: {v!r}", "neplatny_vstup")


def parametry_z_dotazu(args):
    """Query string (mapping) -> parametry pro sestav_stul (jen zadane; zbytek vychozi). Vyhodi StulChyba."""
    out = {}
    for k in args:
        if k in _CISLA or k in _DESETINNA:
            v = args.get(k)
            if (k == "stredni_noha" or k.startswith("police_h") or k == "hpolice_vyska" or k.startswith("led_z")) and str(v).strip().lower() in ("", "null", "none", "stred", "auto"):
                out[k] = None
                continue
            try:
                out[k] = float(v)
            except (TypeError, ValueError):
                raise StulChyba(f"{k}: '{v}' neni cislo", "neplatny_vstup")
        elif k == "police":
            v = str(args.get(k)).strip().lower()
            if v in ("true", "ano", "yes", "on"):
                out[k] = 1
            elif v in ("false", "ne", "no", "off", ""):
                out[k] = 0
            else:
                try:
                    out[k] = float(v)
                except ValueError:
                    raise StulChyba(f"police: '{v}' neni cislo", "neplatny_vstup")
        elif k in PREPINACE or k in VYREZY_PREP or k in ("loz", "vzpery", "suplik_vlevo", "led_svetlo", "police_deska"):
            out[k] = _bool(args.get(k))
        elif k in ("pet_noha", "pet_strana", "stredni_opora", "hpolice_typ", "hpolice_deska"):
            out[k] = str(args.get(k)).strip()
        elif k == "system":
            out[k] = over_system(args.get(k))
        elif k == "_":
            continue            # cache-buster
        else:
            raise StulChyba(f"neznamy parametr: {k}", "neznamy_parametr")
    return out


def odpoved(parametry):
    """Telo odpovedi GET /api/stul/konfigurace: sestava + volby (dostupnost) + prahy pro panel."""
    r = sestav_stul(**parametry)
    r["volby"] = dostupnost(**parametry)
    r["nabidky_roztazeni"] = nabidky_roztazeni(**parametry)
    r["nabidky_police"] = nabidky_police(**parametry)
    r["vzpera_meze"] = vzpera_meze(**r["parametry"]) if r["parametry"]["vzpery"] else None          # presne meze delky vzpery (rameno, stojka, okoli) pro jezdec
    r["rozsah"] = {k: list(v) for k, v in _rozsahy(r["parametry"]["system"]).items()}
    r["system"] = r["parametry"]["system"]
    r["profil_mm"] = SYSTEMY[r["system"]]["profil_mm"]
    r["systemy"] = {str(k): {"profil_mm": v["profil_mm"], "nazev_profilu": v["nazev_profilu"], "vzpery": v["vzpery"], "navlek": k in NAVLEK_SYSTEMY, **({"hluboky": True} if v.get("hluboky") else {})} for k, v in SYSTEMY.items()}
    r["sirka_stredni_noha"] = int(prah_sirky(r["system"]))
    r["min_odstup_stredni_noha"] = min_odstup_stredni_noha(r["system"])
    r["hloubka_bocni_profil"] = int(prah_hloubky(r["system"]))
    if SYSTEMY[r["system"]].get("hluboky"):                                           # jen system 45 (u ostatnich systemu odpoved beze zmeny bit po bitu)
        r["hloubka_stredni_noha"] = int(prah_hloubky_noha(r["system"]))              # nad touto hloubkou stredni rada noh (pravidlo systemu)
    r["ovladani_scena"] = ovladani_3d(r)
    r.pop("klice", None)
    return r


# ---------------------------------------------------------------------------------------------------------------------
# VYROBNI VYPIS (Robert 2026-10-03: generator ma generovat SESTAVY, pri objednani ukladat do DB a obsahovat KOMPLETNI vycet dilu, aby se dalo vyrobit;
# na vyber: desky s vyrezy, spojovaci material, montazni postup). Cista funkce nad vysledkem sestav_stul(); katalogove ceny/SKU doplni stul_shop.
# ---------------------------------------------------------------------------------------------------------------------
ROLE_SABLONY = {
    DESKA_PRAC: ("deska", "pracovní deska"), DESKA_POLICE: ("deska", "spodní police"),
    NOHA_PL: ("noha", "noha přední levá"), NOHA_PP: ("noha", "noha přední pravá"), NOHA_ZL: ("noha", "noha zadní levá"), NOHA_ZP: ("noha", "noha zadní pravá"),
    ZRAIL_PRAC_PRED: ("pricka", "přední příčka rámu desky"), ZRAIL_PRAC_ZAD: ("pricka", "zadní příčka rámu desky"),
    XRAIL_PRAC_L: ("pricka", "levá boční příčka rámu desky"), XRAIL_PRAC_P: ("pricka", "pravá boční příčka rámu desky"),
    XRAIL_POL_L: ("pricka", "levá boční příčka police"), XRAIL_POL_P: ("pricka", "pravá boční příčka police"),
    ZRAIL_POL_PRED: ("pricka", "přední příčka police"), ZRAIL_POL_ZAD: ("pricka", "zadní příčka police"),
    XRAIL_BOX1: ("pricka", "příčka pod deskou držící šuplíky (1)"), XRAIL_BOX2: ("pricka", "příčka pod deskou držící šuplíky (2)"),
    ZRAIL_PANEL: ("pricka", "příčka panelů"), XRAIL_TOP_L: ("pricka", "levé rameno LED"), XRAIL_TOP_P: ("pricka", "pravé rameno LED"), ZRAIL_TOP: ("pricka", "příčka nad LED"),
    BOX: ("prislusenstvi", "šuplíkový box"), LED: ("prislusenstvi", "LED osvětlení"), ELZLAB: ("prislusenstvi", "elektrožlab"),
    PANEL_D: ("prislusenstvi", "perforovaný panel (dolní)"), PANEL_H: ("prislusenstvi", "perforovaný panel (horní)"), PET: ("prislusenstvi", "držák PET lahve"),
}
for _i in KOLECKA:
    ROLE_SABLONY[_i] = ("kolecko", "kolečko")


def role_dilu(klic):
    """(kategorie, citelny popis) dilu podle klice generatoru (r["klice"][i])."""
    if isinstance(klic, tuple) and len(klic) > 1 and klic[0] == "sse":
        return _sse().role(klic)                                             # stul SSE (system 41)
    if isinstance(klic, str):
        return {"FM": ("noha", "střední noha přední"), "RM": ("noha", "střední noha zadní"), "XM_prac": ("pricka", "střední příčka rámu desky"),
                "XM_pol": ("pricka", "střední příčka police"), "XM_top": ("pricka", "střední příčka ramene LED"),
                "kolecko_FM": ("kolecko", "kolečko střední nohy přední"), "kolecko_RM": ("kolecko", "kolečko střední nohy zadní")}.get(klic, ("dil", klic))
    t = klic[0]
    if t == "t":
        return ROLE_SABLONY.get(klic[1], ("dil", f"díl šablony {klic[1]}"))
    if t == "seg":
        kat, pop = ROLE_SABLONY.get(klic[1], ("dil", f"díl šablony {klic[1]}"))
        return kat, pop + " (část dělená střední nohou)"
    if t == "polic":
        kat, pop = role_dilu(klic[2])
        return kat, f"{pop} – police č. {klic[1] + 1}"
    if t == "bok" and klic[2] == "dno":
        return "noha", f"střední noha bočnice ({'levá' if klic[1] == 'L' else 'pravá'} strana, uprostřed hloubky)"
    if t == "bok_kolecko":
        return "kolecko", f"kolečko střední nohy bočnice ({'levá' if klic[1] == 'L' else 'pravá'} strana)"
    if t == "zmid":
        return "pricka", f"střední příčka přes šířku (uprostřed hloubky, úroveň {klic[1] + 1})"
    if t == "bok":
        return "noha", f"svislý profil bočnice ({'levá' if klic[1] == 'L' else 'pravá'} strana, {klic[2] + 1}. patro)"
    if t == "podpera":
        return "pricka", f"podpěra spodní police (mezi čelním a zadním podélníkem) – police č. {klic[1] + 1}"
    if t == "podpera_d":
        return "pricka", "podpěra pod pracovní deskou (mezi čelní a zadní příčkou rámu)"
    if t == "kus":
        return "deska", "pracovní deska – další kus (pravá část u střední opory nebo kus kolem výřezu)"
    if t == "ram":
        return "noha", f"svislý profil vestavěného rámu ({'zadní' if klic[1] == 'pz' else 'přední'}, {klic[2] + 1}. patro)"
    if t == "kusp":
        return "deska", "spodní police – pravá část (za střední opěrou)"
    if t == "hpol":
        return _hpol().role(klic)
    if t == "panrail":
        return "pricka", f"profil pod / nad perforovaným panelem (úroveň {klic[2] + 1})"
    if t == "pan":
        return "prislusenstvi", f"perforovaný panel ({klic[1] + 1}. řada)"
    if t == "polvyr":
        n, druh = klic[1], klic[2]
        return {"deska": ("deska", f"police pod výřezem {n}"), "nos": ("pricka", f"nosný profil police pod výřezem {n}"),
                "zaves": ("noha", f"závěs police pod výřezem {n}")}[druh]
    if t == "konec":
        if len(klic) == 3:                                                   # navlek nohy (jekl) a jeho zaslepka: ("konec", noha, "navlek" | "zasl")
            return "konec", (_NAZVY[NAVLEK_PART] if klic[2] == "navlek" else "záslepka jeklu 40×40")
        return "konec", "záslepka nebo stavitelná patka pod nohou"
    if t == "zasl":
        return "zaslepka", "záslepka volného konce profilu"
    if t == "loz":
        return "jednotka", "ložisková jednotka"
    if t in ("s", "n", "sk"):
        return "spojka", "rohová spojka"
    if t == "vz":
        return ("pricka", "vzpěra ramene LED") if klic[2] == "prof" else ("spojka", "šikmá spojka vzpěry")
    return "dil", str(klic)


def _krok_montaze(kat, popis):
    """Cislo kroku montazniho postupu pro dil (viz MONTAZNI_KROKY)."""
    if "horní police" in popis:
        return 7
    if "vzpěra ramene LED" in popis or "šikmá spojka vzpěry" in popis:
        return 10
    if kat == "konec" or kat == "kolecko" or kat == "zaslepka":
        return 8
    if kat == "jednotka":
        return 9
    if kat == "spojka":
        return 4
    if kat == "prislusenstvi":
        return 7
    if kat == "deska":
        if "police pod výřezem" in popis:
            return 6
        if "spodní police" in popis or "police č." in popis:
            return 3
        return 5
    if "police pod výřezem" in popis:
        return 6
    if kat == "noha" or "boční příčka" in popis or "svislý profil bočnice" in popis:
        return 2
    if "police" in popis and kat == "pricka":
        return 3
    if "šuplíky" in popis or "LED" in popis or "panelů" in popis or "panel" in popis or "rameno" in popis:
        return 7
    return 2 if "střední" in popis else 2


MONTAZNI_KROKY = {
    1: "Nařezat profily podle řezného plánu (řezy kolmé, odjehlit), připravit desky (formát a výřezy podle výkresu) a spojovací materiál. Nasunout hlavy šroubů do T-drážek PŘED sesazením profilů.",
    2: "Sestavit levý a pravý boční rám: nohy, boční příčky rámu desky a police, svislé profily bočnic; střední nohy a střední příčky u širokého stolu (nebo vestavěný rám: dvě příčky v ose X a dva svislé profily "
       "mezi podélníky – podélníky zůstanou celé; desky polic jsou u rámu o mezeru kratší, aby jimi prošel svislý profil rámu).",
    3: "Spojit boční rámy předními a zadními příčkami (rám pracovní desky a rám police); u stolu hlubšího než {prah} mm do rámu každé police a pod pracovní desku vložit podpěrné profily "
       "mezi čelní a zadní podélník (přední konec se dvěma rohovými spojkami, zadní konec na čelo podélníku); vložit spodní police a jejich desky (u hloubky nad {prah} mm jsou o {kr2} mm užší, "
       "{kr} mm z každé strany, aby nezasáhly svislé profily bočnic); u stolu se střední oporou je každá police ze dvou desek (levá a pravá část, dělicí spára v ose střední nohy / rámu); "
       "dotáhnout imbusem přes otvory.",
    4: "Osadit rohové spojky na spoje profilů (kde nekolidují s deskou).",
    5: "Položit pracovní desku na rám (už s výřezy; u stolu se střední oporou obě části desky, dělicí spára v ose střední nohy / rámu) a zkontrolovat doléhání.",
    6: "Police pod výřezem (je-li): přišroubovat závěsy pod přední a zadní příčku rámu, mezi závěsy nosné profily a na ně položit desku police (100 mm pod pracovní deskou).",
    7: "Příslušenství: šuplíkový box s jeho příčkami pod desku, držák PET lahve, perforované panely vsazené mezi zadní stojky (profil pod a nad každým panelem, mezera 1 mm; elektrožlab na panel), "
       "LED s ramenem (jsou-li zvoleny).",
    8: "Konce noh: kolečka, nebo záslepky, nebo stavitelné patky; na všechny volné konce ostatních profilů (konce ramen LED apod.) nasadit záslepky; stůl postavit, vyrovnat a patky nastavit na stejnou výšku.",
    9: "Ložiskové jednotky (jsou-li): vyvrtat otvory podle výkresu desky (polohy od předního a levého okraje) a osadit jednotky; v místě výřezů a dělicí spáry desek se nedávají.",
    10: "Šikmé vzpěry ramen LED (jsou-li): profil vzpěry nařezat kolmo na zadanou délku, na oba konce nasadit šikmé spojky (SKU {vzp_sku}) zrcadlově a přišroubovat: "
        "spodní spojku na přední stranu zadní stojky, horní spojku na spodní stranu ramene LED (45° dělá spojka).",
}
# kroky montaze, ktere se u stolu se spodnimi policemi BEZ DESKY (parametr police_deska = False) lisi: police tvori jen ram z profilu, bez desky a bez podper pod ni (Robert 2026-10-07)
MONTAZNI_KROKY_BEZ_DESEK_POLIC = {
    2: "Sestavit levý a pravý boční rám: nohy, boční příčky rámu desky a police, svislé profily bočnic; střední nohy a střední příčky u širokého stolu (nebo vestavěný rám: dvě příčky v ose X a dva svislé profily "
       "mezi podélníky – podélníky zůstanou celé).",
    3: "Spojit boční rámy předními a zadními příčkami (rám pracovní desky a rám police); u stolu hlubšího než {prah} mm pod pracovní desku vložit podpěrné profily "
       "mezi čelní a zadní podélník (přední konec se dvěma rohovými spojkami, zadní konec na čelo podélníku); spodní police jsou BEZ DESEK – tvoří je jen rám z profilů "
       "(do rámu police se podpěrné profily nevkládají); dotáhnout imbusem přes otvory.",
}


def vyrobni_vypis(r, nazvy_karet=None):
    """Vyrobni vypis v systemu vysledku `r` (r["parametry"]["system"]); viz _vyrobni_vypis_systemu."""
    with _v_systemu((r.get("parametry") or {}).get("system", SYSTEM_VYCHOZI)):
        return _vyrobni_vypis_systemu(r, nazvy_karet)


def _vyrobni_vypis_systemu(r, nazvy_karet=None):
    """Kompletni vycet dilu pro VYROBU z vysledku sestav_stul(): rezny plan profilu, desky s vyrezy a policemi (formaty a polohy), prislusenstvi (vc. polohy
    loziskovych jednotek), rohove spojky, spoje a spojovaci material, montazni postup. Kazdy dil sestavy je v nejakem kroku postupu (`kroky[].dily`).
    Desku rozrezanou na kusy kolem vyrezu popisuje JEDNOU (kusy jsou jen kresleni). Souradnice: mm od PREDNIHO (x) a LEVEHO (z) okraje pracovni desky."""
    from collections import OrderedDict
    dily, klice, p = r["dily"], r["klice"], r["parametry"]
    def _tup(k):
        return tuple(_tup(x) for x in k) if isinstance(k, (list, tuple)) else k
    role = [role_dilu(_tup(k)) for k in klice]
    # ---- rezny plan profilu
    profily = [{"id": i, "role": role[i][1], "delka_mm": round(1000.0 * d["scale"][1], 1)} for i, d in enumerate(dily) if d["part_id"] in PROFIL_PARTS]
    skupiny = OrderedDict()
    for x in sorted(profily, key=lambda q: -q["delka_mm"]):
        skupiny.setdefault(x["delka_mm"], []).append(x["id"])
    rezny_plan = [{"delka_mm": L, "pocet": len(ids), "id_dilu": ids} for L, ids in skupiny.items()]
    # ---- desky (Robert 2026-10-05: formaty tabuli laminodesky): KAZDA deska je jeden kus - pracovni deska, spodni police, police pod vyrezem; u stolu deleneho u stredni opory (noha / ram)
    #      pracovni deska i police dve desky (leva a prava cast, kazda se vejde do tabule); deska rozrezana vyrezem na kusy ve 3D je porad jedna deska. Vyrezy a otvory po deskach.
    skup_d = OrderedDict()                                                 # deska_id -> indexy kusu (poradi podle prvniho kusu)
    for i, d in enumerate(dily):
        if (d["part_id"] == "product_4933" or d["part_id"] in _hpol().DESKA_PARTY) and d.get("deska_id"):
            skup_d.setdefault(d["deska_id"], []).append(i)
    rozdelena = any(k.endswith("_1") for k in skup_d if not k.startswith(("polvyr", "hpol")))
    for i, d in enumerate(dily):                                           # nazvy dilu desek podle desky (klic samotny nerekne, ktera cast to je)
        if d.get("deska_id") and (d["part_id"] == "product_4933" or d["part_id"] in _hpol().DESKA_PARTY):
            role[i] = ("deska", _popis_desky(d["deska_id"], rozdelena) + (" (kus kolem výřezu)" if d.get("deska_kus") else ""))
    idx_desek_praci = [i for did, ids_ in skup_d.items() if did.startswith("prac_") for i in ids_]
    bb = {i: _aabb(dily[i]) for i in idx_desek_praci}
    X0 = min(float(b[0][0]) for b in bb.values()) if bb else 0.0
    Z0 = min(float(b[0][2]) for b in bb.values()) if bb else 0.0
    vyr_cele = [{"n": n, "x0": X0 + p[f"vyrez{n}_x"], "x1": X0 + p[f"vyrez{n}_x"] + p[f"vyrez{n}_d"], "z0": Z0 + p[f"vyrez{n}_z"], "z1": Z0 + p[f"vyrez{n}_z"] + p[f"vyrez{n}_w"]}
                for n in range(1, MAX_VYREZU + 1) if p[f"vyrez{n}"]]
    desky = []
    for did, ids_d in skup_d.items():
        prvni = next((i for i in ids_d if not dily[i].get("deska_kus")), ids_d[0])
        celek = dily[prvni].get("deska_celek")
        sirka_d, hloubka_d = (celek[1], celek[0]) if celek else (1000.0 * dily[prvni]["scale"][1], 1000.0 * dily[prvni]["scale"][0])
        lo_b = np.min([_aabb(dily[j])[0] for j in ids_d], axis=0)
        hi_b = np.max([_aabb(dily[j])[1] for j in ids_d], axis=0)
        vyr_d = []
        if did.startswith("prac_"):
            for v in vyr_cele:
                za, zb = max(v["z0"], float(lo_b[2])), min(v["z1"], float(hi_b[2]))
                if zb - za > 0.05:                                         # vyrez zasahuje do teto desky (u dely se muze vyrez rozdelit mezi obe casti)
                    cely = v["z0"] >= float(lo_b[2]) - 0.05 and v["z1"] <= float(hi_b[2]) + 0.05
                    q = {"n": v["n"], "sirka_mm": round(zb - za, 1), "hloubka_mm": round(v["x1"] - v["x0"], 1), "od_predniho_okraje_mm": round(v["x0"] - float(lo_b[0]), 1),
                         "od_leveho_okraje_mm": round(za - float(lo_b[2]), 1)}
                    if not cely:
                        q["pozn"] = "výřez zasahuje přes dělicí spáru i do druhé části desky (u střední opory)"
                    vyr_d.append(q)
        q = {"role": _popis_desky(did, rozdelena), "ks": 1, "tloustka_mm": _hpol().tloustka_dilu(dily[prvni]["part_id"]), "sirka_mm": round(sirka_d, 1), "hloubka_mm": round(hloubka_d, 1), "vyrezy": vyr_d, "id_dilu": ids_d, "deska_id": did}
        if did.startswith("prac_"):
            q["pocatek_mm"] = [round(float(lo_b[0]) - X0, 1), round(float(lo_b[2]) - Z0, 1)]      # levy predni roh teto desky vuci levemu prednimu rohu CELE pracovni plochy (polohy lozisek jsou vuci cele plose)
        desky.append(q)
    def _poradi_desky(q):                                                  # pracovni deska (leva, prava), police odspodu (leva, prava), police pod vyrezy
        did = q["deska_id"]
        if did.startswith("hpol"):
            return (3, 0, 0)                                               # desky horni police az za policemi pod vyrezy (porad vzniku zustava)
        if did.startswith("prac_"):
            return (0, 0, int(did[-1]))
        if did.startswith("polvyr"):
            return (2, int(did[6:] or 0), 0)
        return (1, int(did[3:].split("_")[0]), int(did[-1]))
    desky.sort(key=_poradi_desky)
    # ---- prislusenstvi (po kartach) a loziskove jednotky s polohami
    prisl = OrderedDict()
    for i, d in enumerate(dily):
        kat = role[i][0]
        if d["part_id"] in PROFIL_PARTS + ("product_4933",) + _hpol().DESKA_PARTY + SPOJKY_PARTS + (LOZ_PART,) + NAVLEK_PARTS + SSE_PARTS:
            continue                                                       # navlek a jeho zaslepka a dily nohou SSE nejsou karty katalogu: viz `navlek` / `nohy_sse` nize
        q = prisl.setdefault(d["part_id"], {"karta_id": int(d["part_id"].split("_")[1]), "nazev": _NAZVY.get(d["part_id"], d["part_id"]), "pocet": 0, "id_dilu": []})
        q["pocet"] += 1
        q["id_dilu"].append(i)
    prislusenstvi = list(prisl.values())
    jednotky = [i for i, d in enumerate(dily) if d["part_id"] == LOZ_PART]
    if jednotky:
        info = r.get("loz") or {}
        prislusenstvi.append({"karta_id": 3025, "nazev": _NAZVY[LOZ_PART], "pocet": len(jednotky), "id_dilu": jednotky, "rozteca_mm": p["loz_rozteca"], "od_okraje_mm": p["loz_okraj"],
                              "radku": info.get("radku"), "sloupcu": info.get("sloupcu"), "vynechano": info.get("vynechano"),
                              "polohy_stredu_mm": [[round(dily[i]["position"][0] - X0, 1), round(dily[i]["position"][2] - Z0, 1)] for i in jednotky]})
    spojky = [i for i, d in enumerate(dily) if d["part_id"] in SPOJKY_PARTS]
    # ---- navlek nohou (jekl 40x40x2 + zaslepka): rezny plan jeklu
    navlek = None
    jekly = [i for i, d in enumerate(dily) if d["part_id"] == NAVLEK_PART]
    if jekly:
        delky = sorted({round(1000.0 * dily[i]["scale"][1], 1) for i in jekly})
        navlek = {"nazev": f"návlek nohy – jekl 40×40×2 (stěna 2 mm), {NAVLEK_BARVA} lesk, se záslepkou jeklu 40×40", "pocet": len(jekly), "id_dilu": jekly, "barva": NAVLEK_BARVA, "povrch": NAVLEK_POVRCH,
                  "zaslepky_jeklu": len([i for i, d in enumerate(dily) if d["part_id"] == NAVLEK_ZASLEPKA]), "srazeni_mm": NAVLEK_SRAZENI,
                  "rezny_plan": [{"delka_mm": L, "pocet": sum(1 for i in jekly if round(1000.0 * dily[i]["scale"][1], 1) == L)} for L in delky],
                  "zasun_nohy_min_mm": NAVLEK_ZASUN, "vnitrni_rozmer_mm": NAVLEK_JEKL - 2 * NAVLEK_STENA,
                  "pozn": f"na spodek každé nohy se nasadí jekl 40×40, stěna 2 mm, vnější rohy sražené {NAVLEK_SRAZENI:g} mm, povrch {NAVLEK_POVRCH}, dole se záslepkou; noha (profil) v něm zajíždí aspoň {NAVLEK_ZASUN:.0f} mm; výšku stolu lze zasunutím nohy mechanicky měnit"}
    # ---- spoje a spojovaci material (PRAVIDLA_SPOJU.md: 1 spoj = 1 sroub do zavitu v cele jednoho profilu + otvor v druhem; typ sroubu/T-matic neni v katalogu definovan)
    spojovaci = {"spoje_profil_profil": len(r["spoje"]), "pocet_rohovych_spojek": len(spojky),
                 "popis_spoje": "1 spoj = 1 šroub do závitu v čele jednoho profilu + otvor v druhém profilu, hlava šroubu předem nasunutá v T-drážce (PRAVIDLA_SPOJU.md)",
                 "typ_sroubu_a_matic": None, "poznamka": "šrouby a matice ke spojům profil–profil zatím nejsou určeny – doplní Robert",
                 "ke_spojkam": spojovaci_material(dily, nazvy_karet),
                 "ke_spojkam_poznamka": (
                     "na každou rohovou spojku 2 ks 2.1.21.0612 + 2 ks 2.1.001.08.06; na každý úhel 45° 2 ks zápustný šroub M6×14 (délka včetně hlavy, SKU zatím neurčeno) "
                     "+ 2 ks 2.1.001.08.06 – Robert 2026-10-04; názvy jsou názvy karet z katalogu" if p["system"] != 40 else
                     "na každou rohovou spojku 40×40 2 ks 2.1.21.0616 (NÁVRH: M6×16, délku šroubu ověřit u karty spojky) + 2 ks 2.1.001.10.06 (otočná matice, drážka 10); na každý úhel 45° (3220) 2 ks zápustný šroub M6 "
                     "(délku a SKU určí Robert) + 2 ks 2.1.001.10.06; názvy jsou názvy karet z katalogu")}
    # ---- montazni postup: kazdy dil prave v jednom kroku
    sse_stul = bool(_sd().get("sse"))
    kroky = {n: {"krok": n, "text": t.replace("{prah}", str(int(prah_hloubky()))).replace("{kr2}", str(int(2 * bok_kraceni_desky()))).replace("{kr}", str(int(bok_kraceni_desky()))).replace("{vzp_sku}", _sd()["vzpera_sku"]), "dily": []}
             for n, t in (_sse().MONTAZNI_KROKY if sse_stul else ({**MONTAZNI_KROKY, **MONTAZNI_KROKY_BEZ_DESEK_POLIC} if (p["police"] and not p.get("police_deska", True)) else MONTAZNI_KROKY)).items()}
    for i in range(len(dily)):
        kroky[_sse().krok_montaze(_tup(klice[i])) if sse_stul else _krok_montaze(*role[i])]["dily"].append(i)
    hpi_ = r.get("hpolice_info")
    if hpi_ and not hpi_.get("problem"):                                # horni police: veta v kroku 7 JEN u zapnute police (vychozi vypis zustava bitove stejny)
        kroky[7]["text"] += (" Horní police mezi zadními stojkami: rám z profilů mezi stojkami (zadní a přední příčka, boční a střední profily), deska shora na rámu nebo v drážce profilů; "
                             "rám s přepážkami má podlahu v drážce a svislé přepážky z překližky na úhelnících, police s lemem pás z překližky na úhelnících.")
    kroky[1]["dily"] = [x["id"] for x in profily] + [i for q in desky for i in q["id_dilu"]]
    if navlek:
        kroky[8]["text"] += (f" S návlekem (systém 35): na spodek každé nohy nasadit jekl 40×40×2 se záslepkou dole (noha v něm aspoň {NAVLEK_ZASUN:.0f} mm), výšku stolu lze zasunutím nohy do jeklu "
                             "mechanicky měnit (způsob zajištění určí výroba).")
    postup = [kroky[n] for n in sorted(kroky) if kroky[n]["dily"] or n == 1]
    return {"profily": profily, "rezny_plan": rezny_plan, "desky": desky, "prislusenstvi": prislusenstvi, **({"navlek": navlek} if navlek else {}), **({"nohy_sse": _sse().vypis_noh(r)} if sse_stul else {}),
            "rohove_spojky": {"pocet": len(spojky), "id_dilu": spojky},
            "spoje": [list(x) for x in r["spoje"]], "spojovaci_material": spojovaci, "montazni_postup": postup,
            "montazni_postup_stav": "návrh sestavený z konstrukce stolu – ke kontrole výrobou", "role_dilu": [list(x) for x in role],
            "pocatek_souradnic": "mm od předního (x) a levého (z) okraje pracovní desky",
            "system": p["system"], "profil_nazev": _sd()["nazev_profilu"], "spojka_karta": int(_sd()["spojka"].split("_")[1])}


# ---------------------------------------------------------------------------------------------------------------------
# OVLADANI PRIMO VE 3D (Robert 2026-10-03: pridavne ovladaci prvky v 3D pohledu - drag and drop, nabidka pravym tlacitkem, vizualni propojeni s panelem;
# u tazeni musi byt videt o kolik mm). Popis ovladacich prvku pro prohlizec - viz docs/OVLADANI_3D.md. Souradnice generatoru (stul_glb.vodici je prevede do GLB).
# ---------------------------------------------------------------------------------------------------------------------
def _patro_ramu_police(klic):
    """Patro (0 = nejnizsi) ramu spodni police podle klice jeho BOCNI PRICKY police ((t, XRAIL_POL_L / P) = patro 0, (polic, k, ...) = patro k), jinak None. Slouzi police BEZ DESKY
    (Robert 2026-10-07; parametr police_deska): patro nema desku, takze ho ve 3D ovladani a v kotach zastupuje jeho ram (obe bocni pricky police)."""
    if not isinstance(klic, tuple):
        return None
    if klic in (("t", XRAIL_POL_L), ("t", XRAIL_POL_P)):
        return 0
    if len(klic) == 3 and klic[0] == "polic" and tuple(klic[2]) in (("t", XRAIL_POL_L), ("t", XRAIL_POL_P)):
        return int(klic[1])
    return None


def ovladani_3d(r):
    """Popis ovladani ve 3D v systemu vysledku `r` (r["parametry"]["system"]); viz _ovladani_3d_systemu."""
    with _v_systemu((r.get("parametry") or {}).get("system", SYSTEM_VYCHOZI)):
        if SYSTEMY[_SYSTEM.get()].get("sse"):
            return _sse().ovladani(r)
        return _ovladani_3d_systemu(r)


def _ovladani_3d_systemu(r):
    """Popis ovladani ve 3D z vysledku sestav_stul()/odpoved(): `casti` (co lze najet/kliknout pravym tlacitkem: AABB, parametry pro propojeni s panelem, nabidka)
    a `tahy` (uchopovaci body pro drag and drop: osa / rovina, parametr, faktor, meze, mereni v mm)."""
    dily, klice, p = r["dily"], r["klice"], r["parametry"]

    def _tup(k):
        return tuple(_tup(x) for x in k) if isinstance(k, (list, tuple)) else k
    klice_t = [_tup(k) for k in klice]
    role = [role_dilu(k) for k in klice_t]
    bb = [_aabb(d) for d in dily]

    def idx(pred):
        return [i for i in range(len(dily)) if pred(klice_t[i], role[i], dily[i])]

    def aabb(ids, pad=0.0, minrozmer=0.0):
        lo = np.min([bb[i][0] for i in ids], axis=0).astype(float)
        hi = np.max([bb[i][1] for i in ids], axis=0).astype(float)
        stred, pul = (lo + hi) / 2.0, np.maximum((hi - lo) / 2.0 + pad, minrozmer / 2.0)
        return [[round(float(v), 1) for v in stred - pul], [round(float(v), 1) for v in stred + pul]]

    def pol(text, nastav=None, duvod=None, **extra):
        out = {"text": text, "nastav": nastav, "zakazano": duvod is not None, "duvod": duvod}
        out.update(extra)
        return out

    casti, tahy = [], []
    # ---- deska
    d_ids = idx(lambda k, rl, d: k == ("t", DESKA_PRAC) or k[0] == "kus")
    if not d_ids:
        return {"casti": [], "tahy": []}
    dlo, dhi = aabb(d_ids)
    X0, y_hore, Z0 = dlo[0], dhi[1], dlo[2]
    X1, Z1 = dhi[0], dhi[2]
    D, W = X1 - X0, Z1 - Z0
    n_vol = next((n for n in range(1, MAX_VYREZU + 1) if not p[f"vyrez{n}"]), None)
    menu = []
    if n_vol:
        menu.append(pol("Přidat výřez sem", {f"vyrez{n_vol}": True}, bod_na_desce={"x": f"vyrez{n_vol}_x", "z": f"vyrez{n_vol}_z", "stred_o": [f"vyrez{n_vol}_d", f"vyrez{n_vol}_w"]}))
    else:
        menu.append(pol("Přidat výřez sem", None, f"Už je {MAX_VYREZU} výřezy (nejvíc)."))
    menu.append(pol("Ložiskové jednotky: " + ("vypnout" if p["loz"] else "zapnout"), {"loz": not p["loz"]}))
    if p["loz"]:
        menu.append(pol("Jednotky hustěji (rozteč −10 mm)", {"loz_rozteca": max(ROZSAH["loz_rozteca"][0], p["loz_rozteca"] - 10.0)}))
        menu.append(pol("Jednotky řidčeji (rozteč +10 mm)", {"loz_rozteca": min(ROZSAH["loz_rozteca"][1], p["loz_rozteca"] + 10.0)}))
    menu.append(pol("Rozměry desky nastavit v panelu", None, fokus="sirka"))
    casti.append({"id": "deska", "label": "Pracovní deska", "param": ["sirka", "hloubka", "presah", "loz"], "aabb": [dlo, dhi], "priorita": 1, "menu": menu})
    # ---- vyrezy a police pod nimi
    for v in r["vyrezy"]:
        n = v["n"]
        vl = [round(v["x0"], 1), round(y_hore - 18.0, 1), round(v["z0"], 1)]
        vh = [round(v["x1"], 1), round(y_hore, 1), round(v["z1"], 1)]
        zap = p[f"vyrez{n}_police"]
        casti.append({"id": f"vyrez{n}", "label": f"Výřez {n}", "param": [f"vyrez{n}", f"vyrez{n}_w", f"vyrez{n}_d", f"vyrez{n}_x", f"vyrez{n}_z", f"vyrez{n}_police"], "aabb": [vl, vh],
                      "priorita": 3, "menu": [pol(f"Police pod výřezem {n}: " + ("odebrat" if zap else "přidat"), {f"vyrez{n}_police": not zap}),
                                              pol(f"Odebrat výřez {n}", {f"vyrez{n}": False, f"vyrez{n}_police": False})]})
        pid = idx(lambda k, rl, d, n=n: k[0] == "polvyr" and k[1] == n)
        if pid:
            casti.append({"id": f"vyrez{n}_police", "label": f"Police pod výřezem {n}", "param": [f"vyrez{n}_police", f"vyrez{n}"], "aabb": aabb(pid, pad=4.0), "priorita": 2,
                          "menu": [pol(f"Odebrat polici pod výřezem {n}", {f"vyrez{n}_police": False}), pol(f"Odebrat výřez {n} i s policí", {f"vyrez{n}": False, f"vyrez{n}_police": False})]})
        # tahy: presun (rovina) a zmena velikosti (roh)
        stred = [round((v["x0"] + v["x1"]) / 2.0, 1), round(y_hore, 1), round((v["z0"] + v["z1"]) / 2.0, 1)]
        w_, d_, x_, z_ = p[f"vyrez{n}_w"], p[f"vyrez{n}_d"], p[f"vyrez{n}_x"], p[f"vyrez{n}_z"]
        tahy.append({"id": f"vyrez{n}_presun", "label": f"Výřez {n}: posun", "typ": "rovina", "ikona": "presun", "bod": stred, "casti": [f"vyrez{n}"],
                     "param_x": f"vyrez{n}_x", "faktor_x": 1.0, "hodnota_x": x_, "min_x": VYREZ_OKRAJ, "max_x": round(D - VYREZ_OKRAJ - d_, 1),
                     "param_z": f"vyrez{n}_z", "faktor_z": 1.0, "hodnota_z": z_, "min_z": VYREZ_OKRAJ, "max_z": round(W - VYREZ_OKRAJ - w_, 1), "krok": 10.0,
                     "mereni": [{"label": "od předního okraje", "param": f"vyrez{n}_x"}, {"label": "od levého okraje", "param": f"vyrez{n}_z"}]})
        tahy.append({"id": f"vyrez{n}_velikost", "label": f"Výřez {n}: velikost", "typ": "rovina", "ikona": "roh", "bod": [vh[0], round(y_hore, 1), vh[2]], "casti": [f"vyrez{n}"],
                     "param_x": f"vyrez{n}_d", "faktor_x": 1.0, "hodnota_x": d_, "min_x": VYREZ_MIN, "max_x": round(D - VYREZ_OKRAJ - x_, 1),
                     "param_z": f"vyrez{n}_w", "faktor_z": 1.0, "hodnota_z": w_, "min_z": VYREZ_MIN, "max_z": round(W - VYREZ_OKRAJ - z_, 1), "krok": 10.0,
                     "mereni": [{"label": "šířka výřezu", "param": f"vyrez{n}_w"}, {"label": "hloubka výřezu", "param": f"vyrez{n}_d"}]})
    # ---- spodni police (kazda deska police zvlast)
    #      Police stolu deleneho u stredni opory tvori dve desky (leva a prava cast, viz _deli_desku_u_opory): pro 3D vyber a tazeni vysky je to JEDNA cast (obalka obou).
    police_ids = idx(lambda k, rl, d: d["part_id"] == "product_4933" and str(d.get("deska_id") or "").startswith("pol") and not str(d.get("deska_id")).startswith("polvyr"))
    patra_p = {}
    for i in police_ids:
        patra_p.setdefault(int(dily[i]["deska_id"][3:].split("_")[0]), []).append(i)
    if not p.get("police_deska", True) and p["police"] >= 1:                # police BEZ DESKY (Robert 2026-10-07): patro = jeho ramove profily (obe bocni pricky police), deska uz neni
        patra_p = {}
        for i in idx(lambda k, rl, d: _patro_ramu_police(k) is not None):
            patra_p.setdefault(_patro_ramu_police(klice_t[i]), []).append(i)
    police_skup = [patra_p[k_] for k_ in sorted(patra_p)]                   # police od nejnizsi: seznam indexu dilu (1 nebo 2 desky; bez desky 2 bocni pricky ramu) na patro
    for j, ids_p in enumerate(police_skup):
        mx = r["max_polic"]
        menu = [pol("Přidat spodní polici", {"police": p["police"] + 1}, None if p["police"] < mx else "Další police se nevejde (nízký stůl nebo šuplíky)."),
                pol("Odebrat spodní polici", {"police": p["police"] - 1}, None if p["police"] > 0 else "Žádná police není.")]
        menu.append(pol(("Odebrat desku police" if p["police"] == 1 else "Odebrat desky všech polic") if p.get("police_deska", True)
                        else ("Vrátit desku police" if p["police"] == 1 else "Vrátit desky všech polic"), {"police_deska": not p.get("police_deska", True)}))          # Robert 2026-10-07: police bez desky (jen ram z profilu), plati pro vsechny spodni police
        casti.append({"id": f"police_{j + 1}", "label": "Spodní police" if len(police_skup) == 1 else f"Spodní police {j + 1}", "param": ["police", "police_deska"], "aabb": aabb(ids_p), "priorita": 2, "menu": menu})
    # ---- VYSKA POLIC (Robert 2026-10-04): tah svisle na kazde desce police; cisluje se SHORA (police 1 = nejvyssi): param police_h1 = odstup horni plochy desky pod spodni hranou podelniku
    #      pracovni plochy, police_hK (K >= 2) = mezera nad policí K; tazeni DOLU zvetsuje hodnotu (osa miri dolu). Meze z r["police_meze"] (ostatni police zustanou jak jsou).
    pm_ = r.get("police_meze") or {}
    if pm_.get("n"):
        radit = sorted(((float(max(bb[i][1][1] for i in ids_p)), j + 1, j) for j, ids_p in enumerate(police_skup)), reverse=True)           # (horni plocha, cislo casti police_j, poradi patra), shora dolu
        for rank, (ytop, cast_no, j_p) in enumerate(radit, start=1):
            if rank > pm_["n"]:
                break
            lo_, hi_ = np.min([bb[i][0] for i in police_skup[j_p]], axis=0), np.max([bb[i][1] for i in police_skup[j_p]], axis=0)
            tahy.append({"id": f"police_h{rank}", "label": f"Výška police {rank}", "typ": "osa", "ikona": "sipka_y",
                         "bod": [round(float(lo_[0]), 1), round(float(hi_[1]), 1), round(float((lo_[2] + hi_[2]) / 2), 1)], "osa": [0.0, -1.0, 0.0], "param": f"police_h{rank}", "faktor": 1.0,
                         "hodnota": pm_["hodnoty"][rank - 1], "min": pm_["min"][rank - 1], "max": pm_["max"][rank - 1], "krok": 10.0, "casti": [f"police_{cast_no}"],
                         "mereni": [{"label": "odstup pod deskou" if rank == 1 else "mezera nad policí", "param": f"police_h{rank}"}]})
    # ---- podpery spodni police (hloubka > 900): po jedne casti na uroven police
    urovne_podper = sorted({k[1] for k in klice_t if isinstance(k, tuple) and len(k) == 3 and k[0] == "podpera"})
    for kp in urovne_podper:
        ids = idx(lambda k, rl, d, kp=kp: isinstance(k, tuple) and len(k) == 3 and k[0] == "podpera" and k[1] == kp)
        casti.append({"id": f"podpery_{kp + 1}", "label": "Podpěry spodní police" if len(urovne_podper) == 1 else f"Podpěry spodní police {kp + 1}", "param": ["police", "hloubka", "sirka"],
                      "aabb": aabb(ids, pad=3.0), "priorita": 3,
                      "menu": [pol("Počet podpěr určuje šířka stolu a střední noha", None, fokus="sirka"),
                               pol("Podpěry jsou při větší hloubce stolu vždy; zmenšením hloubky zmizí", None, fokus="hloubka")]})
    ids_d = idx(lambda k, rl, d: isinstance(k, tuple) and len(k) == 2 and k[0] == "podpera_d")
    if ids_d:
        casti.append({"id": "podpery_deska", "label": "Podpěry pod pracovní deskou", "param": ["hloubka", "sirka", "suplik"], "aabb": aabb(ids_d, pad=3.0), "priorita": 3,
                      "menu": [pol("Počet podpěr určuje šířka stolu, střední noha a šuplíky (jejich příčky desku podpírají)", None, fokus="sirka"),
                               pol("Podpěry jsou při větší hloubce stolu vždy; zmenšením hloubky zmizí", None, fokus="hloubka")]})
    # ---- prislusenstvi
    def skupina(cid, label, pred, param, menu, priorita=2):
        ids = idx(pred)
        if ids:
            casti.append({"id": cid, "label": label, "param": param, "aabb": aabb(ids, pad=3.0), "priorita": priorita, "menu": menu})
        return ids
    suplik_ids = skupina("suplik", "Šuplíky", lambda k, rl, d: d["part_id"] in SUPLIK_PARTY_VSE or (k[0] == "t" and k[1] in (XRAIL_BOX1, XRAIL_BOX2)), ["suplik", "suplik_pocet", "suplik_posun", "suplik_vlevo"],
                         [pol("Odebrat šuplíky", {"suplik": False})]
                         + [pol(f"Box s {c} {'šuplíkem' if c == 1 else 'šuplíky'}", {"suplik_pocet": c}) for c in SUPLIK_POCTY if c != int(p["suplik_pocet"])]
                         + [pol("Šuplíky vrátit na výchozí místo", {"suplik_posun": 0.0}, None if p["suplik_posun"] else "Už jsou na výchozím místě."),
                          pol("Přehodit šuplíky na pravou stranu" if p["suplik_vlevo"] else "Přehodit šuplíky na levou stranu", {"suplik_vlevo": not p["suplik_vlevo"]})])
    hp_ = r.get("hpolice_info")
    if hp_ and not hp_.get("problem"):
        skupina("hpolice", "Police mezi stojkami", lambda k, rl, d: k[0] == "hpol", ["hpolice", "hpolice_typ", "hpolice_deska", "hpolice_vyska", "hpolice_hloubka"], _hpol().menu(r, pol))
    pi_ = r.get("panely_info") or {}
    n_pan = int(p["panely_pocet"])
    menu_pan = [pol("Přidat panel", {"panely_pocet": n_pan + 1}, None if n_pan < int(pi_.get("max") or 0) else "Další panel se sem nevejde (širší stůl, vyšší stojky nebo vestavěný rám).")]
    menu_pan.append(pol("Odebrat panel" if n_pan > 1 else "Odebrat panel (i elektrožlab)", {"panely_pocet": n_pan - 1} if n_pan > 1 else {"panely": False, "elektrozlab": False}))
    if n_pan > 1:
        menu_pan.append(pol("Odebrat všechny panely (i elektrožlab)", {"panely": False, "elektrozlab": False}))
    menu_pan.append(pol("Panely vrátit do spodní polohy", {"panely_posun": 0.0}, None if p["panely_posun"] else "Už jsou dole."))
    menu_pan.append(pol("Panely vrátit doprostřed mezi nohy", {"panely_z": 0.0}, None if p["panely_z"] else "Už jsou uprostřed."))
    for t_ in (pi_.get("typy") or []):                                                      # delka panelu (Robert 2026-10-07): ostatni delky jako volby v menu; ktera se nevejde, je zakazana s duvodem
        if p["panely"] and p["stojky"] and t_["delka"] != int(p["panely_delka"]):
            menu_pan.append(pol(f"Zvolit panel {t_['delka']} mm", {"panely_delka": float(t_["delka"])}, None if t_["vejde"] else "Tahle délka panelu se sem nevejde (širší stůl, vyšší stojky nebo vestavěný rám)."))
    pan_ids = skupina("panely", "Perforované panely", lambda k, rl, d: d["part_id"] in PANEL_PARTY or (isinstance(k, tuple) and k[0] == "panrail"),
                      ["panely", "panely_pocet", "panely_posun", "panely_z", "panely_delka", "elektrozlab", "stojky", "stredni_opora"], menu_pan)
    menu_led_delky = []
    for t_ in ((r.get("led_info") or {}).get("typy") or []):                                  # delka svitidla LED (Robert 2026-10-07): ostatni delky jako volby v menu; ktera se nevejde, je zakazana s duvodem
        if p["led"] and p["stojky"] and p["led_svetlo"] and t_["delka"] != int(p["led_delka"]):
            menu_led_delky.append(pol(f"Zvolit LED {t_['delka']} mm", {"led_delka": float(t_["delka"])}, None if t_["vejde"] else "Tahle délka LED se sem nevejde (širší stůl)."))
    li_led = r.get("led_info") or {}
    if p["led"] and p["stojky"] and p["led_svetlo"] and li_led.get("polohy"):
        pr_led = li_led.get("pridat")                                                              # Robert 2026-10-08: svitidla se pridavaji RUCNE (vychozi 1) a posouvaji se podel profilu
        menu_led_delky.append(pol("Přidat svítidlo LED", pr_led, None if pr_led else "Další svítidlo LED se sem nevejde (jejich délky dohromady by přesáhly šířku stolu)."))
    led_ids = skupina("led", "LED osvětlení", lambda k, rl, d: d["part_id"] in LED_PARTY or k in (("t", XRAIL_TOP_L), ("t", XRAIL_TOP_P), ("t", ZRAIL_TOP)), ["led", "led_delka", "led_rameno", "vzpery", "led_svetlo"],
                      [pol("Odebrat LED osvětlení", {"led": False}),
                       pol("Vrátit svítidlo LED" if not p["led_svetlo"] else "Odebrat jen svítidlo LED (profily zůstanou)", {"led_svetlo": not p["led_svetlo"]})]
                      + menu_led_delky
                      + ([pol("Přidat vzpěry ramen LED", {"vzpery": True})] if not p["vzpery"] and p["stojky"] and _sd()["vzpery"] else []))
    if led_ids and li_led.get("polohy") and p["led"] and p["stojky"] and p["led_svetlo"]:                 # kazde svitidlo zvlast: nabidka (odebrat / vratit na vychozi misto) a tah podel profilu (osa Z)
        n_led_ = len(li_led["polohy"])
        pol_led = [float(x) for x in li_led["polohy"]]
        tel_led = float(li_led.get("telo") or LED_SIRKA)
        pul_led = (float(li_led["okraj"][1]) - float(li_led["okraj"][0])) / 2.0                     # polovina vnejsi sirky stolu (profil nad LED)
        for k_led in range(n_led_):
            klic_led = ("t", LED) if k_led == 0 else ("led", k_led)
            ids_led = idx(lambda kk, rl, d, kl=klic_led: kk == kl)
            if not ids_led:
                continue
            popis_led = f"Svítidlo LED {k_led + 1}" if n_led_ > 1 else "Svítidlo LED"
            odeb_led = (li_led.get("odebrat") or [None] * n_led_)[k_led] if n_led_ > 1 else {"led_svetlo": False}
            je_auto_led = abs(pol_led[k_led] - float((li_led.get("auto") or pol_led)[k_led])) < 0.05
            skupina(f"led_{k_led + 1}", popis_led, lambda kk, rl, d, kl=klic_led: kk == kl, ["led_pocet", f"led_z{k_led + 1}"],
                    [pol("Odebrat toto svítidlo", odeb_led), pol("Vrátit svítidlo na výchozí místo", {f"led_z{k_led + 1}": None}, "Už je na výchozím místě." if je_auto_led else None)], priorita=3)
            lo_led, hi_led = li_led["meze"][k_led]
            if float(hi_led) - float(lo_led) >= 0.5:
                alo_led, ahi_led = aabb(ids_led)
                mer_led = [{"label": "od levého okraje stolu", "param": f"led_z{k_led + 1}", "mul": 1.0, "add": round(pul_led - tel_led / 2.0, 1)},
                           {"label": "od pravého okraje stolu", "param": f"led_z{k_led + 1}", "mul": -1.0, "add": round(pul_led - tel_led / 2.0, 1)}]
                if k_led > 0:
                    mer_led.append({"label": "od levého svítidla", "param": f"led_z{k_led + 1}", "mul": 1.0, "add": round(-(pol_led[k_led - 1] + tel_led), 1)})
                if k_led < n_led_ - 1:
                    mer_led.append({"label": "od pravého svítidla", "param": f"led_z{k_led + 1}", "mul": -1.0, "add": round(pol_led[k_led + 1] - tel_led, 1)})
                tahy.append({"id": f"led_z{k_led + 1}", "label": f"Posun svítidla LED {k_led + 1}" if n_led_ > 1 else "Posun svítidla LED", "typ": "osa", "ikona": "sipka_z",
                             "bod": [round((alo_led[0] + ahi_led[0]) / 2, 1), round(alo_led[1], 1), round((alo_led[2] + ahi_led[2]) / 2, 1)], "osa": [0.0, 0.0, 1.0], "param": f"led_z{k_led + 1}",
                             "faktor": 1.0, "hodnota": round(pol_led[k_led], 1), "min": float(lo_led), "max": float(hi_led), "krok": 1.0, "casti": [f"led_{k_led + 1}"], "mereni": mer_led})
    if p["vzpery"]:
        dl_v = p["vzpera_delka"]
        vm = r.get("vzpera_meze") or {}
        v_min, v_max = vm.get("min", ROZSAH["vzpera_delka"][0]), vm.get("max", ROZSAH["vzpera_delka"][1])        # skutecne meze: rameno LED, vyska stojky, okoli
        skupina("vzpery", "Vzpěry ramen LED", lambda k, rl, d: _je_vz(k), ["vzpery", "vzpera_delka"],
                [pol("Odebrat vzpěry ramen LED", {"vzpery": False}),
                 pol("Vzpěry delší (+50 mm)", {"vzpera_delka": min(v_max, dl_v + 50.0)}, None if dl_v < v_max else "Delší vzpěra se sem nevejde."),
                 pol("Vzpěry kratší (−50 mm)", {"vzpera_delka": max(v_min, dl_v - 50.0)}, None if dl_v > v_min else "Kratší vzpěra už není možná.")],
                priorita=3)
    zlab_ids = skupina("elektrozlab", "Elektrožlab", lambda k, rl, d: d["part_id"] == "product_4932", ["elektrozlab", "elzlab_y", "elzlab_z"],
                       [pol("Odebrat elektrožlab", {"elektrozlab": False}),
                        pol("Elektrožlab vrátit na výchozí místo", {"elzlab_y": 0.0, "elzlab_z": 0.0}, None if (p["elzlab_y"] or p["elzlab_z"]) else "Už je na výchozím místě.")], priorita=3)
    pet_ids = skupina("pet", "Držák PET lahve", lambda k, rl, d: d["part_id"] == "product_4928", ["drzak_pet", "pet_posun", "pet_noha", "pet_strana"],
                      [pol("Odebrat držák PET lahve", {"drzak_pet": False}), pol("Držák PET lahve vrátit na výchozí výšku", {"pet_posun": 0.0}, None if p["pet_posun"] else "Už je ve výchozí výšce.")], priorita=3)
    # ---- nohy a jejich konce
    def menu_konce():
        navlek_ok = p["system"] in NAVLEK_SYSTEMY
        if navlek_ok and p["navlek"]:                                                   # navlek (jekl) misto koleček / záslepek / patek: delku meni polozky nabidky po 50 mm
            nm_ = r.get("navlek_meze") or {}
            dl_n, n_lo, n_hi = float(p["navlek_delka"]), float(nm_.get("min", ROZSAH["navlek_delka"][0])), float(nm_.get("max", ROZSAH["navlek_delka"][1]))
            return [pol("Místo návleku záslepky", {"navlek": False, "kolecka": False, "patky": False}), pol("Místo návleku kolečka", {"navlek": False, "kolecka": True}),
                    pol("Návlek delší (+50 mm)", {"navlek_delka": min(n_hi, dl_n + 50.0)}, None if dl_n < n_hi else "Delší návlek se sem nevejde."),
                    pol("Návlek kratší (−50 mm)", {"navlek_delka": max(n_lo, dl_n - 50.0)}, None if dl_n > n_lo else "Kratší návlek už není možný.")]
        if p["kolecka"]:
            return [pol("Místo koleček záslepky", {"kolecka": False, "patky": False}), pol("Místo koleček stavitelné patky", {"kolecka": False, "patky": True})] \
                + ([pol("Místo koleček návlek (jekl 40×40×2)", {"navlek": True})] if navlek_ok else [])
        if p["patky"]:
            return [pol("Místo patek záslepky", {"patky": False}), pol("Místo patek kolečka", {"patky": False, "kolecka": True})] \
                + ([pol("Místo patek návlek (jekl 40×40×2)", {"navlek": True, "patky": False})] if navlek_ok else [])
        return [pol("Kolečka", {"kolecka": True}), pol("Stavitelné patky místo záslepek", {"patky": True})] + ([pol("Místo záslepek návlek (jekl 40×40×2)", {"navlek": True})] if navlek_ok else [])
    zadni_menu = [pol("Zadní stojky: vypnout (i panely, LED, elektrožlab)", {"stojky": False, "panely": False, "led": False, "elektrozlab": False}) if p["stojky"]
                  else pol("Zadní stojky: zapnout", {"stojky": True})]
    stredni_ids = []
    for i, d in enumerate(dily):
        if klice_t[i] not in (("t", NOHA_PL), ("t", NOHA_PP), ("t", NOHA_ZL), ("t", NOHA_ZP), "FM", "RM"):
            continue
        zadni = klice_t[i] in (("t", NOHA_ZL), ("t", NOHA_ZP), "RM")
        stredni = klice_t[i] in ("FM", "RM")
        menu = menu_konce() + (zadni_menu if zadni else [])
        param = ["kolecka", "patky"] + (["navlek", "navlek_delka"] if p["system"] in NAVLEK_SYSTEMY else []) + (["stojky", "stojky_vyska"] if zadni else []) + (["stredni_noha", "stredni_opora"] if stredni else [])
        if stredni:
            menu.append(pol("Střední nohu vrátit doprostřed", {"stredni_noha": None}, None if p["stredni_noha"] is not None else "Už je uprostřed."))
            menu.append(pol("Střední nohy nahradit vestavěným rámem", {"stredni_opora": "ram"}, None if p["police"] >= 1 else "Vestavěný rám potřebuje spodní polici."))
        casti.append({"id": f"noha_{i}", "label": role[i][1][0].upper() + role[i][1][1:], "param": param, "aabb": aabb([i], pad=4.0), "priorita": 2, "menu": menu})
        if stredni:
            stredni_ids.append(f"noha_{i}")
    ram_ids = skupina("ram", "Vestavěný rám (střední opora)", lambda k, rl, d: isinstance(k, tuple) and (k[0] == "ram" or (k[0] == "polic" and k[2] == "XM_pol")) or k in ("XM_prac", "XM_pol"),
                      ["stredni_opora", "stredni_noha"], [pol("Střední nohy místo vestavěného rámu", {"stredni_opora": "noha"}),
                                                          pol("Rám vrátit doprostřed", {"stredni_noha": None}, None if p["stredni_noha"] is not None else "Už je uprostřed.")], priorita=2) \
        if (r.get("panely_info") or {}).get("rezim") == "ram" else []                      # jen ve vestavenem ramu (prícky XM_* jsou i u strednich noh, ale tam patri k nohám)
    for i, d in enumerate(dily):
        if role[i][0] in ("konec", "kolecko"):
            casti.append({"id": f"konec_{i}", "label": "Konec nohy", "param": ["kolecka", "patky"] + (["navlek", "navlek_delka"] if p["system"] in NAVLEK_SYSTEMY else []),
                          "aabb": aabb([i], pad=6.0, minrozmer=40.0), "priorita": 3, "menu": menu_konce()})
    # ---- tahy: rozmery
    leg_pl = next((i for i, k in enumerate(klice_t) if k == ("t", NOHA_PL)), None)
    if leg_pl is not None:
        lo_, hi_ = bb[leg_pl]
        tahy.append({"id": "vyska", "label": "Výška desky", "typ": "osa", "ikona": "sipka_y", "bod": [round(float((lo_[0] + hi_[0]) / 2), 1), round(float(hi_[1]) - _P(), 1), round(float((lo_[2] + hi_[2]) / 2), 1)],
                     "osa": [0.0, 1.0, 0.0], "param": "vyska", "faktor": 1.0, "hodnota": p["vyska"], "min": ROZSAH["vyska"][0], "max": ROZSAH["vyska"][1], "krok": 10.0, "casti": ["deska"],
                     "mereni": [{"label": "výška desky", "param": "vyska"}]})
    tahy.append({"id": "sirka", "label": "Šířka desky", "typ": "osa", "ikona": "sipka_z", "bod": [round((X0 + X1) / 2, 1), y_hore, Z1], "osa": [0.0, 0.0, 1.0], "param": "sirka", "faktor": 2.0,
                 "hodnota": p["sirka"], "min": ROZSAH["sirka"][0], "max": ROZSAH["sirka"][1], "krok": 10.0, "casti": ["deska"], "mereni": [{"label": "šířka desky", "param": "sirka"}]})
    tahy.append({"id": "hloubka", "label": "Hloubka desky", "typ": "osa", "ikona": "sipka_x", "bod": [X0, y_hore, round((Z0 + Z1) / 2, 1)], "osa": [-1.0, 0.0, 0.0], "param": "hloubka", "faktor": 2.0,
                 "hodnota": p["hloubka"], "min": _rz("hloubka")[0], "max": _rz("hloubka")[1], "krok": 10.0, "casti": ["deska"], "mereni": [{"label": "hloubka desky", "param": "hloubka"}]})
    if pan_ids and p["panely"] and pi_.get("pocet"):                                       # posun panelu (s profily a elektrozlabem) po zadnich stojkach
        plo, phi = aabb(pan_ids)
        tahy.append({"id": "panely_posun", "label": "Výška panelů", "typ": "osa", "ikona": "sipka_y", "bod": [round(plo[0], 1), round(phi[1], 1), round((plo[2] + phi[2]) / 2, 1)],
                     "osa": [0.0, 1.0, 0.0], "param": "panely_posun", "faktor": 1.0, "hodnota": round(float(p["panely_posun"]), 1), "min": 0.0, "max": float(math.floor(pi_["posun_max"] / 10.0 + 1e-9) * 10.0),
                     "krok": 10.0, "casti": ["panely"], "mereni": [{"label": "posun panelů nahoru", "param": "panely_posun"}]})
        pz_ = pi_.get("posun_z") or {}
        if float(pz_.get("max", 0.0)) > 0.0:                                                # vodorovne (Robert 2026-10-05: panely pohyblive, maji-li mezi nohama mezeru): mereni = mezery od VSECH noh
            plo2, phi2 = aabb([i for i in pan_ids if dily[i]["part_id"] in PANEL_PARTY])
            zaber_ = pi_.get("zaber") or []
            radky_ = []
            for j_, u_ in enumerate(zaber_):
                pred_ = "" if len(zaber_) == 1 else ("levý panel " if j_ == 0 else "pravý panel ")
                radky_.append({"label": pred_ + ("od levé nohy" if u_["levy"] == "levá noha" else "od střední nohy"), "param": "panely_z", "mul": 1.0, "add": round(u_["mezera"], 1)})
                radky_.append({"label": pred_ + ("od pravé nohy" if u_["pravy"] == "pravá noha" else "od střední nohy"), "param": "panely_z", "mul": -1.0, "add": round(u_["mezera"], 1)})
            tahy.append({"id": "panely_z", "label": "Panely do stran", "typ": "osa", "ikona": "sipka_z", "bod": [round(plo2[0], 1), round((plo2[1] + phi2[1]) / 2, 1), round(phi2[2], 1)],
                         "osa": [0.0, 0.0, 1.0], "param": "panely_z", "faktor": 1.0, "hodnota": round(float(p["panely_z"]), 1), "min": float(pz_["min"]), "max": float(pz_["max"]),
                         "krok": 1.0, "casti": ["panely"], "mereni": radky_})
    sm_ = r.get("stojky_meze")
    leg_zl = next((i for i, k in enumerate(klice_t) if k == ("t", NOHA_ZL)), None)
    if sm_ and leg_zl is not None:                                                          # vyska zadnich stojek (zkracovat i natahovat; rameno LED jede s nimi)
        lo_, hi_ = bb[leg_zl]
        tahy.append({"id": "stojky_vyska", "label": "Výška zadních stojek", "typ": "osa", "ikona": "sipka_y", "bod": [round(float((lo_[0] + hi_[0]) / 2), 1), round(float(hi_[1]) - 40.0, 1), round(float((lo_[2] + hi_[2]) / 2), 1)],
                     "osa": [0.0, 1.0, 0.0], "param": "stojky_vyska", "faktor": 1.0, "hodnota": round(float(sm_["hodnota"]), 1), "min": float(math.ceil(sm_["min"] / 10.0 - 1e-9) * 10.0), "max": float(sm_["max"]), "krok": 10.0,
                     "casti": [f"noha_{leg_zl}"], "mereni": [{"label": "výška stojek nad deskou", "param": "stojky_vyska"}]})
    zm_ = elzlab_meze(r) if (zlab_ids and p["elektrozlab"]) else None
    if zlab_ids and zm_:                                                                    # elektrozlab: svisle (y) i do stran (z), vzdy v dotyku s panelem nebo profilem
        zlo, zhi = aabb(zlab_ids)
        tahy.append({"id": "elzlab_y", "label": "Elektrožlab: výška", "typ": "osa", "ikona": "sipka_y", "bod": [round(zlo[0], 1), round(zhi[1], 1), round((zlo[2] + zhi[2]) / 2, 1)], "osa": [0.0, 1.0, 0.0],
                     "param": "elzlab_y", "faktor": 1.0, "hodnota": zm_["y"]["hodnota"], "min": zm_["y"]["min"], "max": zm_["y"]["max"], "krok": 10.0, "casti": ["elektrozlab"],
                     "mereni": [{"label": "posun elektrožlabu nahoru", "param": "elzlab_y"}]})
        tahy.append({"id": "elzlab_z", "label": "Elektrožlab: do stran", "typ": "osa", "ikona": "sipka_z", "bod": [round(zlo[0], 1), round((zlo[1] + zhi[1]) / 2, 1), round(zhi[2], 1)], "osa": [0.0, 0.0, 1.0],
                     "param": "elzlab_z", "faktor": 1.0, "hodnota": zm_["z"]["hodnota"], "min": zm_["z"]["min"], "max": zm_["z"]["max"], "krok": 10.0, "casti": ["elektrozlab"],
                     "mereni": [{"label": "posun elektrožlabu doprava", "param": "elzlab_z"}]})
    if pet_ids and p["drzak_pet"]:
        plo, phi = aabb(pet_ids)
        pm = r.get("pet_meze") or {}
        tahy.append({"id": "pet_posun", "label": "Výška držáku PET", "typ": "osa", "ikona": "sipka_y", "bod": [round((plo[0] + phi[0]) / 2, 1), round((plo[1] + phi[1]) / 2, 1), round((plo[2] + phi[2]) / 2, 1)],
                     "osa": [0.0, 1.0, 0.0], "param": "pet_posun", "faktor": 1.0, "hodnota": pm.get("hodnota", p["pet_posun"]), "min": pm.get("min", p["pet_posun"] - 100.0), "max": pm.get("max", p["pet_posun"] + 100.0),
                     "krok": 10.0, "casti": ["pet"], "mereni": [{"label": "posun držáku", "param": "pet_posun"}]})
    if suplik_ids:
        blo, bhi = aabb([i for i in suplik_ids if dily[i]["part_id"] in SUPLIK_PARTY_VSE])
        tahy.append({"id": "suplik_posun", "label": "Posun šuplíků", "typ": "osa", "ikona": "sipka_z", "bod": [blo[0], round((blo[1] + bhi[1]) / 2, 1), round((blo[2] + bhi[2]) / 2, 1)],
                     "osa": [0.0, 0.0, -1.0 if p["suplik_vlevo"] else 1.0], "param": "suplik_posun", "faktor": 1.0, "hodnota": (r.get("suplik_meze") or {}).get("hodnota", p["suplik_posun"]),
                     "min": (r.get("suplik_meze") or {}).get("min", -max(0.0, p["sirka"] - 700.0)), "max": (r.get("suplik_meze") or {}).get("max", 80.0), "krok": 10.0, "casti": ["suplik"],
                     "mereni": [{"label": "posun šuplíků", "param": "suplik_posun"}]})
    if led_ids and p["led"] and p["stojky"]:
        arm = next((i for i, k in enumerate(klice_t) if k == ("t", XRAIL_TOP_L)), None)
        if arm is not None:
            alo, ahi = bb[arm]
            tahy.append({"id": "led_rameno", "label": "Délka ramene LED", "typ": "osa", "ikona": "sipka_x", "bod": [round(float(alo[0]), 1), round(float((alo[1] + ahi[1]) / 2), 1), round(float((alo[2] + ahi[2]) / 2), 1)],
                         "osa": [-1.0, 0.0, 0.0], "param": "led_rameno", "faktor": 1.0, "hodnota": p["led_rameno"], "min": ROZSAH["led_rameno"][0], "max": ROZSAH["led_rameno"][1], "krok": 10.0,
                         "casti": ["led"], "mereni": [{"label": "délka ramene", "param": "led_rameno"}]})
    # ---- tah: stredni noha (nahrazuje starsi vodici.stredni_noha; zakazana pasma v jednotkach parametru = mm od leve nohy)
    sn = (r.get("vodici_scena") or {}).get("stredni_noha")
    if sn:
        zl_, zr_ = sn["z_levy"], sn["z_pravy"]
        tahy.append({"id": "stredni_noha", "label": "Střední noha", "typ": "osa", "ikona": "sipka_z", "bod": [round(sn["x"], 1), round(sn["y"], 1), round(sn["z"], 1)], "osa": [0.0, 0.0, 1.0],
                     "param": "stredni_noha", "faktor": 1.0, "hodnota": round(sn["z"] - zl_, 1), "min": round(sn["min"] - zl_, 1), "max": round(sn["max"] - zl_, 1), "krok": 1.0,
                     "zakazano": [[round(a - zl_, 1), round(b - zl_, 1)] for a, b in sn.get("zakazano", [])], "odstup_od_prekazky": ODSTUP_PRI_TAZENI, "casti": (stredni_ids or (["ram"] if ram_ids else [])),
                     "mereni": [{"label": "od levé nohy", "param": "stredni_noha", "mul": 1.0, "add": 0.0}, {"label": "od pravé nohy", "param": "stredni_noha", "mul": -1.0, "add": round(zr_ - zl_, 1)}]})
    _zive_operace(dily, klice_t, bb, p, tahy)
    return {"jednotky": "mm; GLB: X hloubka (dozadu), Y nahoru, Z šířka (doprava)", "deska": {"pocatek": [X0, y_hore, Z0], "hloubka": round(D, 1), "sirka": round(W, 1)}, "casti": casti, "tahy": tahy}


PROTAHOVANE = PROFIL_PARTS + ("product_4933",)      # dily, ktere se pri zmene rozmeru stolu protahuji (profil 30x30 / 40x40, laminodeska); vse ostatni se jen posouva


def _zive_operace(dily, klice_t, bb, p, tahy):
    """Ke kazdemu tahu (kde to jde) doplni `zive`: operace, kterymi prohlizec behem tazeni HYBE vrcholy dilu primo v nactenem modelu (bez dotazu na server), aby se
    model pohyboval plynule. Operace pracuji s indexy dilu `ix` (jako v `dily`; kde jsou jejich vrcholy v GLB rika `zive_rozsahy` z api/stul_glb.py), delta d = k * (posun uchytu
    podel `osa` v mm):
      posun    {ix, k}          vsechny vrcholy dilu o d podel osy
      natahni  {ix, strana, k}  jen vrcholy na strane `strana` (+1/-1 vuci stredu dilu podel osy) o d (jeden konec dilu se pohne, druhy zustane)
      roztahni {ix, k}          vrcholy na kladne strane o +d, na zaporne o -d (dil se protahne na obe strany)
    Vrcholy PRESNE uprostred dilu (|u - stred| <= 0,05 mm; mesh desky ma stredovy vrchol plochy) se pri `natahni` pohnou o d/2 (lezi uprostred natazeneho dilu) a pri `roztahni` zustanou - bez toho
    by o jejich strane rozhodl zaokrouhlovaci sum (deska se pri natazeni jednoho konce zdeformovala az o d/2).
    Presnost: strední noha, rameno LED a suplik jsou PRESNE (test porovnava s modelem ze serveru), rozmery stolu jsou NAHLED (po pusteni uchytu prijde presny model).
    Vyrezy v desce se nehybou (deska je jeden souvisly povrch) - tam zustava obnova ze serveru."""
    n = len(dily)
    prof = [i for i in range(n) if dily[i]["part_id"] in PROFIL_PARTS]
    spojky = [i for i in range(n) if dily[i]["part_id"] in SPOJKY_PARTS]
    ind_klic = {klice_t[i]: i for i in range(n)}

    def zasl_hostu(ids):
        """Indexy zaslepek VOLNYCH KONCU profilu (klic ("zasl", klic profilu, "+" | "-")), jejichz profil je mezi `ids`: jedou s nim (stejna operace jako profil, ktery se hybe CELY)."""
        mnozina = set(ids)
        return [i for i in range(n) if _je_zasl(klice_t[i]) and ind_klic.get(klice_t[i][1]) in mnozina]

    def dotyk(a, b, pad):
        return bool((np.minimum(bb[a][1], bb[b][1]) - np.maximum(bb[a][0], bb[b][0]) > -pad).all())

    def op_posun(ids, k=1.0):
        return {"op": "posun", "ix": sorted(int(i) for i in ids), "k": k} if ids else None

    def op_natahni(ids, strana, k=1.0):
        return {"op": "natahni", "ix": sorted(int(i) for i in ids), "strana": strana, "k": k} if ids else None

    def op_roztahni(ids, k=1.0):
        return {"op": "roztahni", "ix": sorted(int(i) for i in ids), "k": k} if ids else None

    def dej(tid, ops):
        t = next((x for x in tahy if x["id"] == tid), None)
        ops = [o for o in ops if o]
        if t is not None and ops:
            t["zive"] = ops

    for k_led in range(1, LED_MAX + 1):                                   # svitidla LED (Robert 2026-10-08): svitidlo cislo k jede samo podel profilu (osa Z); jeho poloha je primo parametr led_z<k>, ostatni dily stoji
        i_led = ind_klic.get(("t", LED) if k_led == 1 else ("led", k_led - 1))
        if i_led is not None:
            dej(f"led_z{k_led}", [op_posun([i_led], 1.0)])

    # ---- stredni noha: noha, jeji kolecka/patky, prícky a spojky se posunou; rámy vlevo/vpravo od ní se zkrátí/prodlouží o jeden konec
    mid_klice = ("FM", "RM", "kolecko_FM", "kolecko_RM", "XM_prac", "XM_pol", "XM_top", ("konec", "FM"), ("konec", "RM"), ("konec", "FM", "navlek"), ("konec", "RM", "navlek"), ("konec", "FM", "zasl"), ("konec", "RM", "zasl"))
    R0 = [i for i in range(n) if klice_t[i] in mid_klice or (isinstance(klice_t[i], tuple) and klice_t[i][0] == "vz" and klice_t[i][1] == "M")]
    R0 += zasl_hostu(R0)                                                  # zaslepka volneho konce hybneho profilu (stredni pricka ramene LED) jede s nim
    # odvozene spojky (n): hybe se jen ta, ktera drzi hybny dil (stredni noha, jeji pricky); spojky panelovych profilu u krajnich noh stoji
    R = R0 + [i for i in range(n) if isinstance(klice_t[i], tuple) and klice_t[i][0] == "n" and any(dotyk(i, j, 2.0) for j in R0 if dily[j]["part_id"] in PROFIL_PARTS)]
    legs = [i for i in range(n) if klice_t[i] in ("FM", "RM")]
    levy = pravy = []
    R_ram = []
    # desky delene u stredni opory (_deli_desku_u_opory): leva cast ma u opory PRAVY konec, prava cast LEVY konec - hybou se s osou opory jako konce podelniku. Jen desky z jednoho kusu
    # (kusy kolem vyrezu nemaji vlastni vrcholy v GLB: tam zustava obnova ze serveru, viz poznamka u `plne`)
    patra_kusy = {str(d["deska_id"]).rsplit("_", 1)[0] for d in dily if d.get("deska_id") and (d.get("deska_celek") or d.get("deska_kus"))}      # patra (prac / pol<k>) s kusy kolem vyrezu: jejich cast je v GLB jeden povrch bez rozsahu
    def _deska_strany(koncovka):                                          # (obe poloviny takove desky zustanou pri tazeni pevne - aby se leva a prava cast nepretahly / neroztrhly)
        return [i for i in range(n) if dily[i]["part_id"] == "product_4933" and not (dily[i].get("deska_celek") or dily[i].get("deska_kus"))
                and str(dily[i].get("deska_id") or "").endswith(koncovka) and not str(dily[i].get("deska_id")).startswith("polvyr")
                and str(dily[i]["deska_id"]).rsplit("_", 1)[0] not in patra_kusy]
    desky_l, desky_r = (_deska_strany("_0"), _deska_strany("_1")) if any(str(d.get("deska_id") or "").endswith("_1") for d in dily) else ([], [])
    if legs:
        mlo = min(bb[i][0][2] for i in legs)
        mhi = max(bb[i][1][2] for i in legs)
        levy = [i for i in prof if i not in R and abs(bb[i][1][2] - mlo) < 2.0 and bb[i][1][2] - bb[i][0][2] > 100.0]
        pravy = [i for i in prof if i not in R and abs(bb[i][0][2] - mhi) < 2.0 and bb[i][1][2] - bb[i][0][2] > 100.0]
        panel_i = [i for i in range(n) if (isinstance(klice_t[i], tuple) and klice_t[i][0] == "pan") or klice_t[i] == ("t", ELZLAB)]          # panel a elektrozlab se stredi v useku: hybou se napul
        dej("stredni_noha", [op_posun(R), op_natahni(levy, 1), op_natahni(pravy, -1), op_posun(panel_i, 0.5), op_natahni(desky_l, 1), op_natahni(desky_r, -1)])
    else:                                                                    # vestaveny ram: podelniky jdou cele, hybe se jen ram (svisle profily, pricky vsech polic a jejich spojky)
        ram_i = [i for i in range(n) if klice_t[i] in ("XM_prac", "XM_pol") or (isinstance(klice_t[i], tuple) and (klice_t[i][0] == "ram" or (klice_t[i][0] == "polic" and klice_t[i][2] == "XM_pol")))]
        if ram_i:
            sp_r = [i for i in spojky if any(dotyk(i, j, 2.0) for j in ram_i)]
            R_ram = ram_i + sp_r + zasl_hostu(ram_i)
            dej("stredni_noha", [op_posun(R_ram), op_natahni(desky_l, 1), op_natahni(desky_r, -1)])
    # ---- rameno LED: ramena se prodlouzi predním koncem (smer osy = dopredu), pricka u ramen, LED a rohové spojky na predním konci se posunou
    ramena = [i for i in range(n) if klice_t[i] in (("t", XRAIL_TOP_L), ("t", XRAIL_TOP_P), "XM_top")]
    if ramena:
        predni_x = min(bb[i][0][0] for i in ramena)
        stred_y = float(np.mean([(bb[i][0][1] + bb[i][1][1]) / 2 for i in ramena]))
        pevne = [i for i in range(n) if klice_t[i] == ("t", ZRAIL_TOP) or dily[i]["part_id"] in LED_PARTY]
        pevne += [i for i in spojky if abs((bb[i][0][0] + bb[i][1][0]) / 2 - (predni_x + _H())) < 20.0 + _H() and abs((bb[i][0][1] + bb[i][1][1]) / 2 - stred_y) < 30.0 + _H()]
        pevne += zasl_hostu(pevne)                                                   # zaslepky volnych koncu pricky nad LED jedou s pricnou
        dej("led_rameno", [op_posun(pevne), op_natahni([i for i in ramena], 1)])
    # ---- suplik: boxy, jejich prícky a spojky na nich
    boxy = [i for i in range(n) if dily[i]["part_id"] in SUPLIK_PARTY_VSE]
    prickyb = [i for i in range(n) if klice_t[i] in (("t", XRAIL_BOX1), ("t", XRAIL_BOX2), ("seg", XRAIL_BOX1), ("seg", XRAIL_BOX2))]
    if boxy:
        sp = [i for i in spojky if any(dotyk(i, j, 2.0) for j in prickyb)]
        dej("suplik_posun", [op_posun(boxy + prickyb + sp + zasl_hostu(prickyb))])
    pety = [i for i in range(n) if dily[i]["part_id"] == "product_4928"]
    if pety:
        dej("pet_posun", [op_posun(pety)])
    # ---- rozmery desky: NAHLED (po pusteni uchytu prijde presny model ze serveru)
    plne = [i for i in range(n) if not (dily[i].get("deska_celek") or dily[i].get("deska_kus"))]
    if not plne:
        return
    lo_all = np.min([bb[i][0] for i in plne], axis=0)
    hi_all = np.max([bb[i][1] for i in plne], axis=0)

    def rozmer(osa_idx, znam, zdola):
        if osa_idx == 2 and (legs or R_ram):
            # sirka se stredni nohou / ramem: opora drzi vzdalenost od leve nohy (stredni_noha zadana) -> jde s levou stranou, pravy usek (i prava deska) se protahne na obe strany;
            # opora uprostred (stredni_noha None) zustava a oba useky (i desky) se protahnou na vnejsi konec
            R_ = R if legs else R_ram
            if p.get("stredni_noha") is not None:
                zvl = [op_posun(R_ + levy + desky_l, -1.0), op_roztahni(pravy + desky_r)]
            else:
                zvl = [op_natahni(levy + desky_l, -1, -1.0), op_natahni(pravy + desky_r, 1, 1.0)]
            vynech = set(R_) | set(levy) | set(pravy) | set(desky_l) | set(desky_r)
        elif osa_idx == 0:
            # hloubka: horni ram (ramena, pricka u ramen, LED, spojky nahore) je pevne na zadnich stojkach -> jde se zadni stranou (osa smeruje dopredu: zadni = zaporny smer)
            vrch = float(hi_all[1])
            horni = [i for i in plne if ((bb[i][0][1] + bb[i][1][1]) / 2.0 > vrch - 120.0 and dily[i]["part_id"] not in PROFIL_PARTS)
                     or (dily[i]["part_id"] in PROFIL_PARTS and bb[i][0][1] > vrch - 70.0) or _je_vz(klice_t[i])]          # vzpery ramen jsou na zadnich stojkach a rameni
            zvl, vynech = [op_posun(horni, -1.0)], set(horni)
        else:
            zvl, vynech = [], set()
        T0, T1 = (lo_all[osa_idx], hi_all[osa_idx]) if znam > 0 else (-hi_all[osa_idx], -lo_all[osa_idx])
        T = T1 - T0
        Cc = (T0 + T1) / 2.0
        roz, pos_p, pos_m, nat = [], [], [], []
        # vyska: kazdy SVISLY profil, ktery stoji na podlaze (nejnizsi spodek profilu), se natahuje horním koncem - jinak by kratsi (predni) nohy, kratsi nez polovina
        # celkove vysky stolu (s rameny LED a zadnimi stojkami), nesly nahoru celé a pod nimi by zustala mezera (Robert 2026-10-04: "smerem nahoru zustava mezera")
        dno = min((bb[j][0][1] for j in plne if dily[j]["part_id"] in PROFIL_PARTS), default=None) if (zdola and osa_idx == 1) else None
        for i in plne:
            if i in vynech:
                continue
            a, b = bb[i][0][osa_idx] * znam, bb[i][1][osa_idx] * znam
            lo_, hi_ = min(a, b), max(a, b)
            ext, c = hi_ - lo_, (lo_ + hi_) / 2.0 - Cc
            ex_, ez_ = bb[i][1][0] - bb[i][0][0], bb[i][1][2] - bb[i][0][2]
            stoji_na_podlaze = dno is not None and dily[i]["part_id"] in PROFIL_PARTS and ext >= 300.0 and ext > 3.0 * max(ex_, ez_) and abs(bb[i][0][1] - dno) < 2.0
            if (ext > 0.5 * T or stoji_na_podlaze) and dily[i]["part_id"] in PROTAHOVANE:
                (nat if zdola else roz).append(i)           # protahuji se jen profily a desky; prislusenstvi (panely, LED, elektrozlab, boxy...) MA FIXNI VELIKOST
            elif zdola:
                if (lo_ + hi_) / 2.0 > 0.5 * p["vyska"]:
                    pos_p.append(i)
            elif abs(c) > 0.2 * T:
                (pos_p if c > 0 else pos_m).append(i)
        if zdola:
            return [op_natahni(nat, 1), op_posun(pos_p)]
        return [op_roztahni(roz), op_posun(pos_p), op_posun(pos_m, -1.0)] + zvl
    for t_ in [x["id"] for x in tahy if x["id"].startswith("police_h") or x["id"] in ("panely_posun", "panely_z", "stojky_vyska", "elzlab_y", "elzlab_z")]:           # vyska polic, panelu, stojek a pohyb elektrozlabu: vzdy ze sondy (heuristika `rozmer` pro ne neexistuje)
        ops_p = _zive_sondou(dily, klice_t, bb, p, tahy, t_)
        if ops_p is not None:
            dej(t_, ops_p)
    for tid_, osa_, znam_, zdola_ in (("sirka", 2, 1.0, False), ("hloubka", 0, -1.0, False), ("vyska", 1, 1.0, True)):
        ops_ = _zive_sondou(dily, klice_t, bb, p, tahy, tid_)               # presne (z sondy); heuristika `rozmer` jen kdyz sonda nejde (prah, kde se meni sada dilu)
        dej(tid_, ops_ if ops_ is not None else rozmer(osa_, znam_, zdola_))


def _zive_sondou(dily, klice_t, bb, p, tahy, tid):
    """Operace `zive` tahu `tid` (sirka / hloubka / vyska) ZE SONDY: stul se poskladá znovu pro o kousek vetsi (nebo mensi) rozmer a kazdy dil se zaradi podle toho, co se s nim OPRAVDU stalo -
    pevny / cely se posunul / natahl se jeho jeden konec / protahl se na obe strany. Heuristika podle polohy dilu (`rozmer`) selhavala u kazdeho stolu trochu jinak (predni nohy kratsi nez pul
    vysky stolu se posunuly cele misto natazeni = mezera u koleček; police a podpery police na pevne vysce se pri nizke desce posunuly; deska se pri zmene hloubky/sirky natahla o polovinu -
    Robert 2026-10-04: "smerem nahoru zustava mezera, nenatahuje se to plynule"). Sonda neni odhad: stejne dily, stejne klice, jen jiny rozmer.
    Zkousi kroky +100, -100, +30, -30 mm (prahy, kde pribyvaji/ubyvaji dily, sonda "preskoci"); vraci None (-> heuristika `rozmer`), kdyz se nepovedl zadny krok: sada dilu se zmenila nebo se nejaky
    dil zmenil jinak nez posunem / natazenim podel osy tahu."""
    t = next((x for x in tahy if x["id"] == tid), None)
    if t is None or not t.get("faktor"):
        return None
    osa = np.array(t["osa"], float)
    ax = int(np.argmax(np.abs(osa)))
    if abs(osa[ax]) < 0.99:
        return None
    par = t.get("param") or tid                                         # parametr, ktery tah meni (u rozmeru stejny nazev jako id tahu)
    if tid in ROZSAH:
        lo_p, hi_p, base = ROZSAH[tid][0], ROZSAH[tid][1], p[tid]
    else:                                                               # ostatni tahy (vyska polic...): meze a efektivni hodnota z popisu tahu (parametr muze byt None = automaticky)
        lo_p, hi_p, base = t["min"], t["max"], t["hodnota"]
    kk = lambda c, dv: round(c * t["faktor"] / (dv * osa[ax]), 6)      # posun vrcholu o c mm podel osy  ->  koeficient operace (d = k * posun uchytu)
    sm = 1 if osa[ax] > 0 else -1                                      # kladny konec dilu (souradnice) je na kladne strane osy tahu jen kdyz osa miri do kladnych souradnic

    def tup(k):
        return tuple(tup(x) for x in k) if isinstance(k, (list, tuple)) else k
    kroky = (100.0, -100.0, 30.0, -30.0) + ((10.0, -10.0, 5.0, -5.0, 2.0, -2.0) if p.get("navlek") else ()) + ((10.0, -10.0, 5.0, -5.0, 2.0, -2.0, 1.0, -1.0) if par == "panely_z" else ())      # s navlekem je nejnizsi police tesne nad nim: tahy polic maji jen par mm rezervy -> mensi kroky sondy; panely maji mezi nohama casto jen par mm
    for dv in kroky:
        if not (lo_p <= base + dv <= hi_p):
            continue
        try:
            r2 = sestav_stul(**{**p, par: base + dv})
        except StulChyba:
            continue
        if len(r2["dily"]) != len(dily) or [tup(k) for k in r2["klice"]] != list(klice_t) or any(a["part_id"] != b["part_id"] for a, b in zip(dily, r2["dily"])):
            continue
        skup, ok = {}, True
        bb2 = [_aabb(d) for d in r2["dily"]]
        # GLB se vycentruje v X/Z podle obalky celého stolu a podlaha je y = 0 (api/stul_glb.py): zmena rozmeru tedy posune i "pevne" dily - tazeni pracuje v souradnicich GLB
        lo1, hi1 = np.min([b[0] for b in bb], axis=0), np.max([b[1] for b in bb], axis=0)
        lo2, hi2 = np.min([b[0] for b in bb2], axis=0), np.max([b[1] for b in bb2], axis=0)
        glb_posun = (-lo2[1] + lo1[1]) if ax == 1 else (-(lo2[ax] + hi2[ax]) / 2.0 + (lo1[ax] + hi1[ax]) / 2.0)
        for i in range(len(dily)):
            dlo, dhi = bb2[i][0] - bb[i][0], bb2[i][1] - bb[i][1]
            if max(abs(dlo[j]) for j in range(3) if j != ax) > 0.5 or max(abs(dhi[j]) for j in range(3) if j != ax) > 0.5:
                ok = False
                break
            clo, chi = float(dlo[ax] + glb_posun), float(dhi[ax] + glb_posun)
            if abs(clo) < 0.5 and abs(chi) < 0.5:
                continue                                               # pevny dil (kolecka, spodni police a podpery pri zmene vysky, ...)
            if abs(clo - chi) < 0.5:
                klice = [("posun", None, kk((clo + chi) / 2.0, dv))]
            elif abs(clo) < 0.5:
                klice = [("natahni", sm, kk(chi, dv))]                 # pohnul se jen kladny konec dilu
            elif abs(chi) < 0.5:
                klice = [("natahni", -sm, kk(clo, dv))]
            else:                                                      # oba konce jinak (typicky dil rostouci z jedne strany po vycentrovani GLB): posun o stred + protazeni
                klice = ([("posun", None, kk((clo + chi) / 2.0, dv))] if abs(clo + chi) >= 0.5 else []) + [("roztahni", None, round((chi - clo) / 2.0 * t["faktor"] / (dv * abs(osa[ax])), 6))]
            for klic in klice:
                skup.setdefault(klic, []).append(i)
        if not ok:
            continue
        ops = []
        for (op, strana, k), ids in sorted(skup.items(), key=lambda kv: (kv[0][0], kv[0][1] or 0, kv[0][2])):
            o = {"op": op, "ix": sorted(ids), "k": k}
            if strana is not None:
                o["strana"] = strana
            ops.append(o)
        return ops
    return None


# Hmotnost laminodesky 18 mm (DTDL): plech 2800 x 2070 mm = cca 65 kg (11-12 kg/m2) - Robert 2026-10-03. Katalog u karty 4933 hmotnost nema a ve scene se
# hmotnost desky NEprepocitava podle plochy (configurator_price._entry_weight_price) - proto se vaha desek stolu pocita tady z SKUTECNE plochy kusu.
LAMINO_KG_NA_M2 = 65.0 / (2.8 * 2.07)


def plocha_lamino_m2(dily):
    """Skutecna plocha vsech lamino desek stolu v m2 (pracovni deska bez vyrezu = kusy kolem otvoru, spodni police, police pod vyrezem);
    meritko desky: lokalni x/y = rozmery v mm / 1000 (mesh 1000 x 1000 x 18)."""
    return sum(d["scale"][0] * d["scale"][1] for d in dily if d["part_id"] == "product_4933")


def hmotnost_lamino_kg(dily):
    return plocha_lamino_m2(dily) * LAMINO_KG_NA_M2


def hmotnost_navleku_kg(dily):
    """Hmotnost navleku nohou (jekl 40x40x2: ocel 2,32 kg/m + plastova zaslepka) v kg; katalog nema karty, proto se pocita z delky jeklu (meritko y = delka / 1000)."""
    return sum(d["scale"][1] * NAVLEK_KG_NA_M for d in dily if d["part_id"] == NAVLEK_PART) + NAVLEK_ZASLEPKA_KG * sum(1 for d in dily if d["part_id"] == NAVLEK_ZASLEPKA)


SSE_KG_NA_M_PROFIL = 7850.0 * (SSE_PROFIL ** 2 - (SSE_PROFIL - 4.0) ** 2) / 1.0e6      # vnitrni profil 35x35 (PREDPOKLAD: trubka se stenou 2 mm, 2,07 kg/m; skutecny prurez zatim neni zadan)
SSE_PLECH_KG = 7850.0 * SSE_PLECH_SIRKA * SSE_PLECH_VYSKA * SSE_PLECH_TL / 1.0e9           # ocelova plechova patka 150x40x6 (0,28 kg)
SSE_PATKA_KG = 0.01                                                                          # plastova zaslepka vnitrniho profilu (odhad)


def hmotnost_nohou_sse_kg(dily):
    """Hmotnost dilu nohou SSE v kg (ODHAD z rozmeru: jekl 40x40x2 ocel 2,32 kg/m, vnitrni profil trubka 35x35x2, plechy 150x40x6, plastove zaslepky); dily nohy nemaji kartu katalogu."""
    kg = 0.0
    for d in dily:
        pid, L = d["part_id"], d["scale"][1]
        if pid == SSE_JEKL_PART:
            kg += L * NAVLEK_KG_NA_M
        elif pid == SSE_PROFIL_PART:
            kg += L * SSE_KG_NA_M_PROFIL
        elif pid == SSE_PLECH_PART:
            kg += SSE_PLECH_KG
        elif pid == SSE_PATKA_PART:
            kg += SSE_PATKA_KG
    return kg


def entries_pro_cenu(dily):
    """Vstup pro api/configurator_price.price_entries: [{part_id, length_mm | width_mm+height_mm, joint_count}].
    Profil: delka = scale.y * 1000; deska (laminodeska): rozmer z meritka x/y (karta 1000 x 1000); spoj (profil-profil) pocita
    ten profil, ktery ma v lic_peers nizsi index (jako scena - drzitel spoje)."""
    spoje = {}
    for i, d in enumerate(dily):
        if d["part_id"] not in PROFIL_PARTS:
            continue
        spoje[i] = sum(1 for j in (d.get("lic_peers") or []) if dily[j]["part_id"] in PROFIL_PARTS)
    out = []
    for i, d in enumerate(dily):
        if d["part_id"] in NAVLEK_PARTS or d["part_id"] in SSE_PARTS:
            continue                                      # navlek (jekl) a jeho zaslepka a dily nohy SSE nejsou karty katalogu: cena je pravidlo (stul_api.extra_prace), vcetne zaslepky
        e = {"part_id": d["part_id"]}
        if d["part_id"] in PROFIL_PARTS:
            e["length_mm"] = round(1000.0 * d["scale"][1], 3)
            e["joint_count"] = spoje.get(i, 0)
        elif d["part_id"] == "product_4933" or d["part_id"] in _hpol().DESKA_PARTY:
            if d.get("deska_kus"):
                continue                                  # dalsi kus rozrezane desky (vyrez): cena je cena cele desky
            if d.get("deska_celek"):
                e["width_mm"], e["height_mm"] = d["deska_celek"][0], d["deska_celek"][1]
            else:
                e["width_mm"] = round(1000.0 * d["scale"][0], 3)
                e["height_mm"] = round(1000.0 * d["scale"][1], 3)
        out.append(e)
    return out

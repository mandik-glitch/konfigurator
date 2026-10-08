"""Pohyblive dily Vandr karty pro 3D nabidku (bot10, 2026-10-01, Robert: "(5)
animace realnych pohybu - vysuv supliku, sklopeni dvirek po odjisteni pinu,
vyzvednuti boxu").

Modul vola scripts/v3d/vandr_offer_build.py (hook detect(api)) PRED
slucovanim statickych dilu a PRED prejmenovanim na n/p/m - tady jsou jeste
puvodni jmena uzlu, role (skupina nad meshem) a materialy. Do vystupniho GLB
se z toho nedostane nic krome cisel (pivoty p01.., kroky pohybu v kontraktu
v3d v1) a druhu boxu `sub` (Robert 2026-10-02: vyctem klt | multibox | eurobox |
kufrik, jen u boxu - viewer jmenuje cipy "KLT box N" / "Multibox N" / "Eurobox N"). Rozhrani api viz docstring buildu.

ZDROJE (poradi, pruzkum B 2026-10-01):
 1) typ komponenty = uzel '<X>(Clone)' pod 'Nohy*' <-> unity_id (klic bez
    tecek; sporne/nejednoznacne klice podle pozice ze stored_model_parts.data,
    Unity (x, y, z) m -> glTF (-x, y, z) mm),
 2) kusovnik komponenty (ctx.komponenty[].dily = components_parts):
      Pojezdy.<delka>...      -> suplik/vysuv, draha = delka kolejnice
      Pant_*                  -> sklopna dvirka (osa = primka kloubu)
      Kluzny_sroub_M10        -> podlahova dvirka (osa = kluzne srouby)
      Zapadka_* / Zamek*      -> predkrok odjisteni (pin) pred sklopenim
      BOX.KLT / Box.grey / Multibox -> zvednuti boxu
 3) geometrie (lokalni ram komponenty: X sirka, -Y celo, +Z nahoru; v mm):
      kolejnice = chrom, > 300 mm v Y, < 16 mm v X; na kazde strane dvojice
        vnejsi (vyssi, PEVNA) + vnitrni (nizsi, jede); dvojice stran zleva
        doprava = jeden suplik; jede vse mezi vnejsimi kolejnicemi (krome
        nosniku 45x45/SL40) + dily pred celem kolejnic (zamek vysuvu)
      klouby pantu = cerne valce ~13x13x50 na jedne primce (+-1 mm)
      kridlo = dily v predni zone nad osou, souvisle spojene s nejsirsim
        dilem (lista/panel); pant (jeden mesh pro obe kridla) se rozrizne
        v ose, horni pulka jede s kridlem
      podlahova dvirka: osa = kluzne srouby M10 v dutine NOSNEHO profilu
        (zaobleny R45x45 - primka sroubu lezi uvnitr jeho prurezu). Pak je
        kridlem CELY ram komponenty (nosny profil + sloupky + horni pricka +
        panel v drazkach + dorazy + knofliky zapadek), osove srouby zustavaji.
        Samotny panel vyklopit nejde: je 15 mm v drazce nosneho profilu
        (lezi na jejim dne) a 10 mm v drazce horni pricky (nalez 7 kontroly
        2026-10-01). Draha se pred prijetim proveri (otoceni po 2,5 st.,
        obaly dilu proti trojuhelnikum vseho, co se nehybe); naraz = dvirka
        zustanou staticka s varovanim.
      pin = chromovy valec ~8x8x10 (svisly) + cerny knoflik ~12x12x5 nad nim
        (+ modra zapadka, pokud ji build nevyradil jako kryci listu)
      box = material blue KLT / box tmava / multibox, vsechny rozmery
        >= 60 mm; drobne dily uvnitr jeho obrysu (dno, vlozka) jedou s nim
 4) vychozi hodnoty: ctx.pohyby_vychozi (pohyby-vychozi.json), jinak
    VYCHOZI nize (s varovanim).

Co pravidla nesplni, zustava STATICKE a jde do varovani (vidi jen admin) -
nic se nehada. Pin (posun podel osy X) je hypoteza z geometrie, oznaceno ve
varovanich.

Pivoty: prazdne uzly s jednotkovou rotaci, origin v glTF mm (osa pantu na
primce kloubu; u kolejnice zacatek = predni konec pevne kolejnice, stred mezi
stranami; u boxu stred dna). Vnorene: pin pod dvirky, box pod vysuvem.
Osa ax je v souradnicich rodice = svet (rodic ma jednotkovou rotaci).
Otoceni dvirek: osa orientovana podle "vpravo" z pohledu zakaznika (cross(
-front, up)), znamenko uhlu urcuje geometrie tak, aby se teziste kridla
posunulo k celu komponenty (prava strana karty 4917 tedy opacne nez leva).

Cislovani n (popisky "Suplik 1", "Dvirka 2", "KLT box 3"...): zvlast pro kazdy druh
a u boxu zvlast pro kazdy druh boxu (k, sub), deterministicky: strana (left,
bulkhead, right), sloupec (dvojice noh) zleva doprava z pohledu pred touto
stranou, v nem shora dolu, pak zleva doprava. Poradi pohybu ve vystupu (druh,
pozice v ramu cela) je stejne jako dosud.

Druh boxu `sub` (nic se nehada): zdroje jsou (1) material = ROLE skupiny nad meshem
skorepiny (Multibox_Arc -> multibox, blue_klt -> klt, dark_grey_bin -> eurobox;
rodina materialu je nekonzistentni, viz _render_prirazeni_lib), (2) kusovnik
komponenty (BOX.KLT* -> klt, Box.grey* -> eurobox, Multibox* -> multibox, jen kdyz je
v kusovniku prave jeden druh), (3) klicove slovo v unity_id komponenty (multibox,
klt, eurobox, kufrik). Vsechny zdroje, ktere neco rekly, se musi shodovat; pri
sporu nebo bez zdroje sub chybi + varovani (viewer pak rekne jen "Box N").

Kontrola kolize boxu: pri plnem otevreni (vysuv vysunut + box zvednut,
resp. box vytazeny z police) se AABB boxu nesmi protnout s AABB zadneho
dilu, ktery se s nim nehybe (ve 3 osach). Jinak box zustane na miste
(jede jen s vysuvem) a jde varovani.

Uhel sklopnych dvirek (pohyby-vychozi.json dvirka.uhel_deg, Robert 2026-10-01
120 st.) se omezuje sweepem kolizi po 5 st., nejnize na 90 st.: (a) pri detekci
proti dilum, ktere se nehybou (vlastni pant neni prekazka), (b) PO sestaveni
vsech komponent proti trojuhelnikum PLNE VYSUNUTYCH supliku/vysuvu (vc. boxu,
ktere na nich jedou nezvednute) a naopak (obalky vysunutych dilu proti
trojuhelnikum kridla) - dvirka, ktera se otevrou spolu s "Otevrit vse", nesmi
nic projit (dvirka_dokonci). Co omezeno, jde do varovani a ladeni.

Dorazy beznych dvirek (k=door; Robert 2026-10-02 "porad tem dvirkum chybi dorazy"):
zdrojovy model je nema (cervene dorazy ma jen podlahova dvirka), proto je modul PRIDA
jako doplnene dily (api.add_part) - DVA na dvirka, na obou koncich HORNIHO hlinikoveho
profilu kridla (nejvyssi dlouhy profil kridla: u rámu 20x20 nahore, u jednoprofiloveho
kridla ten jediny). Pravidlo z nasi sceny (shape_geometry_methods doraz_B_dvirek_fbx,
KOMPONENTY_EUROBOXY.md krok 5a, vzor product_assemblies#660) prizpusobene geometrii Vandr:
deska 75 x 20 mm (tvar doraz_dvirek.glb: 3 mm telo se sestranenymi rohy + 2 sroubove hlavy
1 mm), horni hrana v rovine horni hrany profilu, presah 10 mm pres konec profilu (smerem k
nohe), zadni plocha lezi na CELNI rovine profilu (= celni rovina nohy a rámu; v ni sedi i
pant) - deska je v hlavni vrstve pantu, tedy ZEPREDU videt. Deska je pevne spojena s KRIDLEM
(jede s dvirky): kdyby stala na rame/noze, lezela by presne v draze horniho celniho rohu
profilu (profil se pri sklapeni otaci kolem osy pantu o 8 mm pred celem) a otevreni by
zablokovala; takhle se pri otevreni od nohy odklani. Pred umistenim se deska zkontroluje
proti TROJUHELNIKUM vsech dilu v zavrene poloze (dotyk plochou smi, zanoreni nad 0,3 mm
ne): kdyz narazi (napr. horni pulka pantu u dvirek S40), zkrati se vnitrni konec (min. 50
mm), pak se snizi (min. 12 mm); kdyz ani to nestaci, na tom konci doraz neni a jde varovani.
Draha 0..uhel i kontrola proti otevrenym supliku/vysuvum pocitaji dorazy jako soucast kridla.

Ladeni: env V3D_POHYBY_LADENI=<cesta.json> zapise podrobnosti detekce
(kolejnice, klouby, osy, pivoty, kontroly boxu) - jen pro overovani.
"""
import json
import math
import os
import re

import numpy as np

VERZE = "pohyby-2026-10-02-dorazy"

VYCHOZI = {
    "suplik": {"podil": 1.0, "ms": 600, "overeno": False},
    "dvirka": {"uhel_deg": -90, "ms": 650, "overeno": False},
    "podlahova_dvirka": {"uhel_deg": -90, "ms": 700, "overeno": False},
    "pin": {"posun_mm": 16, "ms": 250, "overeno": False},
    "box_na_vysuvu": {"zdvih_mm": 60, "min_zdvih_mm": 12, "ms": 450, "overeno": False},
    "box_na_polici": {"rezerva_mm": 5, "presah_mm": 30, "zdvih_mm": 60, "ms": 450, "overeno": False},
    "typ_z_geometrie": {"povolit": True},
}

# ---------------------------------------------------------------- prahy (mm)
KOLEJ_MIN_DELKA = 300.0
KOLEJ_MAX_SIRKA = 16.0
KOLEJ_DVOJICE_DX = 15.0       # vnejsi a vnitrni kolejnice jedne strany
KOLEJ_DVOJICE_DZ = 15.0
KOLEJ_ROZDIL_VYSKY = 5.0      # vnejsi je vyssi (53/46 vs 30/24)
KOLEJ_DELKA_TOL = 3.0         # geometrie vs. Pojezdy.<delka>
PRED_KOLEJI_X = 60.0          # dily pred celem kolejnic (zamek vysuvu)
KLOUB_PRUMER = 13.0
KLOUB_TOL = 2.5
KLOUB_DELKA = (35.0, 120.0)
OSA_TOL = 1.0                 # stredy kloubu od primky
OSA_UHEL_DEG = 2.0            # primka kloubu vs. osa X komponenty
KRIDLO_Y = (-15.0, 45.0)      # predni zona kolem osy (lokalni Y)
KRIDLO_POD_OSOU = 3.0
KRIDLO_MEZERA = 8.0           # souvislost dilu kridla (zapadka 6 mm muze chybet)
PIN_ROZMER = (8.0, 8.0, 10.0)
PIN_TOL = 1.5
KNOFLIK_ROZMER = (5.0, 12.0, 12.0)
ZAPADKA_ROZMER = (6.0, 20.0, 80.0)
BOX_MIN = 60.0
BOX_PRILOHA_TOL = 2.0
KOLIZE_TOL = 0.5              # AABB se smi dotykat
DRAHA_VZORKU = 36             # kontrola drahy podlahovych dvirek (2,5 st. pri 90)
DRAHA_KROK_DEG = 2.5          # kontrola dvirek proti otevrenym supliku/vysuvum: vzorek po 2,5 st.
DVIRKA_KROK_DEG = 5.0         # omezeni uhlu dvirek po 5 st.
DVIRKA_MIN_DEG = 90.0         # nejmensi uhel dvirek (pod nej se neomezuje)
DRAHA_TOL = 0.8               # obal dilu zmenseny o tol (dotyk/koplanarni plochy nevadi)

# dorazy dvirek (mm)
DORAZ_DELKA = 75.0            # delka desky podel profilu (doraz_dvirek.glb 4 x 75 x 20)
DORAZ_VYSKA = 20.0
DORAZ_TELO = 3.0              # tloustka desky; sroubove hlavy 1 mm navic = 4 mm celkem
DORAZ_HLAVA_V = 1.0
DORAZ_HLAVA_R1 = 6.0          # sroubova hlava: zakladna 6 mm polomer, vrsek 3 mm
DORAZ_HLAVA_R2 = 3.0
DORAZ_HLAVA_OD_KONCE = 15.0   # stred hlavy od konce desky (doraz_dvirek.glb: +-22,5 od stredu)
DORAZ_SESTRANENI = 2.0
DORAZ_PRESAH = 10.0           # presah pres konec profilu (smerem k nohe)
DORAZ_DELKA_MIN = 50.0
DORAZ_PRESAH_MIN = 3.0        # nejmensi presah pres konec profilu pri zkraceni vnejsiho konce
DORAZ_VYSKY = (20.0, 16.0, 12.0)
DORAZ_TOL = 0.3               # zanoreni do jineho dilu: dotyk plochou smi, nad 0,3 mm ne
DORAZ_MEZERA = 0.2            # mezera pri zkraceni vnitrniho konce
DORAZ_SEGMENTU = 12           # sroubova hlava (kuzel)

POJEZD_RE = re.compile(r"^pojezdy\.(?:[a-z_]+\.)*?(\d{3,4})(?:\.|$)", re.I)
PANT_RE = re.compile(r"^pant[_.]", re.I)
ZAPADKA_RE = re.compile(r"^(zapadka|zamek)", re.I)
KLUZ_RE = re.compile(r"^kluzny_sroub", re.I)
BOX_RE = re.compile(r"^(box\.klt|box\.grey|multibox)\b", re.I)
BOX_KUSOVNIK_SUB = {"box.klt": "klt", "box.grey": "eurobox", "multibox": "multibox"}
SUB_ROLE = {"blueklt": "klt", "multiboxarc": "multibox", "darkgreybin": "eurobox"}     # role skorepiny boxu
SUB_RODINA = {"multibox": "multibox", "box tmava": "eurobox"}                          # slabsi (jen kdyz role nic nerekne)
SUB_TYP = (("multibox", "multibox"), ("eurobox", "eurobox"), ("kufrik", "kufrik"), ("klt", "klt"))  # klic v unity_id
NOSNIK_RE = re.compile(r"^(r?45x45|sl_?40x40)", re.I)
POHYBLIVY_TYP_RE = re.compile(r"door|suplik|vysuv|kufrik|box", re.I)
STRANA_PORADI = {"left": 0, "bulkhead": 1, "right": 2}


# ================================================================ pomocne
def _norm(v):
    v = np.asarray(v, dtype=np.float64)
    n = float(np.linalg.norm(v))
    return v / n if n > 1e-12 else v


def _r(x, nd=1):
    return round(float(x), nd) + 0.0


def _v(v, nd=3):
    return [_r(c, nd) for c in v]


def _rozmer_ok(sz, vzor, tol):
    return all(abs(a - b) <= tol for a, b in zip(sorted(sz), sorted(vzor)))


def _mezera(amn, amx, bmn, bmx):
    """Nejvetsi mezera mezi dvema AABB pres osy (<= 0 = dotyk/prunik)."""
    return float(max(np.max(bmn - amx), np.max(amn - bmx)))


def _prunik(amn, amx, bmn, bmx, tol=KOLIZE_TOL):
    """AABB se protinaji ve vsech 3 osach (o vic nez tol)."""
    return bool(np.all(np.minimum(amx, bmx) - np.maximum(amn, bmn) > tol))


def _rodrigues(v, k, uhel):
    k = _norm(k)
    c, s = math.cos(uhel), math.sin(uhel)
    return v * c + np.cross(k, v) * s + k * float(np.dot(k, v)) * (1.0 - c)


def _rot_body(V, P, k, uhel):
    """Otoceni bodu V (N,3) kolem primky (P, k) o uhel (rad, pravotocive)."""
    k = _norm(k)
    c, s = math.cos(uhel), math.sin(uhel)
    W = np.asarray(V, dtype=np.float64) - P
    return P + W * c + np.cross(k, W) * s + np.outer(W @ k, k) * (1.0 - c)


def _tri_box(T, lo, hi):
    """SAT test trojuhelniku (N,3,3) proti AABB [lo, hi]; vraci bool (N,)."""
    c = (lo + hi) / 2.0
    h = (hi - lo) / 2.0
    v = T - c
    ok = np.all((v.min(axis=1) <= h) & (v.max(axis=1) >= -h), axis=1)
    if not ok.any():
        return ok
    idx = np.nonzero(ok)[0]
    vv = v[idx]
    e = [vv[:, 1] - vv[:, 0], vv[:, 2] - vv[:, 1], vv[:, 0] - vv[:, 2]]
    n = np.cross(e[0], e[1])
    res = np.abs(np.einsum("ij,ij->i", n, vv[:, 0])) <= np.abs(n) @ h + 1e-9
    for ei in e:
        for a in np.eye(3):
            ax = np.cross(np.broadcast_to(a, ei.shape), ei)
            p = np.einsum("nkj,nj->nk", vv, ax)
            r = np.abs(ax) @ h
            res &= ~((p.min(axis=1) > r + 1e-9) | (p.max(axis=1) < -r - 1e-9))
    out = np.zeros(len(T), dtype=bool)
    out[idx] = res
    return out


def _doraz_mesh(xa, xb, za, zb, y_zad):
    """Doraz dvirek v LOKALNIM ramu komponenty (X podel profilu, -Y = celo, Z nahoru), mm:
    deska xa..xb x za..zb, zadni plocha v Y = y_zad (lezi na celni rovine profilu), telo
    DORAZ_TELO smerem k celu (-Y), na vnejsi plose 2 sroubove hlavy (kuzel DORAZ_HLAVA_V).
    -> (verts (N,3), tris (M,3)) s vnejsi normalou v lokalnim ramu."""
    c = min(DORAZ_SESTRANENI, (xb - xa) / 4.0, (zb - za) / 4.0)
    obrys = [(xa + c, za), (xb - c, za), (xb, za + c), (xb, zb - c), (xb - c, zb), (xa + c, zb), (xa, zb - c), (xa, za + c)]
    y_cel = y_zad - DORAZ_TELO
    V, T = [], []

    def orientuj(idx_tri, stred):
        out = []
        for a, b, cc in idx_tri:
            n = np.cross(V[b] - V[a], V[cc] - V[a])
            t = (V[a] + V[b] + V[cc]) / 3.0
            out.append((a, b, cc) if float(np.dot(n, t - stred)) >= 0 else (a, cc, b))
        return out

    def prsten(z_y):
        i0 = len(V)
        for x, z in obrys:
            V.append(np.array([x, z_y, z]))
        return list(range(i0, i0 + len(obrys)))
    zad, cel = prsten(y_zad), prsten(y_cel)
    tri = []
    for i in range(1, len(obrys) - 1):
        tri.append((cel[0], cel[i], cel[i + 1]))
        tri.append((zad[0], zad[i], zad[i + 1]))
    for i in range(len(obrys)):
        j = (i + 1) % len(obrys)
        tri += [(zad[i], zad[j], cel[j]), (zad[i], cel[j], cel[i])]
    T += orientuj(tri, np.array([(xa + xb) / 2.0, (y_zad + y_cel) / 2.0, (za + zb) / 2.0]))
    if (zb - za) >= 2 * DORAZ_HLAVA_R1 and (xb - xa) >= 2 * DORAZ_HLAVA_OD_KONCE:
        zc = (za + zb) / 2.0
        for xc in (xa + DORAZ_HLAVA_OD_KONCE, xb - DORAZ_HLAVA_OD_KONCE):
            sp, ho = [], []
            for i in range(DORAZ_SEGMENTU):
                a = 2.0 * math.pi * i / DORAZ_SEGMENTU
                sp.append(len(V))
                V.append(np.array([xc + DORAZ_HLAVA_R1 * math.cos(a), y_cel, zc + DORAZ_HLAVA_R1 * math.sin(a)]))
            for i in range(DORAZ_SEGMENTU):
                a = 2.0 * math.pi * i / DORAZ_SEGMENTU
                ho.append(len(V))
                V.append(np.array([xc + DORAZ_HLAVA_R2 * math.cos(a), y_cel - DORAZ_HLAVA_V, zc + DORAZ_HLAVA_R2 * math.sin(a)]))
            tri = []
            for i in range(DORAZ_SEGMENTU):
                j = (i + 1) % DORAZ_SEGMENTU
                tri += [(sp[i], sp[j], ho[j]), (sp[i], ho[j], ho[i])]
            for i in range(1, DORAZ_SEGMENTU - 1):
                tri.append((ho[0], ho[i], ho[i + 1]))
            T += orientuj(tri, np.array([xc, y_cel - DORAZ_HLAVA_V * 0.25, zc]))
    return np.array(V), np.array(T, dtype=np.int64)


class Ram:
    """Lokalni ram komponenty ve svetovych mm (osy normalizovane - pripadne
    meritko komponenty se do rozmeru nepromita). L = (V - O) @ R.T."""

    def __init__(self, api, obj):
        M = np.array(obj.matrix_world, dtype=np.float64)
        self.O = np.array(api.to_gltf(M[:3, 3]))
        osy = [np.array(api.to_gltf(M[:3, :3] @ np.array(v, dtype=np.float64)))
               for v in ((1.0, 0, 0), (0, 0, 1.0), (0, -1.0, 0))]   # glTF lokal X, +Y, +Z
        self.meritko = [float(np.linalg.norm(o)) for o in osy]
        self.ok = min(self.meritko) > 1e-9
        if self.ok:
            osy = [o / n for o, n in zip(osy, self.meritko)]
            self.ok = all(abs(float(np.dot(osy[i], osy[j]))) < 1e-3 for i, j in ((0, 1), (0, 2), (1, 2)))
        self.R = np.stack(osy)
        self.front = -self.R[1]           # lokalni -Y = celo (svet)
        self.up = self.R[2]

    def lok(self, V):
        return (np.asarray(V, dtype=np.float64) - self.O) @ self.R.T

    def bod(self, p):
        return self.O + np.asarray(p, dtype=np.float64) @ self.R

    def smer(self, v):
        return np.asarray(v, dtype=np.float64) @ self.R

    def aabb_svet(self, mn, mx):
        """Lokalni AABB -> svetovy AABB (8 rohu)."""
        rohy = np.array([[mx[0] if c & 1 else mn[0], mx[1] if c & 2 else mn[1], mx[2] if c & 4 else mn[2]]
                         for c in range(8)])
        W = self.bod(rohy)
        return W.min(axis=0), W.max(axis=0)

    def aabb_lok(self, mn, mx):
        """Svetovy AABB -> lokalni AABB (8 rohu, konzervativne)."""
        rohy = np.array([[mx[0] if c & 1 else mn[0], mx[1] if c & 2 else mn[1], mx[2] if c & 4 else mn[2]]
                         for c in range(8)])
        L = self.lok(rohy)
        return L.min(axis=0), L.max(axis=0)


class Dil:
    """Jeden mesh komponenty v lokalnim ramu."""

    def __init__(self, api, ram, o):
        self.o = o
        self.jm = o.name
        self.jml = re.sub(r"\.\d{3}$", "", o.name).lower()
        self.V = api.verts(o)
        L = ram.lok(self.V) if len(self.V) else np.zeros((1, 3))
        self.mn = L.min(axis=0)
        self.mx = L.max(axis=0)
        self.c = (self.mn + self.mx) / 2.0
        self.sz = self.mx - self.mn
        inf = api.info(o) or {}
        self.role = (inf.get("role") or "").lower()
        self.rod = [(r or "").lower() for r in (inf.get("rodiny") or [])]

    @property
    def chrom(self):
        return self.role == "sroub" or any("chrom" in r for r in self.rod)

    @property
    def cerny(self):
        return self.role == "black" or any(r == "black" for r in self.rod)

    @property
    def modry(self):
        return self.role in ("blueklt", "blue") or any(r == "blue klt" for r in self.rod)

    @property
    def box_mat(self):
        return self.role in ("blueklt", "multiboxarc", "darkgreybin") or \
            any(r in ("blue klt", "box tmava", "multibox") for r in self.rod)

    @property
    def nosnik(self):
        return bool(NOSNIK_RE.match(self.jml))


# ================================================================== stav
class Detekce:
    def __init__(self, api):
        self.api = api
        self.ctx = api.ctx if isinstance(getattr(api, "ctx", None), dict) else {}
        self.warnings = []
        self.pivots = []          # poradi = rodic pred potomkem
        self.motions = []         # [(klic_razeni, druh, motion bez n)]
        self.boxy = []            # cekajici boxy (kontrola az nakonec)
        self.typove = {}          # (unity_id, text) -> pocet kusu
        self.ladeni = {"verze": VERZE, "komponenty": []}
        self.pocty = {"supliky": 0, "vysuvy": 0, "dvirka": 0, "podlahova_dvirka": 0, "piny": 0, "boxy": 0,
                      "panty_rozriznute": 0, "staticke_komponenty": 0, "dorazy_dvirek": 0}
        self._id = 0
        self.pin_pouzit = False
        self.box_polici_pouzit = False
        self.dvere = []           # sklopna dvirka cekajici na kontrolu proti otevrenym supliku/vysuvum
        self.pridane = []         # doplnene dily (dorazy dvirek) - pri selhani komponenty se rusi
        self.dorazy_info = []     # [{pivot, komponenta, dorazy: [...]}] pro geom.json
        self.cfg = self._konfigurace()
        self._rec_uid = {}
        for k in self.ctx.get("komponenty") or []:
            if isinstance(k, dict) and k.get("unity_id"):
                self._rec_uid[k["unity_id"]] = k
        self._instance = []
        for i in self.ctx.get("instance") or []:
            p = i.get("pozice") if isinstance(i, dict) else None
            if isinstance(p, list) and len(p) == 3 and all(isinstance(c, (int, float)) for c in p):
                self._instance.append((np.array([-p[0] * 1000.0, p[1] * 1000.0, p[2] * 1000.0]), i))
        # sloupce = dvojice noh (rodic komponenty), pro cislovani
        self._sloupec = {}
        sk = {}
        for k in api.components:
            par = k["obj"].parent.name if k["obj"].parent is not None else ""
            sk.setdefault((k["side"], par), []).append(np.array(api.to_gltf(np.array(k["obj"].matrix_world)[:3, 3])))
        for key, body in sk.items():
            self._sloupec[key] = np.mean(body, axis=0)

    # ---------------------------------------------------------- obecne
    def warn(self, text):
        if text not in self.warnings:
            self.warnings.append(text)

    def warn_typ(self, uid, text):
        """Varovani za typ komponenty (stejna vec u vice kusu = 1 radek)."""
        self.typove[(uid, text)] = self.typove.get((uid, text), 0) + 1

    def nove_id(self, pref):
        self._id += 1
        return "%s%d" % (pref, self._id)

    def _konfigurace(self):
        raw = self.ctx.get("pohyby_vychozi")
        if not isinstance(raw, dict):
            self.warn("pohyby: ctx nema pohyby-vychozi.json - pouzity vestavene vychozi hodnoty modulu")
            raw = {}
        cfg = {}
        for sekce, vych in VYCHOZI.items():
            s = dict(vych)
            src = raw.get(sekce)
            if isinstance(src, dict):
                for kl, hod in src.items():
                    if kl.startswith("_"):
                        continue
                    if kl in vych and isinstance(vych[kl], bool):
                        s[kl] = bool(hod)
                    elif kl in vych and isinstance(hod, (int, float)) and not isinstance(hod, bool) and math.isfinite(hod):
                        s[kl] = float(hod)
            cfg[sekce] = s
        return cfg

    def _ms(self, sekce):
        return int(max(1, min(10000, round(self.cfg[sekce]["ms"]))))

    def zaznam(self, k):
        """Zaznam ctx.komponenty pro uzel komponenty: nejdriv podle pozice
        (stored_model_parts.data, do 5 mm), jinak jednoznacne podle klice."""
        o = k["obj"]
        P = np.array(self.api.to_gltf(np.array(o.matrix_world)[:3, 3]))
        uid = None
        if self._instance:
            d, inst = min(((float(np.linalg.norm(p - P)), i) for p, i in self._instance), key=lambda t: t[0])
            if d < 5.0:
                uid = inst.get("unity_id")
                if inst.get("klic") and inst.get("klic") != k["key"]:
                    self.warn("%s: uzel modelu (%s) a komponenta na stejne pozici se neshoduji - pouzita pozice"
                              % (uid, k["key"]))
        if uid is None:
            kand = [r for r in self._rec_uid.values() if r.get("klic") == k["key"]]
            if len(kand) == 1:
                uid = kand[0]["unity_id"]
            elif len(kand) > 1:
                return None, None
        if uid is None:
            return None, None
        return self._rec_uid.get(uid), uid

    @staticmethod
    def kusovnik(rec):
        kus = {"pojezdy": [], "pant": 0, "zapadka": 0, "kluz": 0, "boxy": 0, "box_typy": set()}
        for d in rec.get("dily") or []:
            u = str(d.get("unity_id") or "")
            n = int(d.get("pocet") or 0)
            m = POJEZD_RE.match(u)
            if m:
                kus["pojezdy"].append((float(m.group(1)), n, u))
            elif PANT_RE.match(u):
                kus["pant"] += n
            elif ZAPADKA_RE.match(u):
                kus["zapadka"] += n
            elif KLUZ_RE.match(u):
                kus["kluz"] += n
            elif BOX_RE.match(u):
                kus["boxy"] += n
                kus["box_typy"].add(BOX_KUSOVNIK_SUB[BOX_RE.match(u).group(1).lower()])
        return kus

    def razeni(self, k, ram, bod):
        """Klic pro cislovani: strana, sloupec zleva doprava, shora dolu,
        zleva doprava (z pohledu pred touto stranou)."""
        par = k["obj"].parent.name if k["obj"].parent is not None else ""
        vpravo = np.cross(-ram.front, np.array([0.0, 1.0, 0.0]))
        sl = self._sloupec.get((k["side"], par), ram.O)
        return (STRANA_PORADI.get(k["side"], 3), round(float(np.dot(sl, vpravo)) / 10.0),
                -round(float(bod[1]) / 5.0), round(float(np.dot(bod, vpravo)), 1))

    @staticmethod
    def _stred(dily):
        mn = np.min([d.mn for d in dily], axis=0)
        mx = np.max([d.mx for d in dily], axis=0)
        return (mn + mx) / 2.0, mn, mx

    # --------------------------------------------------- druh boxu
    def sub_boxu(self, uid, kus, skorepina):
        """Druh boxu -> (sub | None, zdroje). Vsechny zdroje, ktere neco rekly, se musi shodovat."""
        z = {}
        mat = SUB_ROLE.get(skorepina.role)
        if mat is None:
            mat = next((SUB_RODINA[r] for r in skorepina.rod if r in SUB_RODINA), None)
        z["material"] = [skorepina.role, mat]
        bom = sorted(kus["box_typy"])
        z["kusovnik"] = bom
        typ = next((v for kl, v in SUB_TYP if kl in (uid or "").lower()), None)
        z["typ_komponenty"] = typ
        kand = {x for x in (mat, bom[0] if len(bom) == 1 else None, typ) if x}
        if len(kand) == 1:
            return next(iter(kand)), z
        self.warn_typ(uid or "?", "druh boxu nelze urcit (%s) - chip se jmenuje jen 'Box N'" % (
            "zdroje se nesouhlasi: material %s, kusovnik %s, typ %s" % (mat, bom, typ) if kand
            else "zadny zdroj (role %s)" % skorepina.role))
        return None, z

    # ------------------------------------------------------- komponenta
    def komponenta(self, k):
        api = self.api
        produkt_jm = set(o.name for o in api.produkt)
        meshes = [o for o in k["meshes"] if o.name in produkt_jm]
        if not meshes:
            return
        rec, uid = self.zaznam(k)
        ram = Ram(api, k["obj"])
        popis = "%s (%s, vyska %d mm)" % (uid or k["name"], k["side"] or "?", round(float(ram.O[1])))
        lad = {"komponenta": popis, "uzel": k["name"]}
        self.ladeni["komponenty"].append(lad)
        if rec is None:
            if POHYBLIVY_TYP_RE.search(k["key"]):
                self.warn("%s: komponentu nelze sparovat s kusovnikem (ctx) - zustava staticka" % popis)
                self.pocty["staticke_komponenty"] += 1
            return
        kus = self.kusovnik(rec)
        lad["kusovnik"] = {"pojezdy": [p[2] + " x%d" % p[1] for p in kus["pojezdy"]], "pant": kus["pant"],
                           "zapadka": kus["zapadka"], "kluz": kus["kluz"], "boxy": kus["boxy"]}
        if not (kus["pojezdy"] or kus["pant"] or kus["kluz"] or kus["boxy"] or "door" in uid.lower()):
            return
        if not ram.ok:
            self.warn("%s: matice komponenty neni ortogonalni - zustava staticka" % popis)
            self.pocty["staticke_komponenty"] += 1
            return
        D = [Dil(api, ram, o) for o in meshes]
        supliky = []
        if kus["pojezdy"]:
            supliky = self.supliky(k, popis, uid, ram, D, kus, lad)
        dvere = bool(kus["pant"] or kus["kluz"])
        z_geometrie = False
        if not dvere and "door" in uid.lower() and self.cfg["typ_z_geometrie"]["povolit"] \
                and any(PANT_RE.match(d.jml) for d in D):
            dvere, z_geometrie = True, True
        if dvere:
            self.dvirka(k, popis, uid, ram, D, kus, lad, z_geometrie)
        if kus["boxy"]:
            self.najdi_boxy(k, popis, uid, ram, D, kus, supliky, lad)

    # ---------------------------------------------------------- supliky
    def supliky(self, k, popis, uid, ram, D, kus, lad):
        koleje = [d for d in D if d.chrom and d.sz[1] > KOLEJ_MIN_DELKA and d.sz[0] < KOLEJ_MAX_SIRKA]
        if not koleje:
            self.warn("%s: kusovnik uvadi pojezdy, v modelu kolejnice nejsou - zustava staticka" % popis)
            self.pocty["staticke_komponenty"] += 1
            return []
        koleje.sort(key=lambda d: (round(float(d.c[2])), float(d.c[0]), d.jm))
        pouzite, strany = set(), []
        for i, a in enumerate(koleje):
            if i in pouzite:
                continue
            nej = None
            for j, b in enumerate(koleje):
                if j == i or j in pouzite:
                    continue
                dx, dz = abs(a.c[0] - b.c[0]), abs(a.c[2] - b.c[2])
                if dx < KOLEJ_DVOJICE_DX and dz < KOLEJ_DVOJICE_DZ and abs(a.sz[2] - b.sz[2]) > KOLEJ_ROZDIL_VYSKY:
                    if nej is None or dx < nej[0]:
                        nej = (dx, j)
            if nej is None:
                continue
            pouzite |= {i, nej[1]}
            b = koleje[nej[1]]
            strany.append((a, b) if a.sz[2] > b.sz[2] else (b, a))     # (vnejsi pevna, vnitrni jede)
        lad["kolejnice"] = [{"vnejsi": [s[0].jm, _v(s[0].mn, 1), _v(s[0].mx, 1)],
                             "vnitrni": [s[1].jm, _v(s[1].mn, 1), _v(s[1].mx, 1)]} for s in strany]
        if len(pouzite) != len(koleje):
            self.warn("%s: kolejnice nejdou sparovat (vnejsi + vnitrni) - zustava staticka" % popis)
            self.pocty["staticke_komponenty"] += 1
            return []
        urovne = []
        for s in strany:
            for u in urovne:
                if abs(u[0].c[2] - s[0].c[2]) < KOLEJ_DVOJICE_DZ:
                    break
            else:
                urovne.append(s)
        if len(urovne) > 1:
            self.warn("%s: kolejnice ve vice vyskach v jedne komponente - zustava staticka" % popis)
            self.pocty["staticke_komponenty"] += 1
            return []
        strany.sort(key=lambda s: float(s[0].c[0]))
        if len(strany) % 2:
            self.warn("%s: lichy pocet stran kolejnic (%d) - zustava staticka" % (popis, len(strany)))
            self.pocty["staticke_komponenty"] += 1
            return []
        pary = [(strany[i], strany[i + 1]) for i in range(0, len(strany), 2)]
        for L, R in pary:
            if not (L[1].c[0] > L[0].c[0] and R[1].c[0] < R[0].c[0]):
                self.warn("%s: vnitrni kolejnice nejsou na strane supliku - zustava staticka" % popis)
                self.pocty["staticke_komponenty"] += 1
                return []
        n_kus = sum(p[1] for p in kus["pojezdy"])
        if n_kus != len(pary):
            lad["info_pocet"] = "kusovnik %d paru pojezdu, model %d - animovano podle modelu" % (n_kus, len(pary))
        druh = "slide" if (uid.lower().startswith("vysuv") or ".vysuv" in uid.lower()) else "drawer"
        if kus["zapadka"]:
            self.warn_typ(uid, "zamek/zapadka vysuvu z kusovniku nema pravidlo v modelu - vysouva se bez predkroku "
                               "odjisteni (dily zamku jedou s vysuvem)")
        pevne = set(id(s[0]) for s in strany)
        vysledek = []
        prirazene = set()
        for L, R in pary:
            delka = (L[1].sz[1] + R[1].sz[1]) / 2.0
            shoda = [p for p in kus["pojezdy"] if abs(p[0] - delka) <= KOLEJ_DELKA_TOL]
            if not shoda or abs(L[1].sz[1] - R[1].sz[1]) > KOLEJ_DELKA_TOL:
                self.warn("%s: delka kolejnice %.0f mm nesouhlasi s kusovnikem (%s) - suplik zustava staticky"
                          % (popis, delka, ", ".join(p[2] for p in kus["pojezdy"])))
                self.pocty["staticke_komponenty"] += 1
                continue
            draha = shoda[0][0] * self.cfg["suplik"]["podil"]
            x0, x1 = float(L[0].c[0]), float(R[0].c[0])
            celo_kolej = float(min(L[0].mn[1], R[0].mn[1]))
            jede = []
            for d in D:
                if id(d) in pevne or id(d) in prirazene or d.nosnik:
                    continue
                uvnitr = x0 < d.c[0] < x1
                pred = d.mx[1] <= celo_kolej + 2.0 and d.mx[0] > x0 - PRED_KOLEJI_X and d.mn[0] < x1 + PRED_KOLEJI_X
                if uvnitr or pred:
                    jede.append(d)
            if L[1] not in jede or R[1] not in jede:
                self.warn("%s: vnitrni kolejnice nejsou mezi pohyblivymi dily - suplik zustava staticky" % popis)
                continue
            for d in jede:
                prirazene.add(id(d))
            zac = ram.bod(np.array([(x0 + x1) / 2.0, celo_kolej, float((L[0].c[2] + R[0].c[2]) / 2.0)]))
            pid = self.nove_id("s")
            piv = {"id": pid, "origin": _v(zac), "parent": None, "objects": [d.jm for d in jede]}
            self.pivots.append(piv)
            stred, mn, mx = self._stred(jede)
            mot = {"k": druh, "steps": [{"p": pid, "op": "T", "ax": _v(_norm(ram.front), 6), "v": _r(draha, 1),
                                         "ms": self._ms("suplik")}], "pick": [pid]}
            self.motions.append((self.razeni(k, ram, ram.bod(stred)), druh, mot))
            self.pocty["vysuvy" if druh == "slide" else "supliky"] += 1
            sp = {"pid": pid, "piv": piv, "jede": jede, "draha": draha, "ram": ram, "druh": druh}
            vysledek.append(sp)
            lad.setdefault("supliky", []).append({
                "pivot": pid, "druh": druh, "delka_kolejnice_mm": _r(delka, 1), "kusovnik": shoda[0][2],
                "draha_mm": _r(draha, 1), "pocet_dilu": len(jede), "origin": _v(zac, 1),
                "pevne": [L[0].jm, R[0].jm], "vnitrni": [L[1].jm, R[1].jm]})
        return vysledek

    # ------------------------------------------------- dorazy dvirek
    def _doraz_zasahy(self, ram, lo, hi):
        """Trojuhelniky VSECH dilu produktu, ktere se zanorily do lokalniho kvadru [lo, hi]
        (zmenseny o DORAZ_TOL - dotyk plochou je v poradku) -> [(jmeno dilu, min x, max x, pocet)]
        (x = lokalni X zasahujicich trojuhelniku)."""
        api = self.api
        lo_s, hi_s = lo + DORAZ_TOL, hi - DORAZ_TOL
        out = []
        if np.any(hi_s <= lo_s):
            return out
        for o in api.produkt:
            mn, mx = (np.array(c, dtype=np.float64) for c in api.aabb(o))
            lmn, lmx = ram.aabb_lok(mn, mx)
            if np.any(lmx < lo - 1.0) or np.any(lmn > hi + 1.0):
                continue
            T = api.tris(o)
            if not len(T):
                continue
            Tl = ram.lok(T.reshape(-1, 3)).reshape(-1, 3, 3)
            h = _tri_box(Tl, lo_s, hi_s)
            if h.any():
                X = Tl[h][:, :, 0]
                out.append((o.name, float(X.min()), float(X.max()), int(h.sum())))
        return out

    def _doraz_umisti(self, ram, konec, xe, y_cel, z_top):
        """Umisteni jednoho dorazu na konci profilu (konec "min" | "max" v lokalni X, xe = X konce
        profilu): nominalne DORAZ_DELKA x DORAZ_VYSKA, presah DORAZ_PRESAH pres konec, horni hrana
        v z_top, zadni plocha v y_cel. Kdyz deska zanori do jineho dilu, zkrati se konec na strane
        prekazky: vnitrni (prekazka uvnitr, napr. horni pulka pantu), nebo vnejsi - presah se
        zmensi (nejmene DORAZ_PRESAH_MIN, napr. celni plech vysuvu na noze); delka nejmene
        DORAZ_DELKA_MIN. Pak se snizi (DORAZ_VYSKY). -> ((xa, xb, za, zb, uprava), []) |
        (None, zbyle zasahy)."""
        znam = 1.0 if konec == "max" else -1.0
        zasahy = []
        for vyska in DORAZ_VYSKY:
            za, zb = z_top - vyska, z_top
            # souradnice podel profilu: vnitrni konec a vnejsi konec (vnejsi = dal od stredu profilu)
            vnejsi = xe + znam * DORAZ_PRESAH
            vnitrni = vnejsi - znam * DORAZ_DELKA
            for _pokus in range(6):
                xa, xb = (vnitrni, vnejsi) if konec == "max" else (vnejsi, vnitrni)
                lo = np.array([xa, y_cel - DORAZ_TELO - DORAZ_HLAVA_V, za])
                hi = np.array([xb, y_cel, zb])
                zasahy = self._doraz_zasahy(ram, lo, hi)
                if not zasahy:
                    upr = []
                    if abs(xb - xa) < DORAZ_DELKA - 0.05:
                        upr.append("zkraceno na %.1f mm" % abs(xb - xa))
                    if abs((vnejsi - xe) * znam) < DORAZ_PRESAH - 0.05:
                        upr.append("presah pres konec profilu %.1f mm" % abs((vnejsi - xe) * znam))
                    if vyska < DORAZ_VYSKA - 0.05:
                        upr.append("snizeno na %.0f mm" % vyska)
                    return (xa, xb, za, zb, upr), []
                stred = (xa + xb) / 2.0
                # prekazka na strane k stredu profilu (vnitrni) / na strane od stredu (vnejsi)
                uvnitr = [z for z in zasahy if (z[2] <= stred if konec == "max" else z[1] >= stred)]
                venku = [z for z in zasahy if (z[1] >= stred if konec == "max" else z[2] <= stred)]
                zmena = False
                if uvnitr:
                    novy = (max(z[2] for z in uvnitr) + DORAZ_MEZERA) if konec == "max" else (min(z[1] for z in uvnitr) - DORAZ_MEZERA)
                    if abs(vnejsi - novy) >= DORAZ_DELKA_MIN and abs(novy - vnitrni) > 1e-6:
                        vnitrni, zmena = novy, True
                if venku:
                    novy = (min(z[1] for z in venku) - DORAZ_MEZERA) if konec == "max" else (max(z[2] for z in venku) + DORAZ_MEZERA)
                    if abs(novy - vnitrni) >= DORAZ_DELKA_MIN and (novy - xe) * znam >= DORAZ_PRESAH_MIN \
                            and abs(novy - vnejsi) > 1e-6:
                        vnejsi, zmena = novy, True
                if not zmena:
                    break
        return None, zasahy

    def dorazy_dvirek(self, popis, ram, kridlo, lad):
        """Dva dorazy bezneho dvirka (viz hlavicka modulu) -> [Dil], zaznamy do self.dorazy_info
        (zatim bez cisla dvirek - doplni se ve vysledek()). Selze-li jeden konec, deska na nem
        neni a jde varovani; bez hlinikoveho profilu kridla nic."""
        api = self.api
        if not hasattr(api, "add_part"):
            return [], []
        sirka = max(float(d.sz[0]) for d in kridlo)
        profily = [d for d in kridlo if d.role == "alu" and float(d.sz[0]) >= 0.8 * sirka]
        if not profily:
            self.warn("%s: kridlo dvirek nema hlinikovy profil - bez dorazu" % popis)
            return [], []
        horni = max(profily, key=lambda d: (round(float(d.mx[2]), 1), float(d.sz[0]), d.jm))
        y_cel = float(horni.mn[1])          # celni rovina profilu (= celo noh a rámu, v ni sedi pant)
        z_top = float(horni.mx[2])
        if float(horni.sz[2]) < DORAZ_VYSKA - 0.5:
            self.warn("%s: horni profil kridla je nizsi nez %.0f mm - bez dorazu" % (popis, DORAZ_VYSKA))
            return [], []
        vysledek, zaznamy = [], []
        lad_d = lad.setdefault("dorazy", [])
        for konec, xe in (("min", float(horni.mn[0])), ("max", float(horni.mx[0]))):
            res, zasahy = self._doraz_umisti(ram, konec, xe, y_cel, z_top)
            if res is None:
                self.warn_typ(popis.split(" (")[0], "doraz dvirek na konci '%s' nelze umistit bez zanoreni (%s) - na tomto konci "
                                                   "bez dorazu" % (konec, ", ".join(z[0][:14] for z in zasahy[:3])))
                lad_d.append({"konec": konec, "chyba": [list(z) for z in zasahy[:5]]})
                continue
            xa, xb, za, zb, upr = res
            V, T = _doraz_mesh(xa, xb, za, zb, y_cel)
            W = ram.bod(V)
            if float(np.linalg.det(ram.R)) < 0:
                T = T[:, [0, 2, 1]]
            ob = api.add_part("doraz_%s_%d" % (konec, len(self.pridane)), W, T)
            self.pridane.append(ob)
            dil = Dil(api, ram, ob)
            vysledek.append(dil)
            wmn, wmx = (np.array(c, dtype=np.float64) for c in api.aabb(ob))
            z_ = {"konec": konec, "lok_mn": _v(dil.mn, 2), "lok_mx": _v(dil.mx, 2), "svet_mn": _v(wmn, 2), "svet_mx": _v(wmx, 2),
                  "delka_mm": _r(xb - xa, 1), "vyska_mm": _r(zb - za, 1), "tloustka_mm": _r(DORAZ_TELO + DORAZ_HLAVA_V, 1),
                  "presah_pres_konec_profilu_mm": _r(abs((xb if konec == "max" else xa) - xe), 1), "uprava": upr, "trojuhelniku": int(len(T)),
                  "celo_svet": _v(ram.front, 4),
                  "na_profilu": horni.jm}
            zaznamy.append(z_)
            lad_d.append(z_)
        self.pocty["dorazy_dvirek"] += len(vysledek)
        return vysledek, zaznamy

    # ----------------------------------------------------------- dvirka
    def dvirka(self, k, popis, uid, ram, D, kus, lad, z_geometrie):
        api = self.api
        podlahova = bool(kus["kluz"])
        sekce = "podlahova_dvirka" if podlahova else "dvirka"
        if podlahova:
            osa_dily = [d for d in D if "kluz" in d.jml]
        else:
            osa_dily = [d for d in D if d.cerny and abs(sorted(d.sz)[0] - KLOUB_PRUMER) <= KLOUB_TOL
                        and abs(sorted(d.sz)[1] - KLOUB_PRUMER) <= KLOUB_TOL
                        and KLOUB_DELKA[0] <= d.sz[0] <= KLOUB_DELKA[1]]
        if len(osa_dily) < 2:
            self.warn("%s: osa dvirek nenalezena (%s: %d) - zustava staticka"
                      % (popis, "kluzne srouby" if podlahova else "klouby pantu", len(osa_dily)))
            self.pocty["staticke_komponenty"] += 1
            return
        C = np.array([d.c for d in osa_dily])
        P0 = C.mean(axis=0)
        _u, _s, Vt = np.linalg.svd(C - P0)
        smer = Vt[0] if Vt[0][0] >= 0 else -Vt[0]
        odchylka = float(np.max(np.linalg.norm(np.cross(C - P0, smer), axis=1)))
        lad["osa"] = {"dily": [d.jm for d in osa_dily], "stredy": [_v(c, 2) for c in C], "smer_lok": _v(smer, 6),
                      "odchylka_mm": _r(odchylka, 3)}
        if smer[0] < math.cos(math.radians(OSA_UHEL_DEG)):
            self.warn("%s: osa dvirek neni rovnobezna s osou komponenty - zustava staticka" % popis)
            self.pocty["staticke_komponenty"] += 1
            return
        if odchylka > OSA_TOL:
            self.warn("%s: stredy kloubu nelezi na jedne primce (%.1f mm) - zustava staticka" % (popis, odchylka))
            self.pocty["staticke_komponenty"] += 1
            return
        ay, az = float(P0[1]), float(P0[2])
        osa_id = set(id(d) for d in osa_dily)
        rozpeti = float(C[:, 0].max() - C[:, 0].min())
        # podlahova dvirka: osa uvnitr prurezu nosneho profilu = otaci se cely ram
        nosic = None
        if podlahova:
            nos = [d for d in D if id(d) not in osa_id and d.nosnik and d.mn[1] < ay < d.mx[1]
                   and d.mn[2] < az < d.mx[2] and d.sz[0] >= 0.5 * rozpeti]
            if nos:
                nosic = max(nos, key=lambda d: (float(d.sz[0]), d.jm))
        panty = []
        if nosic is not None:
            kridlo = [d for d in D if id(d) not in osa_id]
        else:
            kand = []
            for d in D:
                if id(d) in osa_id or d.nosnik:
                    continue
                if d.mn[1] < ay + KRIDLO_Y[0] or d.mx[1] > ay + KRIDLO_Y[1]:
                    continue
                if PANT_RE.match(d.jml) and d.mn[2] < az - 1.0 and d.mx[2] > az + 1.0:
                    panty.append(d)
                    continue
                if d.mn[2] < az - KRIDLO_POD_OSOU:
                    continue
                kand.append(d)
            if not kand:
                self.warn("%s: kridlo dvirek nenalezeno - zustava staticka" % popis)
                self.pocty["staticke_komponenty"] += 1
                return
            jadro = max(kand, key=lambda d: (float(d.sz[0]), d.jm))
            if jadro.sz[0] < 0.5 * rozpeti:
                self.warn("%s: kridlo dvirek nenalezeno (nejsirsi dil %.0f mm z %.0f) - zustava staticka"
                          % (popis, jadro.sz[0], rozpeti))
                self.pocty["staticke_komponenty"] += 1
                return
            # horni pulky pantu (virtualni AABB) + jadro -> souvisly rust
            clenove = [(jadro.mn, jadro.mx)]
            for p in panty:
                mn = p.mn.copy()
                mn[2] = az
                clenove.append((mn, p.mx))
            kridlo = [jadro]
            zbyva = [d for d in kand if d is not jadro]
            zmena = True
            while zmena:
                zmena = False
                for d in list(zbyva):
                    if any(_mezera(d.mn, d.mx, mn, mx) <= KRIDLO_MEZERA for mn, mx in clenove):
                        kridlo.append(d)
                        clenove.append((d.mn, d.mx))
                        zbyva.remove(d)
                        zmena = True
        # piny (predkrok) - jen kdyz je zapadka v kusovniku (nebo dvirka z geometrie)
        piny = []
        if kus["zapadka"] or z_geometrie:
            for d in sorted(kridlo, key=lambda d: float(d.c[0])):
                if not (d.chrom and _rozmer_ok(d.sz, PIN_ROZMER, PIN_TOL) and abs(d.sz[2] - PIN_ROZMER[2]) <= PIN_TOL):
                    continue
                skup = [d]
                for e in kridlo:
                    if e is d:
                        continue
                    nad = e.cerny and _rozmer_ok(e.sz, KNOFLIK_ROZMER, PIN_TOL) and \
                        abs(e.c[0] - d.c[0]) < 3.0 and abs(e.c[1] - d.c[1]) < 3.0 and -1.0 < e.mn[2] - d.mx[2] < 2.0
                    pod = e.modry and _rozmer_ok(e.sz, ZAPADKA_ROZMER, 3.0) and -1.0 < d.mn[2] - e.mx[2] < 1.0 \
                        and e.mn[0] - 1.0 <= d.c[0] <= e.mx[0] + 1.0
                    if nad or pod:
                        skup.append(e)
                piny.append(skup)
            if kus["zapadka"] and not piny:
                self.warn_typ(uid, "zapadka (pin) z kusovniku v modelu nenalezena - dvirka bez predkroku odjisteni")
        pin_dily = set(id(e) for s in piny for e in s)
        # teziste kridla a smer otoceni (teziste k celu)
        wx = float((min(d.mn[0] for d in kridlo) + max(d.mx[0] for d in kridlo)) / 2.0)
        P_lok = P0 + smer * ((wx - P0[0]) / smer[0])
        P_w = ram.bod(P_lok)
        ax_w = _norm(ram.smer(smer))
        vpravo = np.cross(-np.array(self.api.front, dtype=np.float64), np.array([0.0, 1.0, 0.0]))
        if float(np.dot(ax_w, vpravo)) < -1e-6 or (abs(float(np.dot(ax_w, vpravo))) <= 1e-6 and
                                                   float(np.dot(ax_w, np.array(self.api.front))) < 0):
            ax_w = -ax_w
        vahy = np.array([float(np.linalg.norm(d.sz)) + 1.0 for d in kridlo])
        teziste_lok = np.sum([d.c * w for d, w in zip(kridlo, vahy)], axis=0) / float(vahy.sum())
        rel = ram.bod(teziste_lok) - P_w
        posun_k_celu = float(np.dot(np.cross(ax_w, rel), ram.front))
        if abs(posun_k_celu) < 1.0:
            self.warn("%s: teziste kridla lezi v ose - nelze urcit smer otevreni, zustava staticka" % popis)
            self.pocty["staticke_komponenty"] += 1
            return
        velikost = abs(float(self.cfg[sekce]["uhel_deg"]))
        if not 0.0 < velikost <= 180.0:
            self.warn("%s: uhel dvirek %.0f mimo rozsah - zustava staticka" % (popis, velikost))
            return
        uhel = velikost if posun_k_celu > 0 else -velikost
        # dorazy beznych dvirek (Robert 2026-10-02) - jede s kridlem, do drahy a kontrol patri k nemu
        dorazy, dorazy_zazn = [], []
        if not podlahova:
            dorazy, dorazy_zazn = self.dorazy_dvirek(popis, ram, kridlo, lad)
        kridlo_d = list(kridlo) + dorazy
        kontrola_dyn = None
        if not podlahova and velikost > 90.0:
            # Robert 2026-10-01: panty se daji vyklopit o vetsi uhel nez 90.
            # Nejvetsi uhel do nastaveneho maxima, pri kterem kridlo po cele
            # draze nic neprojde (krok 5 st., minimum 90).
            zn = 1.0 if uhel > 0 else -1.0

            def omez_uhel(kr):
                vv = velikost
                while vv > 90.0:
                    nove_d, _p = self.naraz_drahy(ram, kr, list(osa_dily) + list(panty), P_w, ax_w, zn * vv)  # vlastni pant neni prekazka
                    if not nove_d:
                        break
                    vv -= 5.0
                return max(90.0, vv)
            v = omez_uhel(kridlo_d)
            if v < velikost:
                lad["uhel_omezen_kolizi"] = {"z": velikost, "na": v}
                if dorazy:
                    v_bez = omez_uhel(kridlo)
                    if v < v_bez:
                        lad["dorazy_omezuji_uhel"] = {"bez_dorazu": v_bez, "s_dorazy": v}
                        self.warn("%s: dorazy dvirek omezuji uhel sklopeni na %.0f st. (bez nich %.0f)" % (popis, v, v_bez))
            uhel = zn * v
            kontrola_dyn = {"zn": zn, "v": v, "velikost": velikost}
        rel2 = _rodrigues(rel, ax_w, math.radians(uhel))
        if podlahova:
            nove, prekazky = self.naraz_drahy(ram, kridlo, osa_dily, P_w, ax_w, uhel)
            lad["draha"] = {"nosny_profil": nosic.jm if nosic is not None else None, "novych_pruniku": nove,
                            "prekazky": prekazky[:8]}
            if nove:
                self.warn("%s: podlahova dvirka by pri sklapeni prosla %s (%d trojuhelniku) - zustava staticka"
                          % (popis, "ramem" if nosic is None else "okolim", nove))
                self.pocty["staticke_komponenty"] += 1
                return
        # rozriznuti pantu v ose (horni pulka jede s kridlem)
        horni_pulky = []
        split = getattr(api, "split", None)
        for p in panty:
            res = split(p.o, _v(P_w, 4), _v(ram.up, 6)) if split else None
            if res:
                horni_pulky.append(res[1].name)
                self.pocty["panty_rozriznute"] += 1
        did = self.nove_id("d")
        objekty = [d.jm for d in kridlo if id(d) not in pin_dily] + horni_pulky + [d.jm for d in dorazy]
        self.pivots.append({"id": did, "origin": _v(P_w), "parent": None, "objects": objekty})
        if not podlahova:
            self.dorazy_info.append({"pivot": did, "komponenta": popis, "dorazy": dorazy_zazn})
        steps = []
        lad_piny = []
        for skup in piny:
            pin = skup[0]
            dovnitr = -1.0 if pin.c[0] > wx else 1.0
            ppid = self.nove_id("k")
            o_w = ram.bod(pin.c)
            ax_pin = _norm(ram.smer(np.array([dovnitr, 0.0, 0.0])))
            self.pivots.append({"id": ppid, "origin": _v(o_w), "parent": did, "objects": [e.jm for e in skup]})
            steps.append({"p": ppid, "op": "T", "ax": _v(ax_pin, 6), "v": _r(self.cfg["pin"]["posun_mm"], 1),
                          "ms": self._ms("pin")})
            lad_piny.append({"pivot": ppid, "dily": [e.jm for e in skup], "origin": _v(o_w, 1), "ax": _v(ax_pin, 4)})
            self.pocty["piny"] += 1
            self.pin_pouzit = True
        steps.append({"p": did, "op": "R", "ax": _v(ax_w, 6), "v": _r(uhel, 1), "ms": self._ms(sekce)})
        druh = "floor_door" if podlahova else "door"
        mot = {"k": druh, "steps": steps, "pick": [did]}
        self.motions.append((self.razeni(k, ram, ram.bod(teziste_lok)), druh, mot))
        if kontrola_dyn is not None:
            # uhel se po sestaveni vsech komponent dokontroluje proti plne otevrenym
            # supliku/vysuvum (dvirka_dokonci) - ty tu jeste nemusi existovat
            kontrola_dyn.update({
                "popis": popis, "ram": ram, "kridlo": kridlo_d, "P_w": P_w, "ax_w": ax_w, "krok": steps[-1],
                "objekty": list(objekty), "piny": [e.jm for s in piny for e in s], "lad": lad, "rel": rel})
            self.dvere.append(kontrola_dyn)
        self.pocty["podlahova_dvirka" if podlahova else "dvirka"] += 1
        if z_geometrie:
            self.warn_typ(uid, "kusovnik ve Vandr DB neuvadi pant ani zapadku - dvirka urcena z modelu (panty + klouby "
                               "na jedne primce)")
        lad["dvirka"] = {
            "pivot": did, "druh": druh, "origin": _v(P_w, 2), "ax": _v(ax_w, 6), "uhel": uhel,
            "kridlo": [d.jm for d in kridlo], "panty_horni": horni_pulky, "piny": lad_piny,
            "teziste": _v(ram.bod(teziste_lok), 1), "posun_teziste_k_celu_mm": _r(float(np.dot(rel2 - rel, ram.front)), 1),
            "celo_komponenty": _v(ram.front, 4), "z_geometrie": z_geometrie,
            "cely_ram": nosic is not None}

    def naraz_drahy(self, ram, kridlo, osa_dily, P_w, ax_w, uhel):
        """Kontrola drahy sklapeni: obaly dilu kridla (lokalni ram komponenty,
        zmensene o DRAHA_TOL) proti trojuhelnikum vseho, co se s kridlem
        nehybe (ostatni dily produktu v zavrene poloze, bez osovych sroubu),
        ve DRAHA_VZORKU polohach 0..uhel. Pocita jen NOVE pruniky proti
        poloze 0 (co se dotyka uz v modelu, neni naraz). Vraci (pocet novych
        trojuhelniku, [jmena dilu-prekazek])."""
        api = self.api
        boxy = []
        for d in kridlo:
            lo, hi = d.mn + DRAHA_TOL, d.mx - DRAHA_TOL
            if np.all(hi > lo):
                boxy.append((lo, hi))
        if not boxy:
            return 0, []
        P_l = ram.lok(P_w)
        a_l = _norm(ram.R @ np.asarray(ax_w, dtype=np.float64))
        rohy = np.array([[hi[0] if c & 1 else lo[0], hi[1] if c & 2 else lo[1], hi[2] if c & 4 else lo[2]]
                         for lo, hi in boxy for c in range(8)]) - P_l
        podel = rohy @ a_l
        r_max = float(np.max(np.linalg.norm(rohy - np.outer(podel, a_l), axis=1)))
        E = np.array([P_l + a_l * float(podel.min()), P_l + a_l * float(podel.max())])
        reg_lo, reg_hi = E.min(axis=0) - r_max - 1.0, E.max(axis=0) + r_max + 1.0
        vyjmout = set(d.jm for d in kridlo) | set(d.jm for d in osa_dily)
        T_all, T_jm = [], []
        for o in api.produkt:
            if o.name in vyjmout:
                continue
            mn, mx = (np.array(c, dtype=np.float64) for c in api.aabb(o))
            lmn, lmx = ram.aabb_lok(mn, mx)
            if np.any(lmx < reg_lo) or np.any(lmn > reg_hi):
                continue
            T = api.tris(o)
            if len(T):
                T_all.append(T)
                T_jm += [o.name] * len(T)
        if not T_all:
            return 0, []
        T = np.concatenate(T_all)
        T_jm = np.array(T_jm)

        def zasahy(theta_deg):
            Tw = _rot_body(T.reshape(-1, 3), np.asarray(P_w, dtype=np.float64), ax_w, -math.radians(theta_deg))
            Tl = ram.lok(Tw).reshape(-1, 3, 3)
            hit = np.zeros(len(T), dtype=bool)
            for lo, hi in boxy:
                hit |= _tri_box(Tl, lo, hi)
            return hit

        h0 = zasahy(0.0)
        nove = np.zeros(len(T), dtype=bool)
        for t in np.linspace(0.0, 1.0, DRAHA_VZORKU + 1)[1:]:
            nove |= zasahy(float(t) * uhel) & ~h0
        return int(nove.sum()), sorted(set(T_jm[nove].tolist()))

    # ------------------------------------- dvirka x otevrene supliky/vysuvy
    def _posuny_otevrenych(self):
        """Jmeno dilu -> posun (svet, glTF mm) v PLNE otevrene poloze supliku
        a vysuvu: soucet kroku T pohybu drawer/slide pres retez pivotu
        (box vnoreny pod vysuvem jede s nim, vlastni zvedani boxu se
        nepocita - 'Otevrit vse' boxy nezvedava)."""
        vlastni = {}
        for _k, druh, m in self.motions:
            if druh not in ("drawer", "slide"):
                continue
            for st in m["steps"]:
                if st["op"] == "T":
                    vlastni[st["p"]] = vlastni.get(st["p"], np.zeros(3)) + _norm(st["ax"]) * float(st["v"])
        rodic = {pv["id"]: pv["parent"] for pv in self.pivots}
        out = {}
        for pv in self.pivots:
            soucet, pid, hl = np.zeros(3), pv["id"], 0
            while pid is not None and hl < 50:
                soucet = soucet + vlastni.get(pid, np.zeros(3))
                pid = rodic.get(pid)
                hl += 1
            if float(np.max(np.abs(soucet))) > 1e-6:
                for jm in pv["objects"]:
                    out[jm] = soucet
        return out

    def _dvere_priprava(self, d, posun, obj):
        """Jednou za dvirka: obaly kridla (lokalni ram), trojuhelniky kridla
        (zavrene), obalky a trojuhelniky otevrenych dilu v dosahu dvirek."""
        api = self.api
        ram = d["ram"]
        vlastni = set(d["objekty"]) | set(d["piny"])
        kridlo_o = [obj[jm] for jm in sorted(vlastni) if jm in obj]
        boxy_k = []
        for dil in d["kridlo"]:
            lo, hi = dil.mn + DRAHA_TOL, dil.mx - DRAHA_TOL
            if np.all(hi > lo):
                boxy_k.append((lo, hi))
        Td = [api.tris(o) for o in kridlo_o]
        Td = np.concatenate([t for t in Td if len(t)]) if any(len(t) for t in Td) else np.zeros((0, 3, 3))
        if not len(Td):
            return None
        P_w = np.asarray(d["P_w"], dtype=np.float64)
        ax = _norm(d["ax_w"])
        Vd = Td.reshape(-1, 3) - P_w
        podel = Vd @ ax
        r_max = float(np.max(np.linalg.norm(Vd - np.outer(podel, ax), axis=1)))
        E = np.array([P_w + ax * float(podel.min()), P_w + ax * float(podel.max())])
        reg_lo, reg_hi = E.min(axis=0) - r_max - 1.0, E.max(axis=0) + r_max + 1.0
        prek_T, prek_box, prek_jm = [], [], []
        for jm, p in posun.items():
            if jm in vlastni or jm not in obj:
                continue
            o = obj[jm]
            mn, mx = (np.array(c, dtype=np.float64) + 0.0 for c in api.aabb(o))
            mn, mx = mn + p, mx + p
            if np.any(mx < reg_lo) or np.any(mn > reg_hi):
                continue
            T = api.tris(o)
            if not len(T):
                continue
            prek_T.append(T + p)
            prek_jm += [jm] * len(T)
            lo, hi = mn + DRAHA_TOL, mx - DRAHA_TOL
            if np.all(hi > lo):
                prek_box.append((jm, lo, hi))
        if not prek_T:
            return {"prazdne": True}
        return {"boxy_k": boxy_k, "Td": Td, "P_w": P_w, "ax": ax, "ram": ram,
                "T": np.concatenate(prek_T), "T_jm": np.array(prek_jm), "box": prek_box}

    @staticmethod
    def _dvere_zasahy(c, theta_deg):
        """(zasahy kridla do trojuhelniku otevrenych dilu, zasahy obalek otevrenych
        dilu do trojuhelniku kridla) pri uhlu theta (stupne, se znamenkem)."""
        ram = c["ram"]
        Tw = _rot_body(c["T"].reshape(-1, 3), c["P_w"], c["ax"], -math.radians(theta_deg))
        Tl = ram.lok(Tw).reshape(-1, 3, 3)
        ha = np.zeros(len(c["T"]), dtype=bool)
        for lo, hi in c["boxy_k"]:
            ha |= _tri_box(Tl, lo, hi)
        Td = _rot_body(c["Td"].reshape(-1, 3), c["P_w"], c["ax"], math.radians(theta_deg)).reshape(-1, 3, 3)
        hb = [_tri_box(Td, lo, hi) for _jm, lo, hi in c["box"]]
        return ha, hb

    def naraz_otevrene(self, c, theta_max_deg):
        """Nove pruniky dvirek (kridlo) s plne otevrenymi supliky/vysuvy po
        drahe 0..theta_max (vzorek po DRAHA_KROK_DEG): obaly kridla proti
        trojuhelnikum otevrenych dilu A obalky otevrenych dilu proti
        trojuhelnikum kridla; NOVE = proti poloze dvirek 0 (co se dotyka uz
        se zavrenymi dvirky, neni naraz). Vraci (pocet, [jmena dilu])."""
        if c is None or c.get("prazdne"):
            return 0, []
        zn = 1.0 if theta_max_deg >= 0 else -1.0
        n = max(1, int(math.ceil(abs(theta_max_deg) / DRAHA_KROK_DEG)))
        ha0, hb0 = self._dvere_zasahy(c, 0.0)
        nove_a = np.zeros(len(ha0), dtype=bool)
        nove_b = [np.zeros(len(c["Td"]), dtype=bool) for _ in hb0]
        for t in np.linspace(0.0, 1.0, n + 1)[1:]:
            ha, hb = self._dvere_zasahy(c, float(t) * theta_max_deg)
            nove_a |= ha & ~ha0
            for i, h in enumerate(hb):
                nove_b[i] |= h & ~hb0[i]
        jmena = set(c["T_jm"][nove_a].tolist()) | set(c["box"][i][0] for i, h in enumerate(nove_b) if h.any())
        return int(nove_a.sum() + sum(int(h.sum()) for h in nove_b)), sorted(jmena)

    def dvirka_dokonci(self):
        """Robert 2026-10-01: dvirka sklopena o 120 st. nesmi nic projit, ani
        kdyz jsou otevrene vsechny supliky a vysuvy ('Otevrit vse'). Po
        sestaveni vsech komponent (a pohybu boxu) se uhel kazdych dvirek
        zkontroluje proti trojuhelnikum plne vysunutych supliku/vysuvu
        (vc. boxu, ktere na nich jedou nezvednute) a po DVIRKA_KROK_DEG se
        snizuje, nejnize na DVIRKA_MIN_DEG. Zavreny stav (staticke dily)
        uz overila kontrola drahy pri detekci dvirek."""
        if not self.dvere:
            return
        posun = self._posuny_otevrenych()
        obj = {o.name: o for o in self.api.produkt}
        for d in self.dvere:
            lad = d["lad"]
            c = self._dvere_priprava(d, posun, obj) if posun else None
            if c is None or c.get("prazdne"):
                lad["otevrene_supliky"] = {"prekazek_v_dosahu": 0}
                continue
            zn, v0 = d["zn"], d["v"]
            v = v0
            nove, jm = self.naraz_otevrene(c, zn * v)
            while nove and v > DVIRKA_MIN_DEG:
                v = max(DVIRKA_MIN_DEG, v - DVIRKA_KROK_DEG)
                nove, jm = self.naraz_otevrene(c, zn * v)
            lad["otevrene_supliky"] = {"prekazek_v_dosahu": len(c["box"]), "prekazky_po_omezeni": jm[:6],
                                       "novych_pruniku": nove}
            if v < v0:
                d["krok"]["v"] = _r(zn * v, 1)
                lad["uhel_omezen_otevrenymi_supliky"] = {"z": v0, "na": v}
                if isinstance(lad.get("dvirka"), dict):
                    lad["dvirka"]["uhel"] = zn * v
                    lad["dvirka"]["posun_teziste_k_celu_mm"] = _r(float(np.dot(
                        _rodrigues(d["rel"], d["ax_w"], math.radians(zn * v)) - d["rel"], d["ram"].front)), 1)
                self.warn("%s: dvirka sklopena jen o %.0f st. (z %.0f) - pri otevrenych supliku/vysuvu by narazila"
                          % (d["popis"], v, v0))
            if nove:
                self.warn("%s: dvirka narazi do otevreneho supliku/vysuvu i pri %.0f st. (%d trojuhelniku)"
                          % (d["popis"], v, nove))

    # ------------------------------------------------------------- boxy
    def najdi_boxy(self, k, popis, uid, ram, D, kus, supliky, lad):
        skorepiny = [d for d in D if d.box_mat and float(d.sz.min()) >= BOX_MIN]
        if not skorepiny:
            self.warn("%s: kusovnik uvadi boxy, v modelu nejsou - bez pohybu boxu" % popis)
            return
        if len(skorepiny) != kus["boxy"]:
            lad["info_boxy"] = "kusovnik %d boxu, model %d - animovano podle modelu" % (kus["boxy"], len(skorepiny))
        skup = {id(s): [s] for s in skorepiny}
        prirazene = set(id(s) for s in skorepiny)
        for d in D:
            if id(d) in prirazene or d.nosnik:
                continue
            for s in skorepiny:
                if np.all(d.mn >= s.mn - BOX_PRILOHA_TOL) and np.all(d.mx <= s.mx + BOX_PRILOHA_TOL):
                    skup[id(s)].append(d)
                    prirazene.add(id(d))
                    break
        # Robert 2026-10-01: "deska pod KLT je jeho dno, ma se sloucit s boxem".
        # Tenka deska (<= 15 mm), jejiz horni plocha lezi na spodku skorepiny
        # (lokalni Z = nahoru, tolerance 3 mm) a pudorysem kryje aspon 70 %
        # spodku boxu, jede s boxem.
        for d in D:
            if id(d) in prirazene or d.nosnik or float(d.sz[2]) > 15.0:
                continue
            for s in skorepiny:
                if abs(float(d.mx[2]) - float(s.mn[2])) > 3.0:
                    continue
                ox = min(float(d.mx[0]), float(s.mx[0])) - max(float(d.mn[0]), float(s.mn[0]))
                oy = min(float(d.mx[1]), float(s.mx[1])) - max(float(d.mn[1]), float(s.mn[1]))
                plocha_boxu = float(s.sz[0]) * float(s.sz[1])
                if ox > 0 and oy > 0 and plocha_boxu > 0 and ox * oy >= 0.7 * plocha_boxu \
                        and float(d.sz[0]) * float(d.sz[1]) <= 1.6 * plocha_boxu:
                    skup[id(s)].append(d)
                    prirazene.add(id(d))
                    lad.setdefault("dno_boxu", []).append(d.jm)
                    break
        for s in sorted(skorepiny, key=lambda s: (-float(s.c[2]), float(s.c[0]))):
            cleny = skup[id(s)]
            sp = next((sp for sp in supliky if any(d is s for d in sp["jede"])), None)
            if sp is None and supliky:
                # box mimo vysuv v komponente s vysuvem - nejasne, zustava
                self.warn("%s: box neni na vysuvu ani na polici bez kolejnic - zustava staticky" % popis)
                continue
            stred, mn, mx = self._stred(cleny)
            sub, sub_zdroje = self.sub_boxu(uid, kus, s)
            self.boxy.append({"k": k, "popis": popis, "ram": ram, "cleny": cleny, "sp": sp,
                              "mn": mn, "mx": mx, "razeni": self.razeni(k, ram, ram.bod(stred)),
                              "sub": sub, "sub_zdroje": sub_zdroje})

    def boxy_dokonci(self):
        """Pohyb boxu az nakonec - kolize se kontroluji proti finalni
        mnozine dilu, ktere se s boxem nehybou: staticke dily + pohyblive
        dily ostatnich komponent v zavrene poloze (konzervativne; napr.
        madlo vysuvu nad boxem). Zdvih se zkrati na volne misto nad boxem
        (- 2 mm); kdyz je mensi nez min_zdvih_mm, box jede jen s vysuvem."""
        if not self.boxy:
            return
        api = self.api
        jede_v = {}                        # jmeno dilu -> id pivotu (stav pred boxy)
        for pv in self.pivots:
            for jm in pv["objects"]:
                jede_v[jm] = pv["id"]
        produkt = list(api.produkt)
        aabb = {o.name: tuple(np.array(c, dtype=np.float64) for c in api.aabb(o)) for o in produkt}
        jmena = [o.name for o in produkt]
        AMN = np.array([aabb[j][0] for j in jmena])
        AMX = np.array([aabb[j][1] for j in jmena])
        rohy_vse = np.stack([np.where(np.array([(c >> i) & 1 for i in range(3)], dtype=bool), AMX, AMN)
                             for c in range(8)], axis=1)           # (N, 8, 3)
        nahoru = np.array([0.0, 0.0, 1.0])
        lad_boxy = []
        zkracene = {}
        for b in self.boxy:
            ram, sp = b["ram"], b["sp"]
            cleny_jm = set(d.jm for d in b["cleny"])
            if sp is not None:
                # s boxem jede: jeho vysuv a vsechny boxy toho vysuvu
                spolu = set(sp["piv"]["objects"]) | set(d.jm for bb in self.boxy if bb["sp"] is sp for d in bb["cleny"])
            else:
                spolu = set(cleny_jm)
            maska = np.array([j not in spolu for j in jmena])
            staticky = np.array([j not in jede_v for j, m in zip(jmena, maska) if m])
            # prekazky v lokalnim ramu komponenty boxu
            Lr = ram.lok(rohy_vse.reshape(-1, 3)).reshape(-1, 8, 3)
            PMN, PMX = Lr.min(axis=1)[maska], Lr.max(axis=1)[maska]
            pjm = [j for j, m in zip(jmena, maska) if m]
            bmn, bmx = b["mn"].copy(), b["mx"].copy()

            def zasahy(mn, mx, vyjma=None):
                hit = np.all(np.minimum(PMX, mx) - np.maximum(PMN, mn) > KOLIZE_TOL, axis=1)
                if vyjma is not None:
                    hit &= ~vyjma
                return np.nonzero(hit)[0]

            def volno_nad(mn, mx):
                stopa = np.all(np.minimum(PMX[:, :2], mx[:2]) - np.maximum(PMN[:, :2], mn[:2]) > KOLIZE_TOL, axis=1)
                nad = stopa & (PMN[:, 2] >= mx[2] - KOLIZE_TOL)
                return float(PMN[nad, 2].min() - mx[2]) if nad.any() else float("inf")

            puvodni = np.zeros(len(PMN), dtype=bool)
            puvodni[zasahy(bmn, bmx)] = True          # uz v modelu se dotyka/prekryva (oblouk multiboxu)
            steps, zaznam = [], {"box": sorted(cleny_jm)[:3], "komponenta": b["popis"], "sub": b["sub"],
                                 "sub_zdroje": b["sub_zdroje"]}
            if sp is not None:
                cfg = self.cfg["box_na_vysuvu"]
                zdvih = float(cfg["zdvih_mm"])
                posun = np.array([0.0, -sp["draha"], 0.0])      # vysuv k celu (lokalni -Y)
                emn, emx = bmn + posun, bmx + posun
                zaznam.update({"druh": "na_vysuvu", "draha_vysuvu_mm": sp["draha"]})
                hit = zasahy(emn, emx)
                if len(hit):
                    self.warn("%s: box po vysunuti narazi (%d dilu) - jede jen s vysuvem" % (b["popis"], len(hit)))
                    zaznam["kolize"] = [pjm[i] for i in hit[:5]]
                    lad_boxy.append(zaznam)
                    continue
                volno = volno_nad(emn, emx)
                zdvih_ok = min(zdvih, volno - 2.0)
                zaznam.update({"volno_nad_mm": _r(min(volno, 9999.0), 1), "zdvih_mm": _r(zdvih_ok, 1)})
                if zdvih_ok < float(cfg["min_zdvih_mm"]):
                    self.warn("%s: nad vysunutym boxem je jen %.0f mm mista - box jede jen s vysuvem"
                              % (b["popis"], volno))
                    lad_boxy.append(zaznam)
                    continue
                if zdvih_ok < zdvih - 0.05:
                    zkracene.setdefault(b["popis"], []).append(zdvih_ok)
                steps.append({"op": "T", "ax": [0.0, 1.0, 0.0], "v": _r(zdvih_ok, 1), "ms": self._ms("box_na_vysuvu")})
                konec = (emn + nahoru * zdvih_ok, emx + nahoru * zdvih_ok)
            else:
                cfg = self.cfg["box_na_polici"]
                self.box_polici_pouzit = True
                zdvih = float(cfg["zdvih_mm"])
                rez = float(cfg["rezerva_mm"])
                # predni hrana komponenty = nejprednejsi dil, ktery se nehybe
                k_jm = set(o.name for o in b["k"]["meshes"])
                predni = [aabb[j] for j in k_jm if j in aabb and j not in jede_v and j not in cleny_jm]
                if predni:
                    celo_y = min(float(ram.aabb_lok(mn, mx)[0][1]) for mn, mx in predni)
                else:
                    celo_y = float(bmn[1])
                d_ven = float(bmx[1] - celo_y + float(cfg["presah_mm"]))
                ven = np.array([0.0, -d_ven, 0.0])
                # strop nad drahou vytazeni (dily cele nad boxem v pudorysu drahy)
                stopa = np.all(np.minimum(PMX[:, :2], bmx[:2]) - np.maximum(PMN[:, :2], (bmn + ven)[:2]) > KOLIZE_TOL,
                               axis=1)
                nad = stopa & (PMN[:, 2] >= bmx[2] - KOLIZE_TOL)
                strop = float(PMN[nad, 2].min() - bmx[2] - KOLIZE_TOL - 0.1) if nad.any() else float("inf")
                z1, ok, hit = 0.0, False, []
                for _it in range(6):
                    hit = zasahy(bmn + nahoru * z1 + ven, bmx + nahoru * z1,
                                 vyjma=puvodni & (PMX[:, 2] <= bmn[2] + z1 + KOLIZE_TOL))
                    if not len(hit):
                        ok = True
                        break
                    nejmene = float(PMX[hit, 2].max() - bmn[2] + 1.0)      # aspon 1 mm nad listou
                    potreba = min(float(PMX[hit, 2].max() - bmn[2] + rez), strop)
                    if potreba < nejmene or potreba <= z1 + 0.01 or potreba > zdvih:
                        break
                    z1 = potreba
                if ok:
                    # svisly zdvih z puvodni polohy nesmi narazit (krome dilu, od kterych se box zvedne)
                    hit = zasahy(bmn, bmx + nahoru * z1, vyjma=puvodni & (PMX[:, 2] <= bmn[2] + z1 + KOLIZE_TOL))
                    ok = not len(hit)
                if not ok:
                    zaznam["prekazky"] = [[pjm[i], _v(PMN[i], 1), _v(PMX[i], 1)] for i in list(hit)[:5]]
                    zaznam["box_lok"] = [_v(bmn, 1), _v(bmx, 1)]
                z2 = 0.0
                if ok:
                    volno = volno_nad(bmn + ven + nahoru * z1, bmx + ven + nahoru * z1)
                    z2 = max(0.0, min(zdvih - z1, volno - 2.0))
                zaznam.update({"druh": "na_polici", "zdvih_pres_listu_mm": _r(z1, 1), "vytazeni_mm": _r(d_ven, 1),
                               "dozvednuti_mm": _r(z2, 1)})
                if not ok:
                    self.warn("%s: box na polici nejde vytahnout bez narazu (nad boxem malo mista) - zustava staticky"
                              % b["popis"])
                    lad_boxy.append(zaznam)
                    continue
                if z1 > 0.5:
                    steps.append({"op": "T", "ax": [0.0, 1.0, 0.0], "v": _r(z1, 1), "ms": self._ms("box_na_polici")})
                steps.append({"op": "T", "ax": _v(_norm(ram.front), 6), "v": _r(d_ven, 1),
                              "ms": self._ms("box_na_polici")})
                if z2 > 0.5:
                    steps.append({"op": "T", "ax": [0.0, 1.0, 0.0], "v": _r(z2, 1), "ms": self._ms("box_na_polici")})
                konec = (bmn + ven + nahoru * (z1 + z2), bmx + ven + nahoru * (z1 + z2))
            # kontrola konecne polohy (AABB ve 3 osach) proti vsemu, co se s boxem nehybe
            hit_final = zasahy(konec[0], konec[1])
            zaznam["kolize_plne_otevreno"] = len(hit_final)
            zaznam["kolize_plne_otevreno_staticke"] = int(sum(1 for i in hit_final if staticky[i]))
            if len(hit_final):
                self.warn("%s: box pri plnem otevreni koliduje (%d dilu) - zustava bez pohybu" % (b["popis"], len(hit_final)))
                lad_boxy.append(zaznam)
                continue
            # pivot boxu (stred dna)
            stred = (bmn + bmx) / 2.0
            o_w = ram.bod(np.array([stred[0], stred[1], bmn[2]]))
            bid = self.nove_id("b")
            if sp is not None:
                sp["piv"]["objects"] = [j for j in sp["piv"]["objects"] if j not in cleny_jm]
            self.pivots.append({"id": bid, "origin": _v(o_w), "parent": sp["pid"] if sp else None,
                                "objects": sorted(cleny_jm)})
            for st in steps:
                st["p"] = bid
            mot = {"k": "box", "steps": steps, "pick": [bid]}
            if b["sub"]:
                mot["sub"] = b["sub"]
            self.motions.append((b["razeni"], "box", mot))
            self.pocty["boxy"] += 1
            zaznam.update({"pivot": bid, "rodic": sp["pid"] if sp else None, "origin": _v(o_w, 1),
                           "konec_lok": [_v(konec[0], 1), _v(konec[1], 1)],
                           "konec_svet": [_v(v, 1) for v in ram.aabb_svet(konec[0], konec[1])]})
            lad_boxy.append(zaznam)
        for popis, z in zkracene.items():
            mn_ = len(z) > 1
            self.warn("%s: %d box%s zvednut%s jen o %.0f mm (nad %s je jiny dil)"
                      % (popis, len(z), "y" if mn_ else "", "y" if mn_ else "", min(z), "nimi" if mn_ else "nim"))
        self.ladeni["boxy"] = lad_boxy

    # ---------------------------------------------------------- vysledek
    def vysledek(self):
        # n = poradi v ramu druhu (u boxu druhu boxu: KLT box 1.., Multibox 1.., Eurobox 1..) v poradi
        # strana > sloupec zleva doprava > shora dolu > zleva doprava
        poradi = {}
        motions = []
        for klic, druh, m in sorted(self.motions, key=lambda t: (t[1], t[0])):
            skupina = (druh, m.get("sub"))
            poradi[skupina] = poradi.get(skupina, 0) + 1
            m = dict(m)
            m["n"] = poradi[skupina]
            motions.append((klic, m))
        # vystup: poradi podle druhu (supliky, vysuvy, dvirka, podlahova, boxy) a pozice v ramu cela
        # (stejne poradi jako dosud; n u boxu uz neni vzestupne napric druhy boxu)
        druhy = ["drawer", "slide", "door", "floor_door", "box"]
        motions.sort(key=lambda t: (druhy.index(t[1]["k"]) if t[1]["k"] in druhy else 9, t[0]))
        for (uid, text), n in sorted(self.typove.items()):
            self.warn("%s%s: %s" % (uid, " (%dx)" % n if n > 1 else "", text))
        if self.pin_pouzit:
            self.warn("pin dvirek: odjisteni posunem %.0f mm podel osy X komponenty (dovnitr) je HYPOTEZA z geometrie, "
                      "neovereno (pohyby-vychozi.json pin)" % self.cfg["pin"]["posun_mm"])
        if self.box_polici_pouzit:
            self.warn("box na polici: zvednout nad listu, vytahnout pred regal a dozvednout je vychozi navrh, neovereno "
                      "(pohyby-vychozi.json box_na_polici)")
        # cisla dvirek (n) pro zaznamy dorazu: pivot dvirek -> n (stejne poradi jako ve vystupu)
        n_dvirek = {m["steps"][-1]["p"]: m["n"] for _k, m in motions if m["k"] == "door"}
        dorazy = [dict(z, dvirka_n=n_dvirek.get(z["pivot"])) for z in self.dorazy_info]
        out = {"pivots": self.pivots, "motions": [m for _k, m in motions], "dims": [], "warnings": self.warnings,
               "info": {"verze": VERZE, "pocty": self.pocty, "dorazy_dvirek": dorazy}}
        cesta = os.environ.get("V3D_POHYBY_LADENI")
        if cesta:
            self.ladeni["pivots"] = self.pivots
            self.ladeni["motions"] = out["motions"]
            self.ladeni["warnings"] = self.warnings
            self.ladeni["pocty"] = self.pocty
            try:
                with open(cesta, "w", encoding="utf-8") as fh:
                    json.dump(self.ladeni, fh, ensure_ascii=False, indent=1, default=str)
            except OSError:
                pass
        return out


# ================================================================== hook
def detect(api):
    det = Detekce(api)
    if not det.ctx.get("komponenty"):
        det.warn("pohyby: ctx bez kusovniku komponent - pohyby se neurcuji (model staticky)")
        return det.vysledek()

    def klic(k):
        P = np.array(api.to_gltf(np.array(k["obj"].matrix_world)[:3, 3]))
        return (STRANA_PORADI.get(k["side"], 3), round(float(P[0]), 1), round(float(P[2]), 1),
                -round(float(P[1]), 1), k["name"])

    for k in sorted(api.components, key=klic):
        n_piv = len(det.pivots)
        n_mot = len(det.motions)
        n_box = len(det.boxy)
        n_dv = len(det.dvere)
        n_pr = len(det.pridane)
        n_di = len(det.dorazy_info)
        try:
            det.komponenta(k)
        except Exception as e:  # noqa: BLE001 - jedna komponenta nesmi shodit ostatni
            del det.pivots[n_piv:]
            del det.motions[n_mot:]
            del det.boxy[n_box:]
            del det.dvere[n_dv:]
            for ob in det.pridane[n_pr:]:          # doplnene dily (dorazy) neselhane komponenty pryc
                try:
                    api.remove_part(ob)
                except Exception:  # noqa: BLE001
                    pass
            det.pocty["dorazy_dvirek"] -= len(det.pridane) - n_pr
            del det.pridane[n_pr:]
            del det.dorazy_info[n_di:]
            det.warn("%s: chyba detekce pohybu (%s: %s) - zustava staticka" % (k["name"], type(e).__name__, e))
    zaloha = [(p, list(p["objects"])) for p in det.pivots]
    n_piv, n_mot = len(det.pivots), len(det.motions)
    try:
        det.boxy_dokonci()
    except Exception as e:  # noqa: BLE001
        det.warn("boxy: chyba kontroly (%s: %s) - boxy jedou jen s vysuvem" % (type(e).__name__, e))
        for p, obj in zaloha:
            p["objects"] = obj
        del det.pivots[n_piv:]
        del det.motions[n_mot:]
    try:
        det.dvirka_dokonci()
    except Exception as e:  # noqa: BLE001
        det.warn("dvirka: chyba kontroly proti otevrenym supliku/vysuvum (%s: %s) - dvirka se sklopi jen o %.0f st."
                 % (type(e).__name__, e, DVIRKA_MIN_DEG))
        for d in det.dvere:
            d["krok"]["v"] = _r((1.0 if d["krok"]["v"] > 0 else -1.0) * DVIRKA_MIN_DEG, 1)
    return det.vysledek()

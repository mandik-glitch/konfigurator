# Razítka při živém tažení (bot8, 2026-10-08)

**Zadání:** Robert 2026-10-08 (po nasazení razítek, pravidlo 61): *„razítka na generátoru při tažení zůstávají na místě“* – při tažení úchytu ve 3D se díly modelu hýbou přímo v prohlížeči (živé tažení,
`webapp/js/v3d-ovladani.js`, popis `vodici.ovladani.zive_rozsahy`), ale logo (instance uzlu) a výplň drážky (vrcholy připojené na konec materiálu hliník) nepatří do rozsahů dílů → zůstaly stát.

## Co se změnilo
* **Server** (`api/stul_razitka.py`, `api/stul_glb.py`, `api/stul_ovladani_verejne.py`): každé razítko nese `dil` (index dílu, na kterém sedí); `poskladej_glb` zaznamená pro každé razítko `{dil, uzel (n<i> loga), vypln: [uzel hliník, od, počet]}`
  (`_POSLEDNI_RAZITKA`, cache `_RAZITKA_CACHE`), `vodici` je dává do `vodici.ovladani.razitka` (jen u výchozího modelu S razítky), veřejný popis ovladání je předává dál. **GLB bajty, pravidla umístění, hash, cena, vedlejší cache se nemění**
  (regrese bit po bitu z `scripts/2026-10-08_razitka_generatory/` platí dál).
* **Prohlížeč** (`v3d-ovladani.js` 1.1.5 → 1.2.0): `liveBegin` posbírá razítka na hýbaných dílech, `liveApply` je hýbe jako tuhá tělesa: `posun` stejně jako díl, `natahni` / `roztahni` podle polohy STŘEDU razítka vůči STŘEDU dílu podél osy
  (stejné pravidlo jako pro vrcholy dílu), Esc je vrátí, po puštění přijde přesný model (razítka se na novém hashi umístí znovu – viz „Poznámky“). Nové zkušební háčky `ov.liveRazitka()`.
* `?v=` hashe assetů přepsány (`scripts/stul_verze.py`, `scripts/miniweb_verze.py`); dokumentace `docs/OVLADANI_3D.md`.
* **Nasazení:** statika (JS) je živě hned po commitu, popis razítek v API až po reloadu (0:00 nebo Robertovo „nasadit“) – do té doby se nový klient chová jako dosud (bez `razitka` nic nehýbe).

## Důkazy
| co | výsledek |
|---|---|
| `test_razitka_tazeni.py` (hermeticky): popis razítek platný (dil, uzel, výplň 24 vrcholů), ve veřejném popisu, bez razítek není, cache; emulace pravidla z JS nad skutečným GLB pro VŠECHNY tahy se živými operacemi × ±60 mm × 6 konfigurací (systémy 30 / 35 / 40 / 45): razítka u hostitele ≤ 5 mm od obálky, u posunu přesně jako díl, nehýbané stojí; kontrola citlivosti (bez pohybu razítek by invariant selhal) | 536 OK |
| `test_razitka_tazeni_stranka.js` (Chromium, skutečná stránka): posun (`panelpos`) logo i výplň přesně s dílem, nehýbaná stojí, Esc vrací, natahni / roztahni (`h`, `w`, `d`) zůstávají u dílu (C1) a drží vzdálenost od konce dílu na své straně – NEZÁVISLÁ kontrola z vrcholů dílu před / po (C2), žádný dotaz na server během tažení, po puštění přesný model, bez chyb v konzoli | 17/17 (kandidát i živý strom) |
| mutace `mutace.py` (S1–S8 server, J1–J5 prohlížeč; J5 = bez pravidla stran u natažení přežila, dokud nepřibyla kontrola C2) | 13/13 zachyceno |
| `regrese.py` (GLB bit po bitu 873 konfigurací) na kódu s touto změnou | 0 chyb |
| `regrese_resolve.py` (90 odpovědí resolve; nové pole `razitka` se před srovnáním odebírá) | 0 rozdílů |

## Poznámky
* **Po puštění se razítka umístí znovu**: umístění se odvozuje z hashe konfigurace (pravidlo 61: pravidla umístění se nemění), takže přesný model po tažení má razítka na jiných místech než náhled při tažení.
  Kdyby to Roberta rušilo, jde o změnu pravidla (stabilní umístění nezávislé na rozměrech) – rozhodnutí Roberta, ne chyba.
* Spuštění: viz hlavičky souborů; kandidátní strom bez zámku `prepare_cand.sh` (API i JS), browserový test z kandidáta: `_most_stul.py` spustit z `$CAND/scripts/...`.
* Obrázky před / po: `render_obrazky.py` (stejný stůl, police o 220 mm výš; razítka stojí / jedou s dílem / přesný model po puštění).

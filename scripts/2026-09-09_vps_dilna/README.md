# Dílna — GUI Blender na VPS

`gui_setup.py` je startovní skript pro GUI Blender na VPS (systemd
jednotka `blender-gui`). Robert v té scéně ladí vzhled renderů; každých
10 s se ukládá snapshot do `private-files/blender-renders/vps_dilna.blend`
a **každá renderovací úloha ho bere jako šablonu automaticky**.

> Robert 2026-09-09: *„moje dilna Blender je tam nato aby se to nastaveni
> renderu vzalo odtud"*

Podrobně viz `PRODUKTOVE_RENDERY.md`.

## Dílna je TRVALÁ

`vps_dilna.blend` je **stav dílny**, ne jen výstup. Při startu se
otevře, pokud existuje; od nuly se staví jen poprvé. Restart služby
Robertovu práci nezahodí.

> Robert 2026-09-09: *„ty menis nastaveni renderu v moji dilne?"* — do
> té chvíle ano, skript scénu stavěl znovu při každém restartu a každá
> oprava přepsala, co si nastavil. Opraveno.

## Co skript postaví (jen při prvním spuštění)

* sestavu z `dilna_job.json` (stejný kód a převod souřadnic jako
  `api/blender_render_turntable.py`)
* studiový základ: HDRI schované před kamerou (Light Path), dvě plošná
  světla, `TT_FLOOR` jako shadow catcher, 256 vzorků, AgX
* ořez viewportu 10–1 000 000 ve **všech** layoutech (scéna je v mm)

Vše je běžná scéna — Robert to smí libovolně přepsat, autosave to
přenese do dalšího renderu.

## Pasti (každá už jednou stála čas)

1. **Obrázky se musí zabalit do souboru** (`img.pack()`). Šablona jde na
   Robertův Windows PC, kde cesty z VPS neexistují — nezabalené HDRI tam
   Blender nenajde a **celý render vyjde fialový**. Balí se automaticky
   při každém autosave, takže i to, co si Robert načte sám. Je to tatáž
   chyba, jakou měl jeho vlastní `X30-1.blend` (odkaz do `Downloads` na
   jeho PC), jen obráceně.
2. `bpy.context.active_object` při startu přes `--python` **neexistuje**
   (`AttributeError`) — mesh se staví z dat, ne operátorem.
2. Startovní skript **nesmí záviset na souboru v uklízeném adresáři** —
   dřív načítal `gui_doblo_a.glb`, ten zmizel, skript spadl a Robert
   koukal 3 hodiny na prázdnou scénu.
4. Scéna je v **milimetrech**; bez zvednutí `clip_end` je regál za
   ořezovou rovinou i při správném natočení.
5. Autosave přes `save_as_mainfile(copy=True)` + `os.replace` — jinak by
   se Robertovi měnil soubor pod rukama a render mohl číst rozepsaný
   `.blend`.

## Restart

```bash
systemctl restart blender-gui
```

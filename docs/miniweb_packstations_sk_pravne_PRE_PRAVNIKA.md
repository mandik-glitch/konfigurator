# Mini-shop: minimálne právne texty (bot7, 2026-10-02)

**Rozhodnutie Roberta: len zákonné prvky, žiadne veľké právne texty.** Web je len pre podnikateľov a len poptávkový (nič sa neobjednáva), preto sú dva krátke dokumenty:
`terms` (prevádzkovateľ, dopyt nie je objednávka) a `privacy` (stručná ochrana údajov). Súbory: `miniweb_packstations_sk_pravne_navrh.json` a `miniweb_packstations_en_pravne_navrh.json`.
Žiadne obchodné podmienky, reklamácie ani vrátenie, kým sa nič neobjednáva.

## Odkiaľ sú údaje
- Názov, sídlo, IČO, DIČ, telefón: `company_info` (rovnaké ako `documents.SUPPLIER`), bez e-mailu.
- Zápis v obchodnom registri: **Městský soud v Praze, oddiel C, vložka 352112** (verejný register cez ARES, zápis z 2021-09-16, predtým Krajský soud v Brně, C 62210). Na našich weboch žiadny zápis uvedený nebol.
- Cookies: v kóde mini-shopu je len `sessionStorage` a `localStorage` (obsah dopytu, jazyk), žiadne cookies ani analytika. Neoverené je, či by pred weby neskôr nepridala cookie služba (napr. CDN).

## Čo je predpoklad (potvrdiť Robertom, prípadne účtovníčkou)
- **Doba uchovávania:** správy, objednávky a doklady sa uchovávajú bez časového obmedzenia, kým Robert nerozhodne inak (Robert 2026-10-04). Poznámka: GDPR (čl. 5 ods. 1 písm. e) vyžaduje obmedzenie doby uchovávania podľa účelu; právnik by mal posúdiť formuláciu.
- Text o príjemcoch údajov je všeobecný („poskytovatelia služieb potrebných na prevádzku webu"). Konkrétnych poskytovateľov (hosting, DNS/CDN) a prípadný prenos mimo EÚ netvrdí ani nepopiera. Robert 2026-10-04: nechať všeobecne, bez mien poskytovateľov.
- Telefón v texte je telefón z `company_info` (pokyn bot3), kým API pre kontakt shopu zámerne telefón neuvádza.

## Až sa začne objednávať
Bude treba obchodné podmienky, reklamácie, DPH a ďalšie. Dlhší návrh pre B2B vrátane zoznamu 16 bodov na overenie právnikom je v histórii gitu (commit `f65b9e00`, `docs/miniweb_packstations_sk_pravne_PRE_PRAVNIKA.md`).

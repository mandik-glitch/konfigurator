# Výchozí konfigurace generátoru stolu (admin tlačítko „Uložit jako výchozí“) – bot8, 2026-10-05

Robert: „postav mi admin tlačítko v generátoru, kterým uložím konfiguraci jako výchozí“. Popis (uložení, routy, schéma, UI, důsledky): `docs/KONTRAKT_KONFIGURATOR_UI.md`, sekce
„Výchozí konfigurace generátoru“. Kód: `api/stul_api.py` (`nacti_vychozi`, `uloz_vychozi`, `vychozi_over`), `api/stul_shop.py` (`slij_vychozi`, `PUT` / `DELETE .../configurator/default`),
`webapp/js/stul-host.js` (`initVychozi`, okno `defcfg`).

```
# server (falešná DB pro app_settings, nic se nezapisuje do produkce; DB jen čte)
systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --setenv=HOME=/root --working-directory=/opt/konfigurator \
    api/venv/bin/python3 scripts/2026-10-05_vychozi_konfigurace/test_vychozi.py                  # 139 kontrol
api/venv/bin/python3 scripts/2026-10-05_vychozi_konfigurace/mutace_vychozi.py                    # 28 mutací, každá musí test shodit (po 4 paralelně)

# stránka v prohlížeči: sekce H souboru test_stul_host.js (PUT / DELETE se podstrčí přes page.route, nic se nezapisuje)
systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --setenv=HOME=/root --setenv=ONLY=H,C --working-directory=/opt/konfigurator \
    api/venv/bin/python3 scripts/2026-10-02_stul_testy/_most_stul.py scripts/2026-10-02_stul_testy/test_stul_host.js 4934
```

Testovací most `scripts/2026-10-02_stul_testy/_most_stul.py` uložené výchozí konfigurace NIKDY nenačítá (testy počítají s vestavěnými hodnotami); `VYCHOZI_TEST='{"<id produktu>": {...}}'` = test s uloženou.

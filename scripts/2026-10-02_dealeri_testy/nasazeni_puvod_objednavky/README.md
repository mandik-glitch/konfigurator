# Původ objednávky, aliasy hostů a přiřazení mini-shopu dealerovi (bot5, 2026-10-02)

**Stav: KÓD PŘIPRAVEN A OTESTOVÁN, NENASAZEN.** Návrh A-D schválil bot3, nasadit až po návrhu e-shopu od bot16 (pokyn bot3: „čekej s nasazením“).
Migrace JSOU V DB (`sql/2026-10-02_puvod_objednavky_storefront_dealer.sql`, `sql/2026-10-02_storefront_hosts.sql`, jen přidávají nullable sloupce a tabulky).

## Co to je
- `shop_orders.order_host` + `order_lang`: neměnný snímek hostu a jazyka mini-shopu (jazyk určuje DOMÉNA, `car_storefronts.lang`) při vzniku zákaznické objednávky (`orders_create`, objednávka z přijaté online nabídky). Ruční objednávka adminem puvod nemá.
- `storefront_hosts`: jeden storefront může mít víc hostů (hlavní `primary_domain` + aliasy, např. vlastní doména dealera na jeho žádost). `resolve_storefront` zkouší nejdřív hlavní host, pak alias. Objednávky ani přiřazení dealera se aliasem nemění (`storefront_id` stejné, `order_host` nese skutečný host).
- `storefront_dealers` + `shop_orders.dealer_source`: dealer se zapisuje na objednávku PŘI JEJÍM VZNIKU z přiřazení platného v tu chvíli (nikdy zpětně z domény); mini-shop s přiřazením rozhoduje i proti cookie z prokliku; vlastní nákup/testovací/neaktivní dealer = objednávka naše BEZ návratu ke kliku; bez přiřazení rozhoduje klik jako dosud.

## Nasazení (až po návrhu e-shopu od bot16)
`bash scripts/2026-10-02_dealeri_testy/nasazeni_puvod_objednavky/deploy_puvod_objednavky.sh` - vezme zámek, patchne `api/dealers.py`, `api/car_storefronts.py`, `api/orders.py` (patch skripty v této složce, kotvy podle HEAD),
pustí `test_storefront.py` a stávající dealerské testy nad živými soubory, přidá test do `run_all.sh` a commitne. Když kotva neodpovídá (někdo mezitím změnil soubor), skript se vrátí zpět a patch je třeba upravit.
Po nasazení serveru (03:30/12:30) ověřit `/api/dealer/me` = 401 a běžnou objednávku.

## Co NENÍ hotové (jen návrh, bot3: „zatím jen návrh“)
- **Zpětná provize** (jen na Robertův výslovný pokyn): admin akce s oprávněním `dealer_provize`, po jednotlivých objednávkách i podle období, POVINNÝ náhled (počet, součet bez DPH, odhad provize) → potvrzení s důvodem; zapíše `dealer_id`, `order_path='our'`, `dealer_source='retro'` a řádek do nové tabulky `dealer_attribution_log` (objednávka, starý a nový dealer, kdo, kdy, proč); objednávky přiřazené jinému dealerovi přeskočí. Vyúčtování se nepřepisují (nové řádky v dalším).
- **Admin endpointy** pro přiřazení (`assign_storefront`/`end_assignment` jsou jen knihovní funkce), pro aliasy hostů (`add_storefront_host`/`remove_storefront_host`) a filtr „Původ“ v seznamu objednávek.
- **nginx a TLS pro aliasy a subdomény dealerů**: `scripts/gen_storefront_vhosts.py` generuje `server_name {primary_domain} www.{primary_domain}` jen z `primary_domain`; alias (vlastní doména dealera) musí do `server_name` a potřebuje certifikát (Origin CA per doména/skupina) - infrastruktura (Robert/bot14, reload nginx blokuje sandbox).
- Dealerský storefront má mít `car_storefronts.kind='dealer'` (hub stránka značky vypisuje jen `kind='model'`, takže dealerské subdomény v hubu nebudou); admin API `kind` zatím nenastavuje.

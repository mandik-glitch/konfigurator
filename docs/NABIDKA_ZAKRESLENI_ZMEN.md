# Zakreslené změny v online nabídce

Robert (2026-10-07): „zakreslování změn komplet je na webu hotové, jen to přenést do online nabídky a to i pro stoly z generátoru“ (+ nabídky z karet Vandr).
Zákazník v online nabídce zakreslí požadovanou změnu do výkresu / 3D pohledu / renderu, připíše popis + kontakt a odešle; Logiman dostane poptávku s obrázky.

## Kdo co dělá
| Část | Soubor | Poznámka |
|---|---|---|
| Kreslení (nástroje, barvy, skládání výsledného obrázku) | `webapp/js/image-markup.js` | **stejný modul jako `product.html`** (Tužka, Kroužek, Škrtnout, Šipka, Text, 3 barvy, Zpět, Vymazat, Hotovo). Nabídka ho načítá líně (`/js/image-markup.js?v=3`, stejná verze = sdílená cache); při změně modulu zvednout `?v=` v `product.html` i `nabidka-online.html`. |
| Stránka nabídky | `webapp/nabidka-online.html` (blok „Zakreslené změny“ před `buildDeck`, `wireOfferMarkupRequests`) | tlačítka, sběr pohledů, odeslání |
| Backend | `api/offer_markup_requests.py` | `POST /api/public/offers/<token>/markup-requests`, `markup_requests_enabled(offer)` |
| Příznak pro stránku | `api/scene_offers.py` → `GET /api/public/offers/<token>` klíč `markup_requests` | vlastnost NABÍDKY (ne role) |

## Kdy se nástroj nabídne
- Jen když veřejná odpověď nabídky nese `markup_requests: true` = nabídka **z konfigurace stolu** (`offer_options.source == 'configurator'`) nebo **z karty Vandr** (`vandr_single_drawing`). Nabídky ze scény (1. větev) mají vlastní starší značkování (Kreslit/Označit/Uložit označení, značky vidí obě strany) a zůstávají beze změny.
- Statika je živá hned, API až při nasazení (0:00/12:30) → bez příznaku stránka nic neukáže (nic se nerozbije).
- U nabídek s příznakem se **starý štětec skryje** (lišta Kreslit/Označit na stránkách výkresů i tlačítka Označit/Uložit označení v dolní liště), aby nebyly dva různé nástroje.
- Admin („Zobrazit online“, `viewer_role == 'admin'`) tlačítka nevidí; backend jeho token odmítá (403).

## Kde jsou tlačítka
- `✏️ Zakreslit změnu` v popisku každé karty výkresu (`drawings_vandr`, `drawings_1/2`) a statických 3D náhledů (úhel 1/2) a u vizualizací (renders).
- Pod živým 3D prohlížečem (V3D): `✏️ Zakreslit změnu v tomto 3D pohledu` – snímek aktuálního pohledu přes `api.snapshot({type:'image/jpeg', width:1600})`, kamera `api.cameraInfo()` (jen informativně do `view.camera`). Tlačítko se ukáže až po načtení modelu (`omNaV3d(api)` volají `initViewerV3d`, `initViewerV3dBuf`).
- Nápověda pod nadpisem stránky; v dolní liště `📨 Odeslat změny (N)` (jen když je něco zakresleno).
- Tok jako na webu: kreslení → **Hotovo** → hned formulář (popis min. 3 znaky, e-mail, telefon) → Odeslat. Víc pohledů se sbírá (max 6 = `product_markups.MAX_VIEWS`), nahledy jdou odebrat ve formuláři. Při otevřeném kreslicím okně sipky nepřepínají stránky nabídky.

## Kontrakt POST
`multipart/form-data`: `email`, `phone` (9–15 číslic), `note` (3–2000), `website` (honeypot), `views` = JSON pole 1–6 objektů `{label, page?, view:{kind:'drawing'|'3d'|'render', key?, camera?}, marks:[…], image_w, image_h}`, soubory `composite_0…N-1` (JPEG/PNG ≤ 3 MB, zákresy jsou „vypálené“ v obrázku).
Odpověď 201 `{"status":"ok","views":N}`; 400 `{error, field}`; 403 admin token; 404 nabídka; 429 rate limit (3/h na token, 8/h na IP). Honeypot vrací 200 a nic neukládá.

## Co endpoint zapíše (jedna transakce, žádné DDL)
`crm_leads` (source `offer_markup`, předmět „Zakreslená změna k nabídce <číslo>“) + `crm_lead_messages` + přílohy do Drive složky poptávky + kopie do galerie poptávky (panel Fotky) + řádek `scene_offer_notes` (položka „Zakreslená změna“, vidět ve statistikách nabídky) + 2× `system_emails` (kind `scene_offer_markup`, **jen do fronty ke schválení**, pravidlo 16): upozornění dodavateli a potvrzení zákazníkovi.

## Testy
- Stránka: `scripts/2026-10-07_nabidka_zakresleni_stranka_testy/test_zakresleni_stranka.js` (32 kontrol, skutečná stránka + skutečný `image-markup.js`, živý 3D prohlížeč přes CDN + SwiftShader; `NABIDKA_HTML=<kandidát>`; mutace na původní verzi propadne).
- Backend: `scripts/2026-10-07_nabidka_zakresleni_testy/test_offer_markup_requests.py` (zastíněné tabulky, 95 kontrol) + `mutace.py`.
- Související: `OFFER_PAGE_KEYS` má od 2026-10-07 i `drawings_vandr` (dřív backend odmítal „Dotaz“, značky i statistiky ze stránky výkresů Vandr nabídky), `CLICK_TARGETS` má `markup_request_draw` / `markup_request_sent`.

## Nezapomenout
- Ověřit živě až po nasazení API: otevřít klientský odkaz nabídky z Vandr karty / ze stolu, zakreslit, odeslat → vznikne CRM poptávka s obrázky, 2 e-maily čekají na schválení. **Ostrou nabídku ani poptávku kvůli testu nezakládat.**
- Do 3D snímku se nepromítají kóty (texty jsou DOM štítky, viz `viewer3d.js` snapshot) – zákazník kreslí do pohledu bez kót.

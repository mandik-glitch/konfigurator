# Návrh: EUR, DPH, doklady a e-maily pro IT/EN web (vandrawee.it, vandrawee.eu)

Zadání: Robert 2026-10-08 (TASKS.md, commit 58c915bc; architektura jazyků `docs/web_jazyky/README.md`, bot16). Rozhodnuto: první vlna = kompletní e-shop, **prodej jen firmám** (VAT ID povinné při registraci, žádná spotřebitelská práva), ceny **EUR bez DPH**. Objednávky na EN/IT se **nezapínají** bez Robertova slova (jako `orders_enabled` u mini-shopů). Autor: bot5. Stav: NÁVRH, kód zatím žádný.

## 1. Co už existuje (mini-shop SK, bot5 2026-10-03) a použije se znovu

| Co | Kde |
|---|---|
| Cena v EUR = Kč ÷ kurz × (1 + marže), celé EUR; kurz = ruční `eur_rate` nebo živý kurz Fio, bez kurzu nebo marže **žádná cena** (pravidlo 9) | `api/miniweb_cena.py`; `web_sites.eur_rate`, `margin_pct` (bot16, NULL = bez ceny) |
| Objednávka hosta bez účtu, fakturační a dodací adresa, ověření VAT ID ve VIES | `api/miniweb_objednavky.py`, `api/miniweb_vies.py` |
| `shop_orders.vat_mode` (`reverse_charge` = DPH 0 %, jinak CZ sazba), `vat_check`, `order_host`, `order_lang`, `billing_dic` | sloupce v ostré DB |
| Doklad s DPH 0 %: sazba z `documents._order_vat_rate`, doložka `VAT_ZERO_NOTE` (§ 64), `document_note` s přepočtem měny | `api/documents.py`; znění doložky čeká na potvrzení účetní |
| Zákazník vidí EUR, **k úhradě v Kč = EUR × kurz** objednávky | mini-shop SK |

## 2. Rozhodnutí o modelu měny (k potvrzení účetní, ne Roberta)

**Varianta A – účetnictví zůstává v Kč, EUR je zákaznická cena (doporučuji, je hotová u mini-shopu SK).**
`shop_orders.total_czk`, doklady a bankovní párování (`bank_transactions`, Kč) se nemění. K objednávce se přidají jen **snapshot** `currency`, `eur_rate` (zamčený kurz v okamžiku objednávky) a `total_eur`, u řádků cena v EUR. Doklad nese Kč jako dosud a v poznámce přepočet („Celkem X EUR, kurz Y“). Zákazník platí v Kč podle kurzu objednávky.
+ nulová změna účetních výkazů, platí stávající SPAYD (`CC:CZK`), jednotná čísla dokladů.
− zákazník z Itálie platí v Kč (kurzové ztráty na jeho straně); dokladem v Kč se musí smířit.

**Varianta B – objednávka i doklad v EUR.** Doklad v EUR + přepočet základu a DPH do Kč kurzem určeným účetní. Platba v EUR na EUR účet (nutný druhý účet a párování plateb v EUR). Zásahy: `shop_orders` a `shop_documents` dostanou `currency` + částky v EUR, `documents.py` (zaokrouhlení, PDF, SPAYD jen pro CZK), `bank_transactions` párování EUR, `nabidka-online.html` (pevné `VAT_RATE_PCT = 21`, `fmtCzk`).
+ obvyklé pro zahraniční B2B. − dvojnásobná práce v kódu i účetnictví.

Doporučení: **A** pro první vlnu (jde nasadit rychle a bezpečně), B jen pokud to účetní výslovně požaduje.

## 3. DPH u firem (otázky pro účetní)

1. Firma z jiného členského státu s **platným VAT ID** (VIES OK) → DPH 0 %, doložka § 64 (`vat_mode = reverse_charge`) – hotové pro SK, znění doložky potvrdit; italská a jiná znění doložky (IT/EN doklad) – potřebuje překlad bot7 po schválení textu.
2. Firma **bez platného VAT ID** nebo ze země mimo EU – registrace odmítne (prodej jen firmám s VAT ID), nebo prodat s českou sazbou 21 %? Návrh: VAT ID je povinné a ověřené, jinak objednávku nepřijmout.
3. VIES nedostupné: objednávka se přijme se `vat_check = nelze_overit` a čeká na ruční ověření (stejně jako mini-shop), DPH se dopočítá až po ověření.
4. Kurz pro Kč přepočet (varianta B) nebo pro zákaznickou cenu (varianta A): kurz objednávky (Fio, snapshot) × ČNB ke dni plnění – který platí na dokladu?
5. Souhrnné a kontrolní hlášení: stačí `billing_dic` + `vat_check` + země (sloupec s kódem země doplníme), nebo je potřeba i kód plnění?
6. Doprava a clo do Itálie/EU: sazby dopravy mimo CZ řeší odděleně (Toptrans pásma jsou pro SK).

## 4. Co se mění v kódu (varianta A, bot5; všechno za vypínačem)

1. `web_sites` + sloupec `orders_enabled TINYINT(1) NOT NULL DEFAULT 0` (migrace, zpětně kompatibilní). Dokud je 0, košík na `.it`/`.eu` objednávku nepřijme (jako `orders_enabled` u mini-shopů).
2. `shop_orders` + `currency CHAR(3) NOT NULL DEFAULT 'CZK'`, `eur_rate DECIMAL(10,4) NULL`, `total_eur DECIMAL(12,2) NULL`, `order_country CHAR(2) NULL`; `order_host`, `order_lang`, `vat_mode`, `vat_check` už jsou. Doklady beze změny schématu (přepočet do `document_note`).
3. `POST /api/orders` na hostu z `web_sites`: ceny v EUR přes `miniweb_cena` (kurz + marže), VIES, `vat_mode`, uložení snapshotu; stávající CZ cesta se nemění (host není v `web_sites` = dnešní chování).
4. `documents.py`: VAT_RATE per objednávka už je (`_order_vat_rate`); doplnit jazyk dokladu z `order_lang` (PDF popisky, doložka), `nabidka-online.html` načítat sazbu z nabídky místo pevných 21 %.
5. E-maily: jazyk podle `order_lang`; šablony ve slovníku `{cs, en, it}` (zdroj českých textů níže), fallback na češtinu (e-mail se nikdy neodešle prázdný). Schvalovací fronta (pravidlo 16) a pravidlo „e-mail s dokladem jen po schválení dokladu“ platí beze změny.
6. Admin: původ (host, jazyk, měna) u objednávky, přehledy dál v Kč s EUR v detailu.

## 5. České zdroje k překladu (pro bot7), soubor:klíč

- `api/orders.py::_order_confirmation_email_body` (předmět „Potvrzení přijetí objednávky“ + tělo, řádek „Položky objednávky“, „Celkem“, upozornění na chybějící zboží)
- `api/orders.py::_status_change_email_body` + `STATUS_LABELS_CZ` (nova, potvrzena, ceka_na_zbozi, pripravit, expedovana, fakturovana, zrusena)
- `api/emails.py::default_subject_body_for_document` (4 typy: proforma_invoice, payment_tax_document, invoice, delivery_note; věty „K úhradě“, „NEPLAŤTE“, „předána k expedici“) a `documents.DOCUMENT_TYPE_LABELS`
- `api/emails.py::_default_subject_body_order_confirmation` (ruční potvrzení objednávky z adminu)
- PDF dokladů `api/documents.py::render_document_pdf` (nadpisy, sloupce tabulky, „Dodavatel“/„Odběratel“, DPH, splatnost, VS, bankovní spojení) a `VAT_ZERO_NOTE` (po potvrzení znění účetní)
- Hlášky košíku a objednávky ve webu (`10_ui`) bot7 už má, chybové kódy z API (`price_changed`, `vat_id_invalid` …) se mapují na jeho slovník.

### Stav překladů šablon (bot7, commit ebb77f20)
Sešit `docs/web_jazyky/12_sablony.json` (77 položek) je přeložen EN + IT. K ověření účetní: popisky na dokladech pro EN/IT – `pdf:ico` = „Company reg. no.“ / „N. registro imprese“, `pdf:dic` = „VAT ID“ / „Partita IVA“; IT název dodacího listu „Documento di trasporto“; částky se v šablonách skládají v kódu s měnou hostu (v textech sešitu symbol měny není). Zápatí PDF `pdf:paticka` je v EN/IT neutrální („Issued by the logiman.cz system“) – české „…systémem konfigurátoru logiman.cz“ se sjednotí v kódu při zapojení překladu. Doložka DPH 0 % (VAT_ZERO_NOTE) se překládá až po znění od účetní.

## 6. Pořadí

1. Potvrzení účetní: varianta A/B, doložka, VIES/ruční ověření (otázky v bodě 3). **Dokud nepřijde, kód objednávek nepíšu.**
2. Migrace (nullable, neškodné) + `orders_enabled = 0`.
3. Ceny EUR v košíku a v detailu produktu (read-only, bez objednávky) – to jde už před odpovědí účetní, pokud Robert chce vidět ceny na hostech v `draft`.
4. Objednávka + doklady + e-maily; testy nad dočasnými tabulkami; zapnutí `orders_enabled` jen na Robertův pokyn.

-- Jazykove verze hlavniho webu (EN = vandrawee.eu, IT = vandrawee.it) - bot16, 2026-10-08 (Robert; architektura docs/web_jazyky/README.md).
-- web_sites: host -> jazyk, mena, rezim ceny, stav (draft = jen zamestnanci pres ?jazyk=, live = verejne), indexace. Hosty, ktere zde nejsou (autovestavby.logiman.cz, logiman.cz, storefronty, mini-shopy), se nemeni.
-- web_i18n:  preklady z sesitu docs/web_jazyky/*.json (klic "kod:pk:pole" nebo "ui:<hash12>:<kontext>"), jedina cesta zapisu je scripts/web_jazyk_import.py.
-- Nova tabulka, nikdo ji zatim necte; zpetne kompatibilni.
-- Kurz a marze se NIKDY nedavaji do kodu (WORKFLOW pravidlo 9): eur_rate NULL = zivy kurz Fio (miniweb_cena), margin_pct NULL = ZADNA cena.

CREATE TABLE IF NOT EXISTS web_sites (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    host            VARCHAR(190) NOT NULL,
    canonical_host  VARCHAR(190) NULL COMMENT 'alias (www.) -> hlavni host, NULL = tento host je hlavni',
    lang            CHAR(2) NOT NULL,
    locale          VARCHAR(10) NOT NULL,
    currency        CHAR(3) NOT NULL DEFAULT 'EUR',
    price_mode      ENUM('excl_vat','incl_vat') NOT NULL DEFAULT 'excl_vat',
    eur_rate        DECIMAL(10,4) NULL COMMENT 'Kc za 1 EUR, NULL = zivy kurz Fio',
    margin_pct      DECIMAL(6,2) NULL COMMENT 'NULL = zadna cena (pravidlo 9)',
    status          ENUM('draft','live') NOT NULL DEFAULT 'draft',
    indexable       TINYINT(1) NOT NULL DEFAULT 0 COMMENT 'smi byt 1 jen po zelene brane vse-nebo-nic',
    x_default       CHAR(2) NOT NULL DEFAULT 'en',
    created_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uq_web_sites_host (host)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS web_i18n (
    klic        VARCHAR(190) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    lang        CHAR(2) CHARACTER SET ascii NOT NULL,
    `text`      MEDIUMTEXT NOT NULL,
    h           CHAR(10) CHARACTER SET ascii NOT NULL DEFAULT '' COMMENT 'sha1(cs)[:10] v okamziku prekladu (sesit bot7)',
    zastarale   TINYINT(1) NOT NULL DEFAULT 0 COMMENT '1 = cestina se od prekladu zmenila (zmena v sesitu), preklad se nepouzije',
    updated_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (klic, lang),
    KEY idx_web_i18n_lang (lang)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- hosty (vsechny jen DRAFT: verejne se nic nezmeni, dokud Robert neschvali nahled a status nepreklopime na live)
INSERT IGNORE INTO web_sites (host, canonical_host, lang, locale) VALUES
    ('vandrawee.eu', NULL, 'en', 'en-GB'),
    ('www.vandrawee.eu', 'vandrawee.eu', 'en', 'en-GB'),
    ('vandrawee.it', NULL, 'it', 'it-IT'),
    ('www.vandrawee.it', 'vandrawee.it', 'it', 'it-IT');

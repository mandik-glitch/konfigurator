-- Vicero dodacich adres na zakaznika - Robert pres bot3, 2026-09-29:
-- "u zakazniku potrebujeme mit moznost vicero dodacich adres, asi na
-- zalozky."
--
-- shop_customers.delivery_address/_street/_city/_zip ZUSTAVAJI BEZE
-- ZMENY (viz api/customers.py _PROFILE_FIELDS) - je to porad JEDINA
-- adresa, kterou cte checkout (webapp/product.html), objednavka
-- (api/orders.py) i doklady (api/documents.py). Tahle nova tabulka je
-- ADRESAR NAD tim - kdyz ma zakaznik >1 adresu, radek s is_default=1
-- se zrcadli DO shop_customers.delivery_* (viz
-- api/customers.py::_sync_default_address), takze VSECHNA existujici
-- mista, ktera cetla shop_customers primo (dohledano pred navrhem:
-- api/orders.py, api/documents.py, webapp/product.html,
-- webapp/admin/js/objednavky-doklady.js), funguji dal BEZE ZMENY -
-- jen ted jde prepnout, KTERA adresa je "ta" delivery_address, misto
-- psani znovu pri kazde zmene.
-- COLLATE utf8mb4_0900_ai_ci (NE _unicode_ci, i kdyz je to "typicky"
-- vzor v ostatnich nedavnych migracich v tomhle adresari) - overeno
-- primo: shop_customers/shop_orders uz bezi na _0900_ai_ci (MySQL 8
-- vychozi), FK JOIN mezi ruznymi collations shodil "Illegal mix of
-- collations" hned pri prvnim ostrem pouziti (_sync_default_address).
CREATE TABLE shop_customer_addresses (
  id INT AUTO_INCREMENT PRIMARY KEY,
  customer_id INT NOT NULL,
  label VARCHAR(100) NOT NULL,
  street VARCHAR(255) NULL,
  city VARCHAR(120) NULL,
  zip VARCHAR(6) NULL,
  is_default TINYINT(1) NOT NULL DEFAULT 0,
  sort_order INT NOT NULL DEFAULT 0,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  CONSTRAINT fk_sca_customer FOREIGN KEY (customer_id) REFERENCES shop_customers(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Zpetne naplneni: kazdy existujici zakaznik se svou dnesni JEDINOU
-- delivery adresou (pokud nejakou ma) dostane 1 radek oznaceny jako
-- vychozi - adresar tak od prvni chvile obsahuje to, co uz v profilu
-- bylo, misto aby zacinal prazdny a vypadal, ze se stavajici adresa
-- ztratila.
-- delivery_street/city casto NULL (hodne zakazniku ma jen volny text
-- delivery_address, ne strukturovana pole, viz api/customers.py::
-- _compose_address) - kdyby se do noveho radku dala jen NULL/NULL
-- struktura, budouci _sync_default_address by pri prvni editaci
-- teto adresy prepsala delivery_address na PRAZDNO (compose z
-- prazdneho street+city vraci fallback=NULL) a skutecny text adresy
-- by se ztratil. Proto street = COALESCE(delivery_street,
-- delivery_address) - kdyz strukturovana pole chybi, cely volny text
-- se ulozi do street (o par znaku vic nez cisty street, ale nic
-- neztrati).
INSERT INTO shop_customer_addresses (customer_id, label, street, city, zip, is_default)
SELECT id, 'Doručovací adresa', COALESCE(delivery_street, delivery_address), delivery_city, delivery_zip, 1
FROM shop_customers
WHERE delivery_address IS NOT NULL AND delivery_address <> '';

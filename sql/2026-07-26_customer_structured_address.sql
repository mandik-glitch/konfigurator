-- Strukturovana adresa zakaznika (Robert: "pri zakladani noveho
-- zakaznika: zvlast PSC, zvlast Mesto i Ulici, zatrzitko na stejnou
-- dodaci adresu s fakturacni, vsechna pole povinna krome poznamky, u
-- firmy jmeno zaznacit interne ze se nema prenaset do faktury a na
-- doklady"). Puvodni volne-textove billing_address/delivery_address
-- ZUSTAVAJI (zpetna kompatibilita s existujicimi konzumenty - napr.
-- zakaznicky self-service checkout v category.html/product.html,
-- ktery dal posila jen volny text) - nove sloupce jsou navic, admin
-- formular "Pridat zakaznika" je pouziva jako zdroj pravdy a
-- billing_address/delivery_address si z nich sam sklada pro zpetnou
-- kompatibilitu se zobrazenim jinde.

ALTER TABLE shop_customers
  ADD COLUMN billing_street VARCHAR(255) DEFAULT NULL AFTER billing_address,
  ADD COLUMN billing_city VARCHAR(120) DEFAULT NULL AFTER billing_street,
  ADD COLUMN billing_zip VARCHAR(6) DEFAULT NULL AFTER billing_city,
  ADD COLUMN delivery_street VARCHAR(255) DEFAULT NULL AFTER delivery_address,
  ADD COLUMN delivery_city VARCHAR(120) DEFAULT NULL AFTER delivery_street,
  ADD COLUMN delivery_same_as_billing TINYINT(1) NOT NULL DEFAULT 0 AFTER delivery_zip,
  ADD COLUMN hide_name_on_documents TINYINT(1) NOT NULL DEFAULT 0
    COMMENT 'U firmy: jmeno kontaktni osoby (full_name) se NEMA pouzit jako nazev na fakture/dokladech - pouzit company_name'
    AFTER note;

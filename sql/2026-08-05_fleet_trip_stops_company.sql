-- Zjednoduseni zastavky "u zakaznika" (Robert 2026-08-05: "zastavka
-- muze byt take nejaky zakaznik, nebo obchodni partner, takze se v
-- takove zastavce vyzada Nazev firmy a Mesto"). Puvodni navrh pocital
-- s vyhledavanim v existujici kartotece `shop_customers` -
-- obchodni partner v ni ale nemusi vubec byt, takze propojeni na
-- customer_id se rusi uplne (nebyla to jeste nasazena/pouzivana
-- funkce, zadna data k migraci) a zustava jen volny text.
ALTER TABLE fleet_trip_stops
  DROP FOREIGN KEY fk_fts_customer,
  DROP COLUMN customer_id,
  CHANGE COLUMN customer_name_freetext company_name VARCHAR(200) NULL;

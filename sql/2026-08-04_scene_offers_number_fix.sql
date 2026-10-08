-- Oprava: scene_offers.offer_number byl VARCHAR(4), ale
-- scene_offers.py::scene_offers_create() uklada offer_number VCETNE
-- prefixu ("RM" + 4 cislice = "RM0010", 6 znaku) - na rozdil od
-- crm_quotes.quote_number, ktery drzi JEN cislo bez prefixu. Odhaleno
-- pri prvnim testovacim zapisu (1406 Data too long).
ALTER TABLE scene_offers MODIFY COLUMN offer_number VARCHAR(10) NOT NULL;

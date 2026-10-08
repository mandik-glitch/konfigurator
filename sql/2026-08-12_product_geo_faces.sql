-- Robert 2026-08-12: "u nekterych dilu potrebuji tlacitko, ktere oznaci
-- plochy objektu podle GEOMETRIE (ne podle 6 pevnych smeru obalky) a ja
-- to levym klikem mysi jen potvrdim - myslim behem uceni [napojeni]".
-- Kulate/nepravidelne dily (cepy...) nemaji smysluplnych 6 "krabicovych"
-- ploch jako uhelnik - potrebuji skutecne rovinne plochy z mesh geometrie.
-- Ulozeno v LOKALNIM prostoru dilu (stejna konvence jako connectorsLocal),
-- takze je nezavisle na tom, jak je dil zrovna ve scene otoceny/umisteny.
ALTER TABLE shop_products ADD COLUMN geo_faces_json TEXT DEFAULT NULL

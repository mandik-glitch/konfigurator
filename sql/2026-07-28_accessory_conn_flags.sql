-- bot1, 2026-07-28. Robert: "nachystej abych mohl odklikat, ktere spoje
-- jsou funkcni, ostatni zrusis" - pro kazdy produkt (prislusenstvi) v
-- katalogu jde ted ulozit, ktere z jeho 6 univerzalnich bounding-box
-- konektoru (viz computeConnectorsLocal ve scene.html) jsou SKUTECNE
-- pouzitelne rovne montazni plochy (napr. u uhelnikove spojky asi jen 2
-- ze 6 - ostatni jsou zaoblene/nefunkcni z hlediska montaze, i kdyz je
-- bounding-box "vidi" jako plochou stenu). NULL = jeste nezkontrolovano,
-- nabizet vsech 6 (puvodni chovani, zpetne kompatibilni).
ALTER TABLE shop_products
  ADD COLUMN accessory_conn_enabled JSON NULL AFTER glb_file;

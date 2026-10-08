-- Robert, 2026-09-29: "kdyz budu opakovane klikat spustit render a pritom
-- menit napr HDri nebo jine parametry, nech se to ukládá do fronty" -
-- kazde kliknuti na "Spustit testovaci render" si drzi SVUJ otisk
-- nastaveni panelu (radky tabulky materialu, azimut, kryci listy...) v
-- okamziku kliknuti. Bez toho automat bral az v okamziku zarazeni
-- AKTUALNI ulozeny stav panelu, takze pozdejsi zmena parametru
-- zmenila i uz cekajici testy.
ALTER TABLE render_hdri_test_requests
  ADD COLUMN nastaveni_json MEDIUMTEXT NULL;

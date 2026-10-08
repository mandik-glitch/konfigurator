-- Doplneni chybejicich slovnich tvaru pro klasifikator "doklad" - bot23, 2026-08-18.
--
-- Kontext (Robert pres bot3, navazne na analyzu "chybejici e-maily"):
-- realna faktura od Ardea-cz ("Danovy doklad k prijate platbe.") skoncila
-- klasifikovana jako "jine" mistro "doklad", protoze crm.classify_incoming_email
-- pocita skore z PRESNYCH shod tokenu (viz crm.py::_tokenize - tokenizer
-- diakritiku NEODSTRANUJE, "Danovy" -> token "danovy" jen po lowercase,
-- s diakritikou zustava "daňový") a v crm_classifier_words tahle slova
-- (vc. holeho "doklad" bez skloneni) proste chybela - vsechny 4 tokeny
-- predmetu ("doklad", "daňový", "přijaté", "platbě") mely skore 0/0/0,
-- takze classify_incoming_email() spadla na vychozi "jine" (zadna
-- kategorie nemela kladne skore, ne remiza).
--
-- Soucasne zjisteno: par UZ existujicich radku bylo naseedovano v ASCII
-- podobe bez diakritiky ("variabilni", "uhrady", "uhradu"), i kdyz
-- realny tokenizer produkuje tvar S diakritikou ("variabilní", "úhrady",
-- "úhradě") - takze tyhle puvodni radky realny text nikdy netrefi.
-- Puvodni ASCII radky NEJSOU mazany (mohly by sedet u jineho zdroje
-- textu bez diakritiky), jen se doplnuji spravne tvary vedle nich.
--
-- ON DUPLICATE KEY UPDATE pouziva GREATEST() - nikdy nesnizi uz existujici
-- (vyssi) skore, jen doplni chybejici/nizsi.
--
-- Pouziti: python api/db_migrate.py sql/2026-08-18_crm_classifier_words_doklad_forms.sql

INSERT INTO crm_classifier_words (word, poptavka_count, jine_count, doklad_count) VALUES
    ('doklad', 0, 0, 5),
    ('daňový', 0, 0, 3),
    ('přijaté', 0, 0, 2),
    ('platbě', 0, 0, 2),
    ('variabilní', 0, 0, 4),
    ('úhrady', 0, 0, 3),
    ('úhradě', 0, 0, 3)
ON DUPLICATE KEY UPDATE
    doklad_count = GREATEST(doklad_count, VALUES(doklad_count));

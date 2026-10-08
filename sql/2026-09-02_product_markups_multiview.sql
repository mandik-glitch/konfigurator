-- v2 "Zakreslena pripominka" (bot14, 2026-09-02, Robert pres bot3):
-- jedna pripominka muze mit VICE pohledu ("Zajemce muze zakreslit, co
-- zamysli, ve vice pohledech a pokazde to bude jinak, protoze natoci
-- pohled jinak"). product_markups zustava 1 radek = 1 pohled, novy
-- submission_id (uuid4 hex) sdruzuje vsechny pohledy JEDNE odeslane
-- pripominky (sdileji i lead_id/note/contact_* - viz api/product_markups.py).
ALTER TABLE product_markups
    ADD COLUMN submission_id CHAR(32) NOT NULL AFTER product_id,
    ADD COLUMN view_index TINYINT NOT NULL DEFAULT 0 AFTER submission_id,
    ADD INDEX idx_product_markups_submission (submission_id);

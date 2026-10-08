-- Robert 2026-09-25: "do naseho stromu jen pridat kategorie a podkategorie
-- ktere jsou na logiman.cz... dej jim jinou barvu textu at to mohu
-- rozeznat a posoudit jestli to tak muzeme nechat" - docasny priznak,
-- dokud Robert nerozhodne (pak se rucne vypne / kategorie smaze).
ALTER TABLE content_categories
    ADD COLUMN pending_review TINYINT(1) NOT NULL DEFAULT 0 AFTER is_visible;

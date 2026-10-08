-- Archivace konverzaci v Podpore (Emaily prichozi) - bot23, 2026-08-17.
--
-- Robert pres bot3: chybi moznost "Archivovat" vedle Uzavrit/Otevrit
-- znovu/Smazat vybrane - archivovana konverzace ma zustat v DB (na
-- rozdil od Smazat), jen se vyradit z bezneho pohledu.
--
-- Stejny vzor jako crm_leads.archived (sql u crm.py, "Zajem z homepage"
-- panel Poptavky) - NEZAVISLY boolean sloupec, ne novy status. status
-- ('open'/'closed') a archived jsou dve nezavisle osy: konverzace muze
-- byt archivovana v jakemkoli stavu, presne jako u poptavek. Bezne
-- zalozky (Vse/Otevrene/Uzavrene) vzdy filtruji archived=0, samostatna
-- zalozka "Archiv" ukazuje archived=1 (viz api/support.py
-- support_admin_list).
ALTER TABLE shop_support_conversations
  ADD COLUMN archived TINYINT(1) NOT NULL DEFAULT 0 AFTER status;

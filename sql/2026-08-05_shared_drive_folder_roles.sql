-- Omezeni pristupu ke slozkam Sdileneho disku podle role (bot4,
-- 2026-08-05). Robert: "ve sdilenem disku potrebujeme resit role podle
-- slozek" - upresneno: podle role (ne jednotlivych uzivatelu), pravidlo
-- se nastavuje jen na slozkach NEJVYSSI urovne (parent_folder_id IS
-- NULL) - podslozky ho vzdy dedi od sve nejvyssi predchudkyne. Slozka
-- bez pristupu neni ze stromu schovana, jen uzamcena (nejde otevrit).
-- Admin vidi vzdy vsechno, manazer/mistr/asistent se ridi stejnymi
-- pravidly jako ostatni role.
--
-- Chybejici radky pro danou top-level slozku = NEOMEZENA (viditelna
-- vsem s pravem sdileny_disk/zobrazit) - zpetne kompatibilni se
-- vsemi slozkami vytvorenymi pred timhle datem.
CREATE TABLE shared_drive_folder_roles (
  folder_id INT NOT NULL,
  role VARCHAR(30) NOT NULL,
  PRIMARY KEY (folder_id, role),
  CONSTRAINT fk_sdfr_folder FOREIGN KEY (folder_id) REFERENCES shared_drive_folders(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

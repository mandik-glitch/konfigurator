-- Podpora - rozsireni na anonymni navstevniky - bot1, 2026-07-25.
-- Robert: "[widget i mimo prihlaseny konfigurator, napr. realizace.html] ano"
--
-- realizace.html (verejna fotogalerie realizaci) NENI za loginem (na
-- rozdil od scene.html, rozhodnuti 2026-07-23 se tyka jen konfiguratoru).
-- Anonymni navstevnik je identifikovan Flask session cookie (session
-- funguje i bez prihlaseni, FLASK_SECRET_KEY uz je nastaveny) - viz
-- support.py _support_identity(). customer_user_id proto musi byt
-- nullable; guest_session_id drzi nahodny token z cookie pro dohledani
-- konverzace pri dalsi navsteve ze stejneho prohlizece.

ALTER TABLE shop_support_conversations
  MODIFY COLUMN customer_user_id INT NULL,
  ADD COLUMN guest_session_id VARCHAR(64) NULL AFTER customer_user_id,
  ADD KEY idx_guest_session (guest_session_id),
  ADD CONSTRAINT chk_shop_support_identity
    CHECK (customer_user_id IS NOT NULL OR guest_session_id IS NOT NULL);

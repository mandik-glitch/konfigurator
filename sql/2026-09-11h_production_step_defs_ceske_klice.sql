-- Sjednoceni klicu rucnich kroku s PLAN_TVORBY_SESTAV.md (bot4 review
-- 2026-09-11): v DB byly anglicky, v planu cesky - bot ridici se planem
-- by dostal 400 "Neznamy krok". Plan je specifikace, kod se ridi jim.
-- production_step_checks ma 0 radku (zadarmo, bez migrace dat).
UPDATE production_step_defs SET step_key='geometrie_zkontrolovana' WHERE step_key='scene_geometry_checked';
UPDATE production_step_defs SET step_key='vycisteno' WHERE step_key='cleaned_legacy_parts';
UPDATE production_step_defs SET step_key='vzor_prestaven' WHERE step_key='rebuilt_per_template';
UPDATE production_step_defs SET step_key='texty_hotove' WHERE step_key='texts_done';
UPDATE production_step_defs SET step_key='prvni_otocka_schvalena' WHERE step_key='first_turntable_approved';

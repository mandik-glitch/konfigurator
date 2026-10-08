-- web_i18n.cs: cesky zdroj v okamziku importu (bot16, 2026-10-08). Slovnik textu stranek se v prohlizeci hleda podle normalizovane cestiny (klic ui:<hash12>:<kontext> ceskou vetu neobsahuje),
-- a pro kontrolu / budouci admin nahled je cestina u prekladu vzdy po ruce. Plni scripts/web_jazyk_import.py.
ALTER TABLE web_i18n ADD COLUMN cs MEDIUMTEXT NULL AFTER lang;

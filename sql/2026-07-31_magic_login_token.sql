-- Robert 2026-07-31: "porad zapominam heslo, chci magic prostě přístup
-- bez hesla" - trvaly (nevyprsivajici, dokud se znovu nevygeneruje)
-- prihlasovaci odkaz pro fotoapku (capture.html?magic=<token>).
-- Uklada se jen HASH tokenu (sha256), ne token samotny - stejny princip
-- jako password_hash, i pri unikuni DB by nikdo neziskal pouzitelny token.
ALTER TABLE app_users ADD COLUMN magic_token_hash VARCHAR(64) NULL;

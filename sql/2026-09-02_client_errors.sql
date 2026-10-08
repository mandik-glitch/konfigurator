-- JS error beacon z prohlizecu (bot5, 2026-09-02, "kontrolni mechanismy"
-- od Roberta pres bot3, dil J). webapp/js/client-errors.js posila
-- window.onerror/unhandledrejection/chyby nacteni zdroju sem
-- (POST /api/client-errors, bez auth, viz api/client_errors.py).
-- fingerprint = hash(message+source+line) - stejna chyba z ruznych
-- navstev/IP se agreguje do jednoho radku (count/last_seen), ne
-- nekonecne rostouci tabulka jednotlivych udalosti.
CREATE TABLE client_errors (
    id INT AUTO_INCREMENT PRIMARY KEY,
    fingerprint CHAR(64) NOT NULL,
    message VARCHAR(500) NOT NULL,
    source VARCHAR(500) NULL,
    line INT NULL,
    col INT NULL,
    stack TEXT NULL,
    url VARCHAR(500) NOT NULL,
    user_agent VARCHAR(300) NULL,
    ip_hash CHAR(64) NULL,
    count INT NOT NULL DEFAULT 1,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_seen_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_client_errors_fingerprint (fingerprint),
    INDEX idx_client_errors_last_seen (last_seen_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

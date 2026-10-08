-- Robert 2026-07-31: propojeni se socialnimi sitemi - "planovane posty".
-- Zatim jen struktura (admin muze pripravovat obsah + datum), skutecne
-- odesilani na Facebook API az az bude k dispozici Page Access Token
-- (viz AGENTS_LOG.md).
CREATE TABLE IF NOT EXISTS social_scheduled_posts (
    id INT AUTO_INCREMENT PRIMARY KEY,
    platform VARCHAR(30) NOT NULL DEFAULT 'facebook',
    message TEXT NOT NULL,
    image_filename VARCHAR(255) DEFAULT NULL,
    scheduled_at DATETIME NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'planned',
    created_by INT DEFAULT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    sent_at DATETIME DEFAULT NULL,
    error_message TEXT DEFAULT NULL,
    KEY idx_social_scheduled_posts_status_time (status, scheduled_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

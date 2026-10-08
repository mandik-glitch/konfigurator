CREATE TABLE IF NOT EXISTS scene_offer_renders (
  id INT AUTO_INCREMENT PRIMARY KEY,
  offer_id INT NOT NULL,
  stored_filename VARCHAR(255) NOT NULL,
  caption VARCHAR(200) DEFAULT NULL,
  mesh_group INT DEFAULT NULL,
  sort_order INT NOT NULL DEFAULT 0,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  KEY idx_offer (offer_id, sort_order),
  CONSTRAINT fk_scene_offer_renders_offer FOREIGN KEY (offer_id) REFERENCES scene_offers(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4

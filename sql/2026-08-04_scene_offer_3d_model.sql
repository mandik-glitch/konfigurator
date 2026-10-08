-- Zivy 3D model (Robert: "3D model ne jako nahledy ale rovnou jako
-- zivy model") - NULLABLE: chybi u starsich nabidek, u selhaneho
-- exportu/uploadu, nebo kdyz WebGL export z jakehokoli duvodu vynecha
-- - frontend pak spolehlive spadne zpet na ploche view_3d_a/b.
ALTER TABLE scene_offers ADD COLUMN view_3d_model VARCHAR(255) NULL AFTER view_3d_b;

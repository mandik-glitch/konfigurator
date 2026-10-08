-- Barva rezaneho kusu podle ZAKAZKY (bot4, "optimizer", 2026-07-26).
-- Robert: "barva obřezávaného dílu nech se ošetří podle zakázky... každá
-- objednávka, která potřebuje nářezy, bude mít přiřazenou nějakou barvu
-- a popis (číslo objednávky) dílu uprostřed... když se to odškrtne jako
-- hotové, barva se uvolní pro příští řezný plán a jinou objednávku."
--
-- Reseni: paleta barev (viz cutting.py ORDER_COLOR_PALETTE / admin.html
-- CP_COLORS - oba seznamy udrzovany stejne), kazde objednavce s aspon
-- jednim NEDOKONCENYM (pending) kusem je prirazena jedna trvala barva
-- (radek v teto tabulce). Jakmile uz objednavka nema zadny pending kus
-- (vsechny tyce/desky s jejimi kusy jsou 'done'), radek se SMAZE - barva
-- se tim uvolni pro jinou objednavku pri pristim generovani/cteni planu
-- (viz cutting.py:_sync_order_colors, volano z GET /api/admin/cutting-plan,
-- POST .../generate a PATCH .../units/<id>).
--
-- Pouziti (na DB instance "Configurator", xebyhtfeaj @ 80.211.73.226):
--   mysql -h 80.211.73.226 -u <user> -p xebyhtfeaj < 2026-07-26_order_colors.sql

CREATE TABLE IF NOT EXISTS shop_cutting_order_colors (
    order_number VARCHAR(40) NOT NULL PRIMARY KEY,
    color        VARCHAR(10) NOT NULL,
    assigned_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

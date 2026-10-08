-- Robert: "do zalozky Souvisejici, pridej moznost vlozit do detailu
-- produktu video jako embed z youtube" - rozsireni doc_type o 'youtube'
-- (vedle existujiciho nahravaneho souboru 'video'/mp4). U 'youtube'
-- radku se sloupec filename nepouziva pro soubor na disku, ale pro
-- extrahovane YouTube video ID (11 znaku) - viz api/products.py
-- shop_product_document_youtube_add().
ALTER TABLE shop_product_documents
    MODIFY doc_type ENUM('pdf','video','youtube') NOT NULL;

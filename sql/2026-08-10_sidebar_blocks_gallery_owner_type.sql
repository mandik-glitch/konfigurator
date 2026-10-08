-- bot5 2026-08-10 - "sidebar_block" jako dalsi platna hodnota
-- content_gallery_items.owner_type, aby sel pouzit stejny vzor
-- vkladani obrazku do tela textu (Quill editor) jako u homepage_blocks
-- (viz hpbQuillImageHandler v admin.html, obdoba sbbQuillImageHandler).
ALTER TABLE content_gallery_items
    MODIFY COLUMN owner_type ENUM('category','product','document','stock_movement','po_item','order','inbox','lead','homepage_block','sidebar_block') NOT NULL;

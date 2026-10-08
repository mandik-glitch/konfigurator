-- Robert 2026-08-12: "cep potrebuje byt zanoreny castecne do profilu,
-- protoze tam je zasroubovany... tyto pozice potrebuji tlacitkem
-- potvrdit, potom uz je to na tobe". Signed odsazeni (mm) podel osy
-- pripojeni (kladne = vic ven, zaporne = zanoreno do profilu),
-- aplikuje se AZ PO standardnim flush osazeni (Volne celo).
ALTER TABLE shop_products ADD COLUMN attach_offset_mm DECIMAL(6,2) DEFAULT 0

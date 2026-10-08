# Obnova projektu ze zálohy (zaloha_RRRR-MM-DD.tar.gz)

Návod pro bota/člověka, který dostane denní zálohu (viz
`scripts/daily_backup.py`) a má na čistém VPS (Ubuntu 24.04) postavit
živý systém. Záloha obsahuje VŠECHNA data (kód vč. git historie,
nahrané soubory, api/.env s přístupy, dump DB, nginx+systemd config),
ale NE nainstalovaný software - ten se instaluje podle tohoto návodu.

## 1. Rozbalení

```bash
tar xzf zaloha_RRRR-MM-DD.tar.gz -C /opt/     # vznikne /opt/konfigurator
cd /opt/konfigurator
```

## 2. Systémové balíčky

```bash
apt update && apt install -y nginx python3-venv python3-pip \
  mysql-client blender fonts-roboto \
  libpango-1.0-0 libpangocairo-1.0-0 libcairo2 libgdk-pixbuf-2.0-0  # WeasyPrint
python3.12 -m pip install numpy --break-system-packages  # pro Blender FBX export
# Node.js 24 (jen pro vyvojove kontroly node --check, neni nutny pro beh)
```

## 3. Python venv (v záloze záměrně není)

```bash
cd /opt/konfigurator/api
python3 -m venv venv
venv/bin/pip install -r requirements.txt
```

`step_venv` (převod STEP souborů) - viz komentáře v
`api/step_convert.py`, samostatná instalace; bez ní funguje vše kromě
uploadu .stp/.step.

## 4. Databáze

DB běží na EXTERNÍM serveru (viz DB_HOST v `api/.env`). Dvě situace:

- **Externí DB server žije** → nic neobnovuj, `api/.env` už na něj
  ukazuje. Dump v záloze je jen pojistka.
- **DB je ztracená** → nový MySQL 8, pak:
  ```bash
  zcat db_xebyhtfeaj_RRRR-MM-DD.sql.gz | mysql -h <novy-host> -u <user> -p <databaze>
  ```
  a přepsat DB_HOST/DB_USER/DB_PASSWORD/DB_NAME v `api/.env`.

## 5. Práva souborů

```bash
chown -R www-data:www-data /opt/konfigurator
```

## 6. Systemd + nginx (konfigurace je v archivu ve složce system-config/)

```bash
cp system-config/konfigurator*.service system-config/konfigurator*.timer /etc/systemd/system/
cp system-config/konfigurator /etc/nginx/sites-available/
ln -s /etc/nginx/sites-available/konfigurator /etc/nginx/sites-enabled/
systemctl daemon-reload
systemctl enable --now konfigurator
systemctl enable --now konfigurator-support-email-sync.timer \
  konfigurator-refresh-prices.timer konfigurator-refresh-product-prices.timer \
  konfigurator-daily-backup.timer
```

## 7. HTTPS certifikát (NENÍ v záloze - vázaný na IP/doménu)

Porty 8091/8092 (fotoaparát v adminu) potřebují TLS. Na novém VPS je
nová IP → nová sslip.io doména:

```bash
apt install -y certbot python3-certbot-nginx
# v /etc/nginx/sites-available/konfigurator prepsat starou
# <IP-s-pomlckami>.sslip.io domenu na novou, pak:
certbot certonly --nginx -d <nova-ip-s-pomlckami>.sslip.io
```

## 8. Ověření

```bash
nginx -t && systemctl reload nginx
curl -s http://127.0.0.1:8090/api/health   # {"db":"connected","status":"ok"}
```

Pak projít admin (přihlášení z app_users platí - hesla jsou v DB) a
scénu. SMTP/IMAP přístupy jsou v `api/.env`, není třeba nic měnit.

## Co v záloze záměrně NENÍ

- `api/venv`, `api/step_venv` (krok 3)
- systémové balíčky (krok 2)
- TLS certifikáty (krok 7)
- předchozí zálohy (`zaloha_*` - ochrana proti exponenciálnímu růstu)

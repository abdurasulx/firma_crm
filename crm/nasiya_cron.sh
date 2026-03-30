#!/bin/bash
# StockFirm CRM — Nasiya Eslatma Skripti
# Har kuni ertalab 6:00 da avtomatik ishga tushadi
# Cron: 0 6 * * * /www/wwwroot/crm.stockfirm.uz/crm/nasiya_cron.sh >> /www/wwwroot/crm.stockfirm.uz/crm/nasiya_cron.log 2>&1

cd '/www/wwwroot/crm.stockfirm.uz/crm'
source ./venv/bin/activate
python manage.py nasiya_eslatma

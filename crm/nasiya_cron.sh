#!/bin/bash
# Firma CRM — Nasiya Eslatma Skripti
# Har kuni ertalab 9:00 da avtomatik ishga tushadi
# Cron: 0 9 * * * /media/banda/New\ Volume/firma_crm/crm/nasiya_cron.sh >> /var/log/nasiya_eslatma.log 2>&1

cd '/media/banda/New Volume/firma_crm/crm'
source ./venv/bin/activate
python manage.py nasiya_eslatma

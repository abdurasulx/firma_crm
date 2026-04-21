#!/bin/bash
# ============================================================
# StockFirm CRM — Kunlik Cron Skript
# ============================================================
# Crontab ga qo'shish uchun:
#   crontab -e
# Quyidagi qatorlarni qo'shing:
#
#   # Har kecha 02:00 da — asosiy cron
#   0 2 * * * /media/banda/NewVolume/firma_crm/crm/run_cron.sh >> /media/banda/NewVolume/firma_crm/crm/logs/cron.log 2>&1
#
#   # Har 6 soatda — nasiya eslatmasi
#   0 8,14,20 * * * /media/banda/NewVolume/firma_crm/crm/run_cron.sh --nasiya-only >> /media/banda/NewVolume/firma_crm/crm/logs/cron_nasiya.log 2>&1
# ============================================================

# Yo'llar
PROJECT_DIR="/media/banda/NewVolume/firma_crm/crm"
PYTHON="/usr/bin/python3"
MANAGE="$PROJECT_DIR/manage.py"
LOG_DIR="$PROJECT_DIR/logs"
DATE=$(date '+%Y-%m-%d %H:%M:%S')

# Log papkasini yaratish
mkdir -p "$LOG_DIR"

echo ""
echo "=============================================="
echo "  StockFirm CRM Cron — $DATE"
echo "=============================================="

# Argumentlarni tekshirish
if [ "$1" == "--nasiya-only" ]; then
    echo "▶ Faqat nasiya eslatmalari..."
    cd "$PROJECT_DIR" && "$PYTHON" "$MANAGE" cron_tasks --skip-lifecycle
elif [ "$1" == "--lifecycle-only" ]; then
    echo "▶ Faqat lifecycle tekshiruvi..."
    cd "$PROJECT_DIR" && "$PYTHON" "$MANAGE" cron_tasks --skip-nasiya
elif [ "$1" == "--dry-run" ]; then
    echo "▶ Dry-run rejimi..."
    cd "$PROJECT_DIR" && "$PYTHON" "$MANAGE" cron_tasks --dry-run
else
    echo "▶ Barcha tasklar ishga tushirilmoqda..."
    cd "$PROJECT_DIR" && "$PYTHON" "$MANAGE" cron_tasks
fi

EXIT_CODE=$?
if [ $EXIT_CODE -eq 0 ]; then
    echo "✅ Cron muvaffaqiyatli yakunlandi — $DATE"
else
    echo "❌ Cron XATO bilan tugadi (exit code: $EXIT_CODE) — $DATE"
fi

exit $EXIT_CODE

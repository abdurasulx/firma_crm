import os
import django
import logging
import sys
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# 1. Setup Django
# Adjust Python path to include the project root
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'crm.settings')
django.setup()

from django.conf import settings
from main.models import User
from main.bot_logic import generate_tg_link_token
from asgiref.sync import sync_to_async

# 2. Configure Logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

@sync_to_async
def get_user_data(chat_id):
    """Safely fetch user and company data in a sync context."""
    user = User.objects.filter(tg_id=chat_id).select_related('company', 'company__plan').first()
    if user:
        # Pre-fetch company to avoid lazy loading issues in async
        company = user.company
        return {
            'exists': True,
            'user_type': user.type,
            'full_name': user.tuliq_ismi or user.username,
            'company_name': company.name if company else None,
            'company_subdomain': company.subdomain if company else None,
            'is_active': company.is_active if company else False,
            'has_bot_feature': (company.is_on_trial or (company.plan and company.plan.has_telegram_bot)) if company else False
        }
    return {'exists': False}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    data = await get_user_data(chat_id)
    
    base_domain = getattr(settings, 'BASE_DOMAIN', 'localhost:8000')
    scheme = "https" if not any(x in base_domain for x in ["localhost", "127.0.0.1", "lvh.me"]) else "http"
    
    if data['exists']:
        # Active check
        if not data['is_active']:
            await update.message.reply_text(
                "Sizning firmaningiz faoliyati vaqtincha to'xtatilgan. "
                "Iltimos, qayta faollashtirish uchun administrator bilan bog'laning."
            )
            return

        # Tariff check (Owners always have access for notifications)
        if data['user_type'] != 'ega' and not data['has_bot_feature']:
            await update.message.reply_text(
                f"Assalomu alaykum, {data['full_name']}!\n\n"
                "Sizning Telegram hisobingiz bog'langan, biroq firmaning tarif rejasida Telegram Bot xizmati mavjud emas. "
                "Iltimos, xizmatni faollashtirish uchun administrator bilan bog'laning."
            )
            return

        subdomain = data['company_subdomain'] or "www"
        token = generate_tg_link_token(chat_id)
        login_url = f"{scheme}://{subdomain}.{base_domain}/login/?tg_id={chat_id}&hash={token}"
        
        keyboard = [[InlineKeyboardButton("🖥 Saytga kirish (Auto-login)", url=login_url)]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            f"Assalomu alaykum, {data['full_name']}!\n\n"
            "Sizning Telegram hisobingiz tizimga bog'langan. "
            "Profil bo'yicha saytga kirish uchun pastdagi tugmani bosing.\n\n"
            f"Firma: <b>{data['company_name']}</b>",
            reply_markup=reply_markup,
            parse_mode="HTML"
        )
    else:
        # User not linked
        token = generate_tg_link_token(chat_id)
        link_url = f"{scheme}://{base_domain}/login/?tg_id={chat_id}&hash={token}"
        
        keyboard = [[InlineKeyboardButton("🔗 Hisobni bog'lash", url=link_url)]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "Assalomu alaykum!\n\n"
            "CRM tizimidagi hisobingizni Telegramga bog'lash uchun:\n"
            "1. Pastdagi tugmani bosing.\n"
            "2. O'z firmangiz saytida login va parolingiz bilan kiring.\n\n"
            "Shundan so'ng hisobingiz avtomatik bog'lanadi.",
            reply_markup=reply_markup
        )

if __name__ == '__main__':
    token = getattr(settings, 'TELEGRAM_BOT_TOKEN', None)
    if not token or token == 'YOUR_BOT_TOKEN_HERE':
        logger.error("TELEGRAM_BOT_TOKEN is not set in settings.py or .env. Please check.")
        sys.exit(1)
    
    application = ApplicationBuilder().token(token).build()
    
    start_handler = CommandHandler('start', start)
    application.add_handler(start_handler)
    
    logger.info("Bot is starting...")
    application.run_polling()

from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse, FileResponse
from django.utils import timezone
from django.conf import settings
from .models import Company, Plan
from .backup_utils import generate_backup, restore_backup, get_backup_dates
from .plan_utils import company_has_access
import datetime
import logging

logger = logging.getLogger(__name__)

@login_required(login_url='login')
def prepare_backup_page(request):
    """
    Kompaniya uchun zaxira yuklashdan oldin
    foydalanuvchini kutish sahifasiga yo'naltirish.
    """
    if request.user.type != 'ega':
        messages.error(request, "Faqat do'kon egasi zaxira yuklab olishi mumkin.")
        return redirect('main')
    
    company = request.company
    
    # To'lov holatini tekshirish
    if not company_has_access(company):
        messages.warning(request, "Zaxira nusxasini yuklab olish uchun to'lov amalga oshirilgan bo'lishi kerak.")
        return redirect('main')
    
    # Backup turi va ruxsatini tekshirish
    backup_type = 'none'
    if getattr(company, 'is_on_trial', False):
        backup_type = 'none'
    elif getattr(company, 'is_custom_plan', False):
        backup_type = company.custom_backup_type
    elif getattr(company, 'plan', None):
        backup_type = company.plan.backup_type
    
    if backup_type == 'none':
        messages.error(request, "Tarifingizda backup mavjud emas yoki sinov muddatida ruxsat berilmagan.")
        return redirect('main')
        
    start_date = request.GET.get('start_date', '')
    end_date = request.GET.get('end_date', '')
    
    return render(request, 'backup_preparing.html', {
        'start_date': start_date,
        'end_date': end_date
    })

@login_required(login_url='login')
def download_backup(request):
    """Kompaniya uchun backup faylini yuklab olish"""
    if request.user.type != 'ega':
        messages.error(request, "Faqat do'kon egasi backup yuklab olishi mumkin.")
        return redirect('main')
    
    company = request.company
    
    # To'lov holatini tekshirish
    if not company_has_access(company):
        messages.warning(request, "Zaxira nusxasini yuklab olish uchun to'lov amalga oshirilgan bo'lishi kerak.")
        return redirect('main')
    
    # Backup turi va ruxsatini tekshirish
    backup_type = 'none'
    if company.is_on_trial:
        backup_type = 'none'
    elif company.is_custom_plan:
        backup_type = company.custom_backup_type
    elif company.plan:
        backup_type = company.plan.backup_type
    
    if backup_type == 'none':
        messages.error(request, "Tarifingizda backup mavjud emas yoki sinov muddatida ruxsat berilmagan.")
        return redirect('main')
    
    # Sanalarni qabul qilish
    start_date_str = request.GET.get('start_date')
    end_date_str = request.GET.get('end_date')
    start_date = None
    end_date = None
    
    try:
        if start_date_str:
            start_date = timezone.make_aware(datetime.datetime.strptime(start_date_str, '%Y-%m-%d'))
        if end_date_str:
            # End date should include the whole day
            end_date = timezone.make_aware(datetime.datetime.strptime(end_date_str, '%Y-%m-%d')) + datetime.timedelta(days=1) - datetime.timedelta(microseconds=1)
    except ValueError:
        messages.error(request, "Sana formati noto'g'ri (YYYY-MM-DD bo'lishi kerak).")
        return redirect('main')
    
    # Backup yaratish
    try:
        memory_zip = generate_backup(company, start_date=start_date, end_date=end_date)
        
        # Oxirgi backup vaqtini yangilash
        company.last_backup_at = timezone.now()
        company.save()
        
        filename = f"backup_{company.subdomain}_{timezone.now().strftime('%Y%m%d_%H%M%S')}.zip"
        
        response = HttpResponse(memory_zip.getvalue(), content_type='application/zip')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response
        
    except Exception as e:
        messages.error(request, f"Backup yaratishda xato yuz berdi: {str(e)}")
        return redirect('main')

@login_required(login_url='login')
def restore_view(request):
    """Backupdan ma'lumotlarni tiklash sahifasi"""
    if request.user.type != 'ega':
        messages.error(request, "Faqat do'kon egasi ma'lumotlarni tiklay oladi.")
        return redirect('main')
    
    company = request.company
    
    # To'lov holatini tekshirish (sinov muddatida restore mumkin emas)
    if not company_has_access(company) or company.is_on_trial:
        messages.warning(request, "Ma'lumotlarni tiklash uchun to'lov amalga oshirilgan bo'lishi kerak (Sinov muddatida ruxsat berilmagan).")
        return redirect('main')
    
    context = {}
    
    if request.method == 'POST':
        action = request.POST.get('action')
        zip_file = request.FILES.get('backup_file')
        
        if action == 'upload_only':
            if not zip_file:
                messages.error(request, "Iltimos, backup faylini yuklang.")
                return render(request, 'backup/restore.html', context)
            
            # Save file temporarily or extract dates directly
            oldest, newest = get_backup_dates(zip_file)
            
            if oldest is None:
                messages.error(request, "Yaroqsiz backup fayli. Fayl ichida all.json topilmadi yoki ma'lumot o'qib bo'lmadi.")
                return render(request, 'backup/restore.html', context)
                
            # Temporarily save the file so it can be restored on the next step
            import tempfile
            import os
            
            # Reset zip file pointer for saving
            zip_file.seek(0)
            
            # Create a simple temp file logic (in a real app, use Django's proper storage or cache)
            # We'll just pass the path on the server back to the context
            temp_dir = os.path.join(settings.MEDIA_ROOT, 'temp_backups')
            os.makedirs(temp_dir, exist_ok=True)
            temp_path = os.path.join(temp_dir, f"{request.user.id}_temp_backup.zip")
            
            with open(temp_path, 'wb+') as destination:
                for chunk in zip_file.chunks():
                    destination.write(chunk)
                    
            context['temp_backup_path'] = temp_path
            context['detected_start'] = oldest.strftime('%Y-%m-%d')
            context['detected_end'] = newest.strftime('%Y-%m-%d')
            context['file_name'] = zip_file.name
            context['step_two'] = True
            
            messages.info(request, "Fayl tahlil qilindi. Endi sanalarni tasdiqlang va tiklashni boshlang.")
            return render(request, 'backup/restore.html', context)
            
        elif action == 'restore':
            temp_path = request.POST.get('temp_backup_path')
            start_date_str = request.POST.get('start_date')
            end_date_str = request.POST.get('end_date')
            
            if not temp_path or not os.path.exists(temp_path):
                messages.error(request, "Backup fayli topilmadi. Iltimos, qaytadan yuklang.")
                return render(request, 'backup/restore.html')
            
            # Sanalarni parse qilish
            start_date = None
            end_date = None
            try:
                if start_date_str:
                    start_date = timezone.make_aware(datetime.datetime.strptime(start_date_str, '%Y-%m-%d'))
                if end_date_str:
                    end_date = timezone.make_aware(datetime.datetime.strptime(end_date_str, '%Y-%m-%d')) + datetime.timedelta(days=1) - datetime.timedelta(microseconds=1)
            except ValueError:
                messages.error(request, "Sana formati noto'g'ri.")
                return render(request, 'backup/restore.html')
                
            try:
                # Ochiq fayl sifatida restore ga uzatamiz
                with open(temp_path, 'rb') as f:
                    success = restore_backup(request.company, f, start_date, end_date)
                
                if success:
                    messages.success(request, "Ma'lumotlar muvaffaqiyatli tiklandi!")
                    # Tozalash
                    try:
                        os.remove(temp_path)
                    except Exception as e:
                        logger.warning(f"Vaqtinchalik faylni o'chirib bo'lmadi: {temp_path}, xato: {e}")
                else:
                    messages.error(request, "Ma'lumotlarni tiklashda xato yuz berdi.")
            except Exception as e:
                import traceback
                traceback.print_exc()
                messages.error(request, f"Xato: {str(e)}")
                
            return redirect('main')
            
    return render(request, 'backup/restore.html', context)

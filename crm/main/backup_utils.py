import os
import json
import zipfile
import shutil
from io import BytesIO
from django.core import serializers
from django.conf import settings
from django.utils import timezone
from django.contrib.auth.hashers import make_password
from .models import (
    User, Mahsulot, MahsulotTuri, Savdo, 
    HaridorDukon, Pazanda, YetkazibBeruvchi, 
    AmalLog, qaytarilgan_mahsulotlar, NasiyaTolov,
    YuklamaSorov, MiqdorQoshish, DeliveryStock, StockHistory
)

def generate_backup(company, start_date=None, end_date=None):
    """
    Kompaniya uchun ma'lumotlarni ZIP arxivga yig'adi.
    - all.json: barcha model ma'lumotlari
    - media/: barcha rasm va fayllar
    """
    # 1. Ma'lumotlarni yig'ish (Faqat ushbu kompaniyaga tegishli)
    data = []
    
    # Modellarni tartib bilan yig'amiz
    models_to_backup = [
        (MahsulotTuri, MahsulotTuri.objects.filter(company=company)),
        (Mahsulot, Mahsulot.objects.filter(company=company)),
        (HaridorDukon, HaridorDukon.objects.filter(company=company)),
        (Savdo, Savdo.objects.filter(company=company)),
        (NasiyaTolov, NasiyaTolov.objects.filter(company=company)),
        (AmalLog, AmalLog.objects.filter(company=company)),
        (qaytarilgan_mahsulotlar, qaytarilgan_mahsulotlar.objects.filter(company=company)),
        (YuklamaSorov, YuklamaSorov.objects.filter(company=company)),
        (MiqdorQoshish, MiqdorQoshish.objects.filter(company=company)),
        (DeliveryStock, DeliveryStock.objects.filter(company=company)),
        (StockHistory, StockHistory.objects.filter(company=company)),
    ]
    
    for model_class, queryset in models_to_backup:
        if start_date or end_date:
            # Check if model has created_at
            if hasattr(model_class, 'created_at'):
                if start_date:
                    queryset = queryset.filter(created_at__gte=start_date)
                if end_date:
                    queryset = queryset.filter(created_at__lte=end_date)
        
        data.extend(json.loads(serializers.serialize('json', queryset)))
    
    # Foydalanuvchilar (Parollarni default qilamiz)
    users = User.objects.filter(company=company)
    users_data = json.loads(serializers.serialize('json', users))
    
    for u_json in users_data:
        u_obj = User.objects.get(pk=u_json['pk'])
        if u_obj.type == 'ega':
            u_json['fields']['password'] = make_password('admin123')
        else:
            u_json['fields']['password'] = make_password('staff123')
    
    data.extend(users_data)
    
    # 2. ZIP Arxiv yaratish
    memory_zip = BytesIO()
    with zipfile.ZipFile(memory_zip, 'w', zipfile.ZIP_DEFLATED) as zf:
        # JSON ma'lumotni qo'shish
        zf.writestr('all.json', json.dumps(data, indent=4, ensure_ascii=False))
        
        # Media fayllarni qo'shish: barcha modellardan rasm yo'llarini yig'ish
        media_paths = set()
        
        def collect_path(field_val):
            """ImageField yoki str yo'lni normalize qiladi."""
            if not field_val:
                return None
            p = getattr(field_val, 'name', None) or str(field_val)
            p = p.strip().lstrip('/') if p and p.strip() else None
            return p if p else None

        def resolve_path(rel):
            """Yo'lni MEDIA_ROOT ga nisbatan topib qaytaradi."""
            if not rel:
                return None
            media_root = settings.MEDIA_ROOT
            # Candidate 1: direct join (relative path stored correctly)
            c1 = os.path.join(media_root, rel)
            if os.path.isfile(c1):
                return c1
            # Candidate 2: strip leading 'media/' prefix if present
            if rel.startswith('media/'):
                c2 = os.path.join(media_root, rel[6:])
                if os.path.isfile(c2):
                    return c2
            # Candidate 3: search by basename recursively inside MEDIA_ROOT
            fname = os.path.basename(rel)
            if fname:
                for root_dir, dirs, files in os.walk(media_root):
                    if fname in files:
                        return os.path.join(root_dir, fname)
            return None

        def add_field(val):
            p = collect_path(val)
            if p:
                media_paths.add(p)

        # 1. Mahsulot rasmlari
        for m in Mahsulot.objects.filter(company=company):
            add_field(m.rasmi)

        # 2. Foydalanuvchi rasmlari
        for u in User.objects.filter(company=company):
            add_field(u.rasmi)

        # 3. Haridor dukon rasmlari (dukon va egasi)
        for h in HaridorDukon.objects.filter(company=company):
            add_field(h.dukon_rasmi)
            add_field(h.egasining_rasmi)

        # 4. Savdo chek rasmlari (smr = savdo rasmi)
        for s in Savdo.objects.filter(company=company):
            add_field(s.smr)

        # 5. MiqdorQoshish rasmlari
        for mq in MiqdorQoshish.objects.filter(company=company):
            add_field(mq.rasmi)

        # ZIPga rasmlarni qo'shish (original subfolder strukturasida saqlash)
        added = set()
        for rel_path in media_paths:
            full_path = resolve_path(rel_path)
            if full_path and full_path not in added:
                # Preserve subfolder structure inside media/
                arc_name = 'media/' + rel_path.replace('media/', '', 1)
                zf.write(full_path, arc_name)
                added.add(full_path)
                
    memory_zip.seek(0)
    return memory_zip

def restore_backup(company, zip_file, start_date=None, end_date=None):
    """
    ZIP arxivdan ma'lumotlarni qayta tiklaydi.
    start_date va end_date berilgan bo'lsa, faqat shu oraliqdagi ma'lumotlar tiklanadi.
    """
    with zipfile.ZipFile(zip_file, 'r') as zf:
        # all.json ni o'qish
        with zf.open('all.json') as f:
            data = json.loads(f.read().decode('utf-8'))
            
        # Media fayllarni tiklash
        for file_info in zf.infolist():
            if file_info.filename.startswith('media/'):
                relative_path = file_info.filename.replace('media/', '')
                full_path = os.path.join(settings.MEDIA_ROOT, relative_path)
                os.makedirs(os.path.dirname(full_path), exist_ok=True)
                with zf.open(file_info) as source, open(full_path, 'wb') as target:
                    shutil.copyfileobj(source, target)
        
        # JSON ma'lumotlarni ob'ekt qilib yuklash va saqlash
        deserialized = list(serializers.deserialize('json', json.dumps(data)))
        
        for obj in deserialized:
            instance = obj.object
            
            # Vaqt bo'yicha cheklovlar
            if start_date or end_date:
                check_date = None
                if hasattr(instance, 'created_at'):
                    check_date = instance.created_at
                elif hasattr(instance, 'date_joined'):
                    check_date = instance.date_joined
                if check_date:
                    if start_date and check_date < start_date:
                        continue
                    if end_date and check_date > end_date:
                        continue
            
            # Kompaniyani majburiy o'rnatish (xavfsizlik uchun)
            if hasattr(instance, 'company_id') or hasattr(instance, 'company'):
                instance.company = company
            
            # update_or_create: pk mavjud bo'lsa yangilaydi, yo'q bo'lsa yaratadi
            ModelClass = instance.__class__
            pk_val = instance.pk
            
            # pk bo'yicha defaults sifatida barcha maydonlarni tayyorlaymiz
            fields = {
                f.name: getattr(instance, f.name)
                for f in ModelClass._meta.get_fields()
                if hasattr(f, 'column') and not f.many_to_many and not f.one_to_many
            }
            fields.pop('id', None)  # pk ni defaults dan olib tashlaymiz
            
            if pk_val:
                ModelClass.objects.update_or_create(pk=pk_val, defaults=fields)
            else:
                ModelClass.objects.create(**fields)
                
    return True

def get_backup_dates(zip_file):
    """
    ZIP arxivdagi all.json faylidan eng eski va eng yangi sanalarni topadi.
    Faqat 'created_at' yoki 'date_joined' maydonlariga ega bo'lgan ma'lumotlarni tekshiradi.
    Yaroqli arxiv emas yoki all.json topilmasa, (None, None) qaytaradi.
    """
    try:
        with zipfile.ZipFile(zip_file, 'r') as zf:
            if 'all.json' not in zf.namelist():
                return None, None
                
            with zf.open('all.json') as f:
                data = json.loads(f.read().decode('utf-8'))
                
            objects = serializers.deserialize('json', json.dumps(data))
            
            oldest_date = None
            newest_date = None
            
            for obj in objects:
                instance = obj.object
                check_date = None
                
                if hasattr(instance, 'created_at') and instance.created_at:
                    check_date = instance.created_at
                elif hasattr(instance, 'date_joined') and instance.date_joined:
                    check_date = instance.date_joined
                    
                if check_date:
                    if oldest_date is None or check_date < oldest_date:
                        oldest_date = check_date
                    if newest_date is None or check_date > newest_date:
                        newest_date = check_date
                        
            return oldest_date, newest_date
    except Exception as e:
        return None, None

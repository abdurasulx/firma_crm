from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0043_remove_mahsulotturi_company'),
    ]

    operations = [
        migrations.AlterField(
            model_name='user',
            name='type',
            field=models.CharField(
                choices=[
                    ('pazanda', 'Ishlab chiqaruvchi'),
                    ('ishlab_chiqaruvchi', 'Ishlab chiqaruvchi'),
                    ('omborchi', 'Omborchi'),
                    ('savdogar', 'Savdogar'),
                    ('yetkazib_beruvchi', 'Yetkazib Beruvchi'),
                    ('ega', 'Ega'),
                ],
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name='mahsulot',
            name='warehouse_type',
            field=models.CharField(
                choices=[
                    ('finished', 'Tayyor mahsulotlar ombori'),
                    ('semi_finished', 'Yarim tayyor mahsulotlar ombori'),
                ],
                default='finished',
                max_length=20,
            ),
        ),
        migrations.AlterField(
            model_name='stockhistory',
            name='event_type',
            field=models.CharField(
                choices=[
                    ('ADD', "Qo'shildi (Pazanda tomonidan)"),
                    ('DEDUCT', 'Kamaytirildi (Savdo/Yuklash)'),
                    ('RETURN', 'Qaytarildi'),
                    ('REQUEST_APPROVED', 'Sorov tasdiqlandi'),
                    ('RAW_REQUESTED', "Ishlab chiqarish uchun so'rov yuborildi"),
                    ('RAW_APPROVED', 'Yarim tayyor mahsulot ombordan berildi'),
                    ('RAW_REJECTED', "Yarim tayyor mahsulot so'rovi rad etildi"),
                    ('ADJUST', 'Admin tomonidan tuzatildi'),
                ],
                max_length=20,
            ),
        ),
        migrations.CreateModel(
            name='ProductionMaterialRequest',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('qty', models.FloatField()),
                ('status', models.CharField(choices=[('waiting', 'Kutilmoqda'), ('approved', 'Tasdiqlandi'), ('rejected', 'Rad etildi')], default='waiting', max_length=20)),
                ('note', models.TextField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('reviewed_at', models.DateTimeField(blank=True, null=True)),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='material_requests', to='main.company')),
                ('material', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='production_material_requests', to='main.mahsulot')),
                ('producer', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='material_requests', to='main.pazanda')),
                ('reviewed_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='reviewed_material_requests', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': "Ishlab chiqarish material so'rovi",
                'verbose_name_plural': "Ishlab chiqarish material so'rovlari",
                'ordering': ['-created_at'],
            },
        ),
    ]

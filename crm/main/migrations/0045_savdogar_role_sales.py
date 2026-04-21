from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0044_erp_warehouse_material_requests'),
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
        migrations.AlterField(
            model_name='savdo',
            name='yetkazib_beruvchi',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='main.yetkazibberuvchi'),
        ),
        migrations.AddField(
            model_name='savdo',
            name='savdogar',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='savdolar', to=settings.AUTH_USER_MODEL),
        ),
    ]

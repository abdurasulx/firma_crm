from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0050_production_material_target_product'),
    ]

    operations = [
        migrations.AddField(
            model_name='mahsulot',
            name='is_savdogar_product',
            field=models.BooleanField(default=False),
        ),
        migrations.AlterField(
            model_name='savdo',
            name='haridor_dukon',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                to='main.haridordukon',
            ),
        ),
    ]

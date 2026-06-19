from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0049_savdogar_contract_documents'),
    ]

    operations = [
        migrations.AddField(
            model_name='productionmaterialrequest',
            name='target_product',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='production_target_requests',
                to='main.mahsulot',
            ),
        ),
    ]

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0051_savdogar_walkin_products'),
    ]

    operations = [
        migrations.AddField(
            model_name='company',
            name='savdogar_contract_next_number',
            field=models.PositiveIntegerField(default=1),
        ),
        migrations.AddField(
            model_name='savdo',
            name='contract_number',
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='savdo',
            name='credit_down_payment',
            field=models.FloatField(default=0),
        ),
    ]

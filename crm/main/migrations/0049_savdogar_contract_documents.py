from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0048_appnotification'),
    ]

    operations = [
        migrations.AddField(
            model_name='company',
            name='custom_has_savdogar_sales',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='company',
            name='savdogar_contract_text',
            field=models.TextField(blank=True, default=''),
        ),
        migrations.AddField(
            model_name='planrequest',
            name='custom_has_savdogar_sales',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='savdo',
            name='contract_pdf',
            field=models.FileField(blank=True, null=True, upload_to='savdo_contracts/pdf/'),
        ),
        migrations.AddField(
            model_name='savdo',
            name='customer_passport_image',
            field=models.ImageField(blank=True, null=True, upload_to='savdo_contracts/passports/'),
        ),
        migrations.AddField(
            model_name='savdo',
            name='signed_contract_scan',
            field=models.FileField(blank=True, null=True, upload_to='savdo_contracts/signed/'),
        ),
    ]

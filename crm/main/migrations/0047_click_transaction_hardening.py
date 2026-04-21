from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0046_credit_sale_terms_settings'),
    ]

    operations = [
        migrations.AddField(
            model_name='clicktransaction',
            name='click_paydoc_id',
            field=models.CharField(blank=True, default='', max_length=255),
        ),
        migrations.AddField(
            model_name='clicktransaction',
            name='service_id',
            field=models.CharField(blank=True, default='', max_length=255),
        ),
        migrations.AlterField(
            model_name='clicktransaction',
            name='click_trans_id',
            field=models.CharField(max_length=255, unique=True),
        ),
        migrations.AddIndex(
            model_name='clicktransaction',
            index=models.Index(fields=['merchant_trans_id'], name='main_clickt_merchan_6e3d6b_idx'),
        ),
        migrations.AddIndex(
            model_name='clicktransaction',
            index=models.Index(fields=['status'], name='main_clickt_status_2fe156_idx'),
        ),
    ]

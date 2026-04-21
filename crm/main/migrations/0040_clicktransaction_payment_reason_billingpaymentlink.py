from uuid import uuid4

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0039_planrequest_is_trial'),
    ]

    operations = [
        migrations.AddField(
            model_name='clicktransaction',
            name='payment_reason',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.CreateModel(
            name='BillingPaymentLink',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('token', models.CharField(default=uuid4, editable=False, max_length=64, unique=True)),
                ('reason', models.CharField(max_length=255)),
                ('billing_period_start', models.DateField()),
                ('amount_usd', models.DecimalField(decimal_places=2, max_digits=12)),
                ('amount_uzs', models.DecimalField(decimal_places=2, max_digits=14)),
                ('click_url', models.TextField()),
                ('status', models.CharField(choices=[('created', 'Yaratilgan'), ('opened', "Ochildi"), ('paid', "To'langan"), ('failed', 'Xatolik'), ('canceled', 'Bekor qilingan')], default='created', max_length=20)),
                ('opened_at', models.DateTimeField(blank=True, null=True)),
                ('paid_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('company', models.ForeignKey(on_delete=models.deletion.CASCADE, related_name='billing_payment_links', to='main.company')),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
    ]

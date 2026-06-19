from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0047_click_transaction_hardening'),
    ]

    operations = [
        migrations.CreateModel(
            name='AppNotification',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=255)),
                ('message', models.TextField()),
                ('notification_type', models.CharField(choices=[('success', 'Muvaffaqiyatli'), ('warning', 'Ogohlantirish'), ('info', 'Maʼlumot')], default='info', max_length=20)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='notifications', to='main.company')),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='appnotification',
            index=models.Index(fields=['company', '-created_at'], name='main_appnot_company_c5aec1_idx'),
        ),
    ]

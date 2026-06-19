from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0052_savdogar_contract_number'),
    ]

    operations = [
        migrations.AlterField(
            model_name='locationhistory',
            name='timestamp',
            field=models.DateTimeField(default=django.utils.timezone.now),
        ),
        migrations.AddField(
            model_name='locationhistory',
            name='client_timestamp',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='locationhistory',
            name='accuracy',
            field=models.FloatField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='locationhistory',
            name='speed',
            field=models.FloatField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='locationhistory',
            name='source',
            field=models.CharField(default='websocket', max_length=30),
        ),
    ]

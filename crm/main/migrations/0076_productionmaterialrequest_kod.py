import uuid

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0075_planrequest_desktop_agent_stations'),
    ]

    operations = [
        migrations.AddField(
            model_name='productionmaterialrequest',
            name='kod',
            field=models.CharField(
                default=uuid.uuid4, editable=False, max_length=64, unique=True,
                help_text="So'rov QR kodi — chop etib jismoniy paketga yopishtirish uchun",
            ),
        ),
    ]

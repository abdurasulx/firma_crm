from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0053_locationhistory_offline_tracking'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='rasm',
            field=models.ImageField(blank=True, null=True, upload_to='users/'),
        ),
    ]

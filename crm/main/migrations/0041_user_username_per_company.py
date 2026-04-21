import django.contrib.auth.validators
from django.db import migrations, models
from django.utils.translation import gettext_lazy as _


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0040_clicktransaction_payment_reason_billingpaymentlink'),
    ]

    operations = [
        migrations.AlterField(
            model_name='user',
            name='username',
            field=models.CharField(
                help_text='150 ta belgigacha. Harf, raqam va @/./+/-/_ belgilaridan foydalaning.',
                max_length=150,
                validators=[django.contrib.auth.validators.UnicodeUsernameValidator()],
                verbose_name='username',
            ),
        ),
        migrations.AddConstraint(
            model_name='user',
            constraint=models.UniqueConstraint(fields=('company', 'username'), name='unique_username_per_company'),
        ),
    ]

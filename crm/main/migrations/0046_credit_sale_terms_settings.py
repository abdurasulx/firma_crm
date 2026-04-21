from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0045_savdogar_role_sales'),
    ]

    operations = [
        migrations.AddField(
            model_name='company',
            name='credit_sales_enabled',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='company',
            name='credit_contract_template',
            field=models.TextField(blank=True, default="Nasiya shartnomasi: {{ company }} va {{ customer }} o'rtasida {{ months }} oy muddatga {{ total }} so'mlik savdo."),
        ),
        migrations.AddField(
            model_name='company',
            name='credit_early_discount_percent',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=5),
        ),
        migrations.AddField(
            model_name='company',
            name='credit_late_penalty_percent',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=5),
        ),
        migrations.AddField(
            model_name='company',
            name='credit_rules_note',
            field=models.TextField(blank=True, default="3 oy - 10%, 6 oy - 15%, 9 oy - 20%, 12 oy - 30% ustama. To'lov grafigi oyma-oy nazorat qilinadi."),
        ),
        migrations.AddField(
            model_name='savdo',
            name='base_summa',
            field=models.FloatField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='savdo',
            name='credit_term_months',
            field=models.PositiveSmallIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='savdo',
            name='credit_markup_percent',
            field=models.FloatField(default=0),
        ),
        migrations.AddField(
            model_name='savdo',
            name='credit_due_date',
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='savdo',
            name='credit_contract_text',
            field=models.TextField(blank=True, null=True),
        ),
    ]

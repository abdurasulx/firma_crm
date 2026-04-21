from django.db import migrations


def merge_duplicate_product_types(apps, schema_editor):
    MahsulotTuri = apps.get_model('main', 'MahsulotTuri')
    Mahsulot = apps.get_model('main', 'Mahsulot')

    canonical_by_name = {}

    for product_type in MahsulotTuri.objects.all().order_by('id'):
        key = (product_type.nomi or '').strip().lower()
        if not key:
            key = f"__empty_{product_type.id}"

        canonical = canonical_by_name.get(key)
        if canonical is None:
            canonical_by_name[key] = product_type
            cleaned_name = (product_type.nomi or '').strip()
            if cleaned_name and cleaned_name != product_type.nomi:
                product_type.nomi = cleaned_name
                product_type.save(update_fields=['nomi'])
            continue

        Mahsulot.objects.filter(turi_id=product_type.id).update(turi_id=canonical.id)
        product_type.delete()


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0042_alter_user_options'),
    ]

    operations = [
        migrations.RunPython(merge_duplicate_product_types, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name='mahsulotturi',
            name='company',
        ),
    ]

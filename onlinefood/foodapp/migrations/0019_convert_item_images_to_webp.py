from pathlib import Path

from django.conf import settings
from django.db import migrations


def convert_item_images_to_webp(apps, schema_editor):
    Item = apps.get_model('foodapp', 'Item')
    media_root = Path(settings.MEDIA_ROOT)
    db_alias = schema_editor.connection.alias

    for item in Item.objects.using(db_alias).all():
        name = item.image.name
        if not name or not name.lower().endswith(('.jpg', '.jpeg', '.png')):
            continue

        webp_name = str(Path(name).with_suffix('.webp'))
        if (media_root / webp_name).exists():
            Item.objects.using(db_alias).filter(pk=item.pk).update(image=webp_name)


class Migration(migrations.Migration):

    dependencies = [
        ('foodapp', '0018_coupon_cart_coupon'),
    ]

    operations = [
        migrations.RunPython(convert_item_images_to_webp, migrations.RunPython.noop),
    ]

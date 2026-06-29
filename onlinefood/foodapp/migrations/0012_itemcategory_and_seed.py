from django.db import migrations, models
import django.db.models.deletion
import uuid


def seed_categories(apps, schema_editor):
    ItemCategory = apps.get_model('foodapp', 'ItemCategory')
    Item = apps.get_model('foodapp', 'Item')
    db_alias = schema_editor.connection.alias

    categories = [
        'Veg', 'Non-Veg', 'Chinese', 'Italian',
        'Desserts', 'Beverages', 'South Indian',
    ]
    created = {}
    for name in categories:
        cat, _ = ItemCategory.objects.using(db_alias).get_or_create(category_name=name)
        created[name] = cat

    # Map existing items (old category field data may be lost, so just assign defaults)
    # If category_char still exists on the model during migration, try reading it
    # Otherwise, items get no category (null) which is fine with null=True


class Migration(migrations.Migration):

    dependencies = [
        ('foodapp', '0011_cart_status_alter_orderplaced_status'),
    ]

    operations = [
        migrations.CreateModel(
            name='ItemCategory',
            fields=[
                ('uid', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('category_name', models.CharField(max_length=100, unique=True)),
            ],
            options={
                'verbose_name_plural': 'Categories',
                'abstract': False,
            },
        ),
        migrations.AlterField(
            model_name='item',
            name='category',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='items', to='foodapp.itemcategory'),
        ),
        migrations.RunPython(seed_categories, migrations.RunPython.noop),
    ]

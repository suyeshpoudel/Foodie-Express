from io import BytesIO
from pathlib import Path
from urllib.request import urlretrieve
import ssl
import tempfile

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand

from foodapp.models import Item

ssl._create_default_https_context = ssl._create_unverified_context

SEARCH_TERMS = {
    'paneer butter masala': 'paneer-butter-masala',
    'dal makhani': 'dal-makhani',
    'chole bhature': 'chole-bhature',
    'palak paneer': 'palak-paneer',
    'aloo gobi': 'aloo-gobi',
    'veg manchurian': 'veg-manchurian',
    'mushroom masala': 'mushroom-masala',
    'chicken biryani': 'chicken-biryani',
    'butter chicken': 'butter-chicken',
    'mutton curry': 'mutton-curry',
    'egg curry': 'egg-curry',
    'chicken tikka': 'chicken-tikka',
    'fish curry': 'fish-curry',
    'chicken 65': 'chicken-65',
    'pepper chicken': 'pepper-chicken',
    'hakka noodles': 'hakka-noodles',
    'gobi manchurian': 'gobi-manchurian',
    'fried rice': 'fried-rice',
    'spring rolls': 'spring-rolls',
    'chilli chicken': 'chilli-chicken',
    'schezwan noodles': 'schezwan-noodles',
    'dim sum': 'dim-sum',
    'hot & sour soup': 'hot-sour-soup',
    'margherita pizza': 'margherita-pizza',
    'pasta alfredo': 'pasta-alfredo',
    'risotto': 'risotto',
    'bruschetta': 'bruschetta',
    'lasagna': 'lasagna',
    'tiramisu': 'tiramisu',
    'fettuccine carbonara': 'fettuccine-carbonara',
    'garlic bread': 'garlic-bread',
    'gulab jamun': 'gulab-jamun',
    'brownie': 'brownie-chocolate',
    'ice cream sundae': 'ice-cream-sundae',
    'cheesecake': 'cheesecake',
    'rasmalai': 'rasmalai',
    'chocolate mousse': 'chocolate-mousse',
    'kheer': 'kheer-rice-pudding',
    'lemon tart': 'lemon-tart',
    'mango lassi': 'mango-lassi',
    'masala chai': 'masala-chai',
    'cold coffee': 'cold-coffee',
    'fresh lime soda': 'lime-soda',
    'chocolate shake': 'chocolate-shake',
    'green tea': 'green-tea',
    'fruit punch': 'fruit-punch',
    'buttermilk': 'buttermilk',
    'masala dosa': 'masala-dosa',
    'idli sambar': 'idli-sambar',
    'vada': 'vada-indian',
    'uttapam': 'uttapam',
    'rava dosa': 'rava-dosa',
    'medu vada': 'medu-vada',
    'rasam rice': 'rasam-rice',
    'coconut rice': 'coconut-rice',
}


def download_image(search_term):
    url = f'https://loremflickr.com/512/512/{search_term}'
    tmp = Path(tempfile.mkstemp(suffix='.jpg')[1])
    try:
        urlretrieve(url, str(tmp))
        data = tmp.read_bytes()
        return ContentFile(data)
    finally:
        tmp.unlink(missing_ok=True)


class Command(BaseCommand):
    help = 'Download actual food images for all items'

    def handle(self, *args, **options):
        items = Item.objects.all()
        total = items.count()
        updated = 0
        errors = 0

        self.stdout.write(f'Updating images for {total} items...')

        for item in items:
            key = item.item_name.lower()
            search = SEARCH_TERMS.get(key, key.replace(' ', '-'))
            try:
                image_file = download_image(search)
                safe_name = key.replace("'", '').replace('&', 'and').replace(' ', '_')
                item.image.save(f'{safe_name}.jpg', image_file, save=True)
                updated += 1
                self.stdout.write(f'  [{updated}/{total}] {item.item_name} — updated')
            except Exception as e:
                errors += 1
                self.stdout.write(self.style.WARNING(f'  [{updated + errors}/{total}] {item.item_name} — failed: {e}'))

        self.stdout.write(self.style.SUCCESS(f'\nDone. Updated {updated} items ({errors} errors).'))

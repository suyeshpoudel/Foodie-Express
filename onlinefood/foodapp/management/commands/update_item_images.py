import difflib
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from io import BytesIO

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from PIL import Image, ImageOps, UnidentifiedImageError

from foodapp.management.commands.seed_items import CATEGORY_ITEMS
from foodapp.models import Item

KNOWN_ITEM_NAMES = [entry[0] for items in CATEGORY_ITEMS.values() for entry in items]

USER_AGENT = 'DjangoOnlineFoodSeeder/1.0 (https://github.com/supo21/Django-online-food)'
COMMONS_API = 'https://commons.wikimedia.org/w/api.php'
WIKIPEDIA_API = 'https://en.wikipedia.org/w/api.php'

REQUEST_TIMEOUT = 25
MAX_RETRIES = 4
RETRY_DELAY = 2
MAX_IMAGE_BYTES = 10 * 1024 * 1024
IMAGE_SIZE = 512

SEARCH_TERMS = {
    'veg biryani': 'vegetable biryani',
    'veg manchurian': 'veg manchurian',
    'mushroom masala': 'mushroom butter masala',
    'hot & sour soup': 'hot and sour soup',
    'pasta alfredo': 'fettuccine alfredo',
    'fettuccine carbonara': 'carbonara',
    'ice cream sundae': 'ice cream sundae',
    'chocolate shake': 'chocolate milkshake',
    'fresh lime soda': 'lime soda',
    'rasam rice': 'rasam',
    'brownie': 'chocolate brownie',
    'rasmalai': 'ras malai',
    'spring rolls': 'spring roll',
    'cold coffee': 'cold coffee',
    'green tea': 'green tea cup',
}

SIZE_WORDS = {'small', 'medium', 'large', 'regular', 'special', 'mini', 'jumbo'}

STOPWORDS = {
    'the', 'a', 'an', 'and', 'with', 'of', 'in', 'on', 'for', 'to', 'from', 'by',
}

BAD_WORDS = {
    'logo', 'icon', 'map', 'diagram', 'chart', 'poster', 'cover', 'stamp', 'coin',
    'sign', 'banner', 'drawing', 'clipart', 'gatorade', 'g2',
}


def _normalize(value):
    value = value.lower().replace('&', ' and ')
    value = re.sub(r'[^a-z0-9]+', ' ', value)
    return value.strip()


def _clean_title(title):
    title = re.sub(r'^file:\s*', '', title, flags=re.IGNORECASE)
    title = re.sub(r'\.(jpe?g|png|gif|webp|tiff?)$', '', title, flags=re.IGNORECASE)
    return title.strip()


def _slug(name):
    value = name.lower().replace('&', 'and').replace("'", '')
    value = re.sub(r'[^a-z0-9]+', '_', value)
    return value.strip('_')


def _get_json(url):
    last_error = None
    for attempt in range(MAX_RETRIES):
        request = urllib.request.Request(
            url,
            headers={
                'User-Agent': USER_AGENT,
                'Accept': 'application/json',
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT) as response:
                return json.loads(response.read().decode('utf-8'))
        except urllib.error.HTTPError as exc:
            last_error = exc
            if exc.code not in (429, 500, 502, 503, 504):
                raise
            retry_after = exc.headers.get('Retry-After')
            delay = float(retry_after) if retry_after and retry_after.isdigit() else RETRY_DELAY * (attempt + 1)
            time.sleep(delay)
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last_error = exc
            time.sleep(RETRY_DELAY * (attempt + 1))
    raise last_error


def _score(query, title):
    normalized_query = _normalize(query)
    normalized_title = _normalize(title)
    if not normalized_query or not normalized_title:
        return None

    tokens = [token for token in normalized_query.split() if token not in STOPWORDS]
    if not tokens:
        tokens = normalized_query.split()

    hits = sum(1 for token in tokens if token in normalized_title)
    coverage = hits / len(tokens)
    if coverage < 0.5:
        return None

    compact_query = normalized_query.replace(' ', '')
    compact_title = normalized_title.replace(' ', '')
    phrase_bonus = 15 if compact_query in compact_title else 0
    extra_words = max(len(normalized_title.split()) - len(tokens), 0)

    score = coverage * 100 + phrase_bonus - extra_words * 2
    if any(word in normalized_title.split() for word in BAD_WORDS):
        score -= 50
    return score


def _commons_candidates(query):
    params = {
        'action': 'query',
        'generator': 'search',
        'gsrsearch': f'filetype:bitmap {query}',
        'gsrnamespace': '6',
        'gsrlimit': '20',
        'prop': 'imageinfo',
        'iiprop': 'url|mime|size',
        'iiurlwidth': str(IMAGE_SIZE),
        'format': 'json',
    }
    url = f'{COMMONS_API}?{urllib.parse.urlencode(params)}'
    data = _get_json(url)
    return list(((data.get('query') or {}).get('pages') or {}).values())


def _candidate_queries(item_name):
    seen = set()
    mapped = SEARCH_TERMS.get(item_name.lower())
    stripped = ' '.join(
        word for word in item_name.split() if word.lower() not in SIZE_WORDS
    )
    for query in (mapped, item_name, stripped):
        if query and query.lower() not in seen:
            seen.add(query.lower())
            yield query


def _wikipedia_candidate(query):
    params = {
        'action': 'query',
        'generator': 'search',
        'gsrsearch': query,
        'gsrlimit': '3',
        'prop': 'pageimages',
        'piprop': 'thumbnail',
        'pithumbsize': str(IMAGE_SIZE),
        'format': 'json',
    }
    url = f'{WIKIPEDIA_API}?{urllib.parse.urlencode(params)}'
    data = _get_json(url)
    pages = ((data.get('query') or {}).get('pages') or {}).values()
    ranked = []
    for page in pages:
        thumbnail = (page.get('thumbnail') or {}).get('source')
        title = _clean_title(page.get('title', ''))
        score = _score(query, title)
        if thumbnail and score is not None:
            ranked.append((score, title, thumbnail))
    if ranked:
        ranked.sort(key=lambda entry: entry[0], reverse=True)
        _, title, thumbnail = ranked[0]
        return title, thumbnail
    return None


def _find_image(query):
    ranked = []
    for rank, page in enumerate(_commons_candidates(query)):
        info = (page.get('imageinfo') or [{}])[0]
        mime = info.get('mime', '')
        if mime not in ('image/jpeg', 'image/png', 'image/webp'):
            continue
        if info.get('width', 0) < 300 or info.get('height', 0) < 300:
            continue
        source = info.get('thumburl') or info.get('url')
        if not source:
            continue
        title = _clean_title(page.get('title', ''))
        score = _score(query, title)
        if score is None:
            continue
        compact_length = len(_normalize(title).replace(' ', ''))
        ranked.append((score, -compact_length, -rank, title, source))

    if ranked:
        ranked.sort(reverse=True)
        _, _, _, title, source = ranked[0]
        return title, source

    return _wikipedia_candidate(query)


def _find_item_image(item_name):
    for query in _candidate_queries(item_name):
        candidate = _find_image(query)
        if candidate:
            return candidate

    close_matches = difflib.get_close_matches(item_name, KNOWN_ITEM_NAMES, n=1, cutoff=0.85)
    if close_matches:
        for query in _candidate_queries(close_matches[0]):
            candidate = _find_image(query)
            if candidate:
                return candidate

    return None


def _download_image(url):
    last_error = None
    for attempt in range(MAX_RETRIES):
        request = urllib.request.Request(
            url,
            headers={
                'User-Agent': USER_AGENT,
                'Accept': 'image/jpeg,image/png,image/webp,image/*',
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT) as response:
                content_type = response.headers.get('Content-Type', '')
                if not content_type.startswith('image/'):
                    raise ValueError(f'unexpected content type: {content_type!r}')
                raw = response.read(MAX_IMAGE_BYTES + 1)
            if len(raw) > MAX_IMAGE_BYTES:
                raise ValueError('image exceeds size limit')
            return _to_webp(raw)
        except urllib.error.HTTPError as exc:
            last_error = exc
            if exc.code not in (429, 500, 502, 503, 504):
                raise
            time.sleep(RETRY_DELAY * (attempt + 1))
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last_error = exc
            time.sleep(RETRY_DELAY * (attempt + 1))
    raise last_error


def _to_webp(raw):
    try:
        with Image.open(BytesIO(raw)) as probe:
            probe.verify()
        with Image.open(BytesIO(raw)) as image:
            if image.mode in ('RGBA', 'LA') or (image.mode == 'P' and 'transparency' in image.info):
                image = image.convert('RGBA')
                background = Image.new('RGB', image.size, (255, 255, 255))
                background.paste(image, mask=image.split()[-1])
                image = background
            else:
                image = image.convert('RGB')
            image = ImageOps.fit(image, (IMAGE_SIZE, IMAGE_SIZE), method=Image.LANCZOS)
            output = BytesIO()
            image.save(output, format='WEBP', quality=82)
    except (UnidentifiedImageError, OSError) as exc:
        raise ValueError(f'invalid image: {exc}') from exc
    return ContentFile(output.getvalue())


def _save_image(item, content):
    filename = f'{_slug(item.item_name)}.webp'
    storage = item.image.storage
    target = f'item/{filename}'
    if storage.exists(target):
        storage.delete(target)
    item.image.save(filename, content, save=False)
    item.save(update_fields=['image', 'updated_at'])
    return item.image.name


class Command(BaseCommand):
    help = 'Download real food images from Wikimedia Commons for all items'

    def add_arguments(self, parser):
        parser.add_argument(
            '--item',
            help='Only update items whose name contains this value',
        )
        parser.add_argument(
            '--delay',
            type=float,
            default=1.0,
            help='Seconds to wait between item lookups (default: 1.0)',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show the selected image for each item without downloading it',
        )

    def handle(self, *args, **options):
        items = Item.objects.all().order_by('item_name')
        if options['item']:
            items = items.filter(item_name__icontains=options['item'])

        total = items.count()
        if not total:
            raise CommandError('No matching items found.')

        updated = 0
        errors = 0

        self.stdout.write(f'Looking up images for {total} item(s)...')
        if connection.vendor != 'sqlite':
            self.stdout.write(
                self.style.WARNING(
                    f'Images will be written to {settings.MEDIA_ROOT}. '
                    'Make sure this path is persistent on the deployed server.'
                )
            )

        for index, item in enumerate(items, start=1):
            try:
                candidate = _find_item_image(item.item_name)
                if not candidate:
                    raise LookupError(f'no image found for {item.item_name!r}')
                title, source = candidate

                if options['dry_run']:
                    self.stdout.write(f'  [{index}/{total}] {item.item_name} -> {title}')
                    self.stdout.write(f'      {source}')
                else:
                    content = _download_image(source)
                    saved_name = _save_image(item, content)
                    updated += 1
                    self.stdout.write(f'  [{index}/{total}] {item.item_name} -> {saved_name} ({title})')
            except Exception as exc:
                errors += 1
                self.stderr.write(
                    self.style.WARNING(f'  [{index}/{total}] {item.item_name} — failed: {exc}')
                )

            if options['delay'] and index < total:
                time.sleep(options['delay'])

        if options['dry_run']:
            self.stdout.write(self.style.SUCCESS(f'\nDry run complete. {errors} error(s).'))
            return

        self.stdout.write(
            self.style.SUCCESS(f'\nDone. Updated {updated} item(s) ({errors} error(s)).')
        )
        if updated == 0:
            raise CommandError('No images were updated.')

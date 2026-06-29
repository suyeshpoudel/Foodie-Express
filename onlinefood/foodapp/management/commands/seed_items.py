from io import BytesIO
from pathlib import Path

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand

from foodapp.models import Item, ItemCategory

CATEGORY_ITEMS = {
    'Veg': [
        ('Paneer Butter Masala', 'Rich and creamy paneer curry with aromatic spices', 320, 20),
        ('Dal Makhani', 'Slow-cooked black lentils in creamy gravy', 250, 25),
        ('Veg Biryani', 'Fragrant basmati rice layered with mixed vegetables', 280, 30),
        ('Chole Bhature', 'Spicy chickpea curry served with fried bread', 200, 20),
        ('Palak Paneer', 'Cottage cheese in creamy spinach gravy', 300, 20),
        ('Aloo Gobi', 'Potato and cauliflower curry with turmeric', 180, 15),
        ('Veg Manchurian', 'Deep-fried vegetable balls in tangy sauce', 240, 20),
        ('Mushroom Masala', 'Mushrooms cooked in spiced onion-tomato gravy', 280, 20),
    ],
    'Non-Veg': [
        ('Chicken Biryani', 'Aromatic basmati rice with tender chicken and spices', 350, 30),
        ('Butter Chicken', 'Tender chicken in a rich tomato-cream sauce', 380, 25),
        ('Mutton Curry', 'Slow-cooked mutton in aromatic spice gravy', 450, 40),
        ('Egg Curry', 'Boiled eggs in spiced onion-tomato gravy', 200, 15),
        ('Chicken Tikka', 'Marinated chicken pieces grilled to perfection', 350, 25),
        ('Fish Curry', 'Fresh fish in tangy coconut-based gravy', 400, 25),
        ('Chicken 65', 'Crispy deep-fried chicken with curry leaves', 320, 20),
        ('Pepper Chicken', 'Spicy chicken roast with crushed peppercorns', 340, 25),
    ],
    'Chinese': [
        ('Hakka Noodles', 'Stir-fried noodles with vegetables and soy sauce', 220, 15),
        ('Gobi Manchurian', 'Cauliflower florets in spicy Manchurian sauce', 230, 18),
        ('Fried Rice', 'Wok-tossed rice with vegetables and egg', 200, 15),
        ('Spring Rolls', 'Crispy rolls stuffed with spiced vegetables', 180, 15),
        ('Chilli Chicken', 'Crispy chicken tossed in chilli-soy sauce', 350, 20),
        ('Schezwan Noodles', 'Spicy noodles with Schezwan sauce and veggies', 250, 18),
        ('Dim Sum', 'Steamed dumplings with vegetable filling', 300, 25),
        ('Hot & Sour Soup', 'Tangy and spicy soup with tofu and vegetables', 180, 10),
    ],
    'Italian': [
        ('Margherita Pizza', 'Classic pizza with mozzarella and fresh basil', 400, 25),
        ('Pasta Alfredo', 'Creamy pasta with parmesan and garlic', 350, 20),
        ('Risotto', 'Creamy arborio rice with mushrooms and parmesan', 380, 30),
        ('Bruschetta', 'Toasted bread with tomato, basil and olive oil', 250, 12),
        ('Lasagna', 'Layered pasta sheets with béchamel and meat sauce', 450, 35),
        ('Tiramisu', 'Classic Italian coffee-flavoured layered dessert', 300, 10),
        ('Fettuccine Carbonara', 'Pasta with creamy egg and bacon sauce', 380, 20),
        ('Garlic Bread', 'Toasted bread with garlic butter and herbs', 150, 10),
    ],
    'Desserts': [
        ('Gulab Jamun', 'Deep-fried milk solids soaked in sugar syrup', 120, 10),
        ('Brownie', 'Rich chocolate brownie with walnuts', 180, 10),
        ('Ice Cream Sundae', 'Vanilla ice cream with chocolate syrup and nuts', 200, 5),
        ('Cheesecake', 'Creamy New York style cheesecake', 250, 10),
        ('Rasmalai', 'Soft cottage cheese patties in sweetened milk', 150, 10),
        ('Chocolate Mousse', 'Light and airy dark chocolate mousse', 220, 10),
        ('Kheer', 'Creamy rice pudding with cardamom and nuts', 140, 15),
        ('Lemon Tart', 'Tangy lemon curd in buttery pastry shell', 230, 10),
    ],
    'Beverages': [
        ('Mango Lassi', 'Creamy yogurt drink blended with mango', 150, 5),
        ('Masala Chai', 'Spiced Indian tea with ginger and cardamom', 80, 5),
        ('Cold Coffee', 'Chilled coffee blended with milk and ice cream', 180, 5),
        ('Fresh Lime Soda', 'Refreshing lime soda with a hint of mint', 80, 3),
        ('Chocolate Shake', 'Thick chocolate milkshake with whipped cream', 200, 5),
        ('Green Tea', 'Japanese green tea with antioxidants', 60, 3),
        ('Fruit Punch', 'Mixed fruit juice with a splash of soda', 120, 5),
        ('Buttermilk', 'Spiced chilled buttermilk with cumin', 60, 3),
    ],
    'South Indian': [
        ('Masala Dosa', 'Crispy rice crepe with spiced potato filling', 180, 20),
        ('Idli Sambar', 'Steamed rice cakes served with lentil soup', 120, 15),
        ('Vada', 'Crispy lentil donuts served with chutney', 100, 12),
        ('Uttapam', 'Thick rice pancake topped with vegetables', 160, 18),
        ('Rava Dosa', 'Crispy semolina crepe with onions and chillies', 180, 18),
        ('Medu Vada', 'Fluffy lentil fritters with coconut chutney', 110, 12),
        ('Rasam Rice', 'Tangy tamarind soup served with steamed rice', 150, 15),
        ('Coconut Rice', 'Fragrant rice cooked with coconut and spices', 160, 15),
    ],
}

IMAGE_COLORS = [
    (255, 99, 71), (60, 179, 113), (70, 130, 180), (218, 165, 32),
    (147, 112, 219), (255, 140, 0), (0, 200, 200), (220, 20, 60),
    (50, 205, 150), (255, 105, 180), (210, 105, 30), (100, 149, 237),
    (34, 139, 34), (255, 215, 0), (72, 61, 139), (233, 150, 70),
    (0, 128, 128), (255, 182, 193), (154, 205, 50), (160, 82, 45),
]


def generate_item_image(item_name, color):
    from PIL import Image, ImageDraw, ImageFont

    size = 512
    img = Image.new('RGB', (size, size), color)
    draw = ImageDraw.Draw(img)

    try:
        font = ImageFont.truetype('/System/Library/Fonts/Helvetica.ttc', 36)
    except (IOError, OSError):
        try:
            font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 36)
        except (IOError, OSError):
            font = ImageFont.load_default()

    lines = []
    words = item_name.split()
    current = ''
    for word in words:
        test = current + ' ' + word if current else word
        bbox = draw.textbbox((0, 0), test, font=font)
        w = bbox[2] - bbox[0]
        if w > size - 40 and current:
            lines.append(current)
            current = word
        else:
            current = test
    if current:
        lines.append(current)

    total_h = sum(draw.textbbox((0, 0), line, font=font)[3] - draw.textbbox((0, 0), line, font=font)[1] for line in lines) + (len(lines) - 1) * 10
    y = (size - total_h) // 2

    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        tw = bbox[2] - bbox[0]
        x = (size - tw) // 2
        draw.text((x, y), line, fill='white', font=font)
        y += (bbox[3] - bbox[1]) + 10

    buf = BytesIO()
    img.save(buf, format='JPEG', quality=75)
    return ContentFile(buf.getvalue())


class Command(BaseCommand):
    help = 'Seeds the database with fake items and generated images'

    def handle(self, *args, **options):
        media_dir = Path(settings.MEDIA_ROOT) / 'item'
        media_dir.mkdir(parents=True, exist_ok=True)

        color_idx = 0
        total_created = 0

        for category_name, items in CATEGORY_ITEMS.items():
            cat, _ = ItemCategory.objects.get_or_create(category_name=category_name)
            for item_name, desc, price, prep_time in items:
                if Item.objects.filter(item_name=item_name, category=cat).exists():
                    self.stdout.write(f"  Skipping '{item_name}' — already exists")
                    continue

                color = IMAGE_COLORS[color_idx % len(IMAGE_COLORS)]
                color_idx += 1
                image_file = generate_item_image(item_name, color)
                safe_name = item_name.lower().replace(' ', '_')
                item = Item(
                    category=cat,
                    item_name=item_name,
                    description=desc,
                    price=price,
                    prep_time=prep_time,
                )
                item.image.save(f'{safe_name}.jpg', image_file, save=True)
                total_created += 1
                self.stdout.write(f"  Created '{item_name}' ({category_name}) — Rs.{price}")

        self.stdout.write(self.style.SUCCESS(f'\nDone. Created {total_created} items.'))

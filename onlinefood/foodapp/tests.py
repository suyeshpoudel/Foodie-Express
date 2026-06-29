import uuid
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from .models import Item, ItemCategory, Cart, CartItems, OrderPlaced, ItemReview, FavouriteItem


class ItemModelTest(TestCase):
    def setUp(self):
        self.cat, _ = ItemCategory.objects.get_or_create(category_name="Veg")
        self.item = Item.objects.create(
            category=self.cat,
            item_name="Test Pizza",
            description="Delicious pizza",
            price=500,
        )

    def test_item_creation(self):
        self.assertEqual(str(self.item), "Test Pizza")
        self.assertEqual(self.item.price, 500)

    def test_item_defaults(self):
        self.assertEqual(self.item._meta.get_field('price').default, 100)

    def test_category_str(self):
        self.assertEqual(str(self.cat), "Veg")


class CartModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="testuser", password="testpass123")
        self.cat, _ = ItemCategory.objects.get_or_create(category_name="Veg")
        self.item = Item.objects.create(category=self.cat, item_name="Burger", price=200)
        self.cart = Cart.objects.create(user=self.user, is_paid=False)
        self.cart_item = CartItems.objects.create(cart=self.cart, item=self.item, quantity=2)

    def test_cart_total(self):
        self.assertEqual(self.cart.get_cart_total(), 400)

    def test_cart_item_total_cost(self):
        self.assertEqual(self.cart_item.total_cost, 400)

    def test_cart_creation(self):
        self.assertFalse(self.cart.is_paid)
        self.assertEqual(self.cart.user.username, "testuser")


class OrderPlacedModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="testuser", password="testpass123")
        self.cat, _ = ItemCategory.objects.get_or_create(category_name="Non-Veg")
        self.item = Item.objects.create(category=self.cat, item_name="Chicken", price=350)
        self.order = OrderPlaced.objects.create(
            user=self.user, item=self.item, quantity=3, status="Pending"
        )

    def test_order_total(self):
        self.assertEqual(self.order.get_order_total, 1050)

    def test_order_default_status(self):
        self.assertEqual(self.order.status, "Pending")


class ViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username="testuser", password="testpass123")
        self.superuser = User.objects.create_superuser(
            username="admin", password="adminpass123", email="admin@test.com"
        )
        self.cat, _ = ItemCategory.objects.get_or_create(category_name="Veg")
        dummy_image = SimpleUploadedFile(
            name="test.jpg",
            content=b"",
            content_type="image/jpeg",
        )
        self.item = Item.objects.create(
            category=self.cat, item_name="Samosa", price=30, image=dummy_image
        )

    def test_home_page_status(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)

    def test_all_items_page(self):
        response = self.client.get('/all-items/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Samosa")

    def test_category_filter(self):
        response = self.client.get('/all-items/', {'category': 'Veg'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Samosa")

    def test_search_items(self):
        response = self.client.get('/all-items/', {'search': 'Samosa'})
        self.assertContains(response, "Samosa")
        response = self.client.get('/all-items/', {'search': 'Pizza'})
        self.assertNotContains(response, "Samosa")

    def test_login_view(self):
        response = self.client.post('/login/', {
            'username': 'testuser', 'password': 'testpass123'
        })
        self.assertEqual(response.status_code, 302)

    def test_login_invalid_password(self):
        response = self.client.post('/login/', {
            'username': 'testuser', 'password': 'wrongpass'
        })
        self.assertEqual(response.status_code, 302)

    def test_register_view(self):
        response = self.client.post('/register/', {
            'first_name': 'New', 'last_name': 'User',
            'username': 'newuser', 'password': 'newpass123'
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(User.objects.filter(username='newuser').exists())

    def test_cart_requires_login(self):
        response = self.client.get('/cart/')
        self.assertEqual(response.status_code, 302)

    def test_orders_requires_login(self):
        response = self.client.get('/orders/')
        self.assertEqual(response.status_code, 302)

    def test_add_item_page_loads(self):
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get('/add-item/')
        self.assertEqual(response.status_code, 200)

    def test_add_cart_requires_post(self):
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(f'/add-cart/{self.item.uid}')
        self.assertEqual(response.status_code, 405)

    def test_add_cart_post(self):
        self.client.login(username='testuser', password='testpass123')
        response = self.client.post(f'/add-cart/{self.item.uid}')
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Cart.objects.filter(user=self.user, is_paid=False).exists())

    def test_category_filter_empty(self):
        response = self.client.get('/all-items/', {'category': 'Italian'})
        self.assertNotContains(response, "Samosa")

    def test_delete_item_requires_post(self):
        self.client.login(username='admin', password='adminpass123')
        response = self.client.get(f'/delete-recipe/{self.item.uid}/')
        self.assertEqual(response.status_code, 405)

    def test_admin_dashboard_redirects_non_admin(self):
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get('/admin-dashboard/')
        self.assertEqual(response.status_code, 302)

    def test_admin_dashboard_loads(self):
        self.client.login(username='admin', password='adminpass123')
        response = self.client.get('/admin-dashboard/')
        self.assertEqual(response.status_code, 200)

    def test_delete_item_post(self):
        self.client.login(username='admin', password='adminpass123')
        response = self.client.post(f'/delete-recipe/{self.item.uid}/')
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Item.objects.filter(uid=self.item.uid).exists())

    def test_add_review_post(self):
        self.client.login(username='testuser', password='testpass123')
        response = self.client.post(f'/add-review/{self.item.uid}/', {
            'rating': 5, 'text': 'Delicious!'
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(ItemReview.objects.filter(user=self.user, item=self.item).exists())

    def test_add_review_requires_post(self):
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(f'/add-review/{self.item.uid}/')
        self.assertEqual(response.status_code, 405)

    def test_add_review_invalid_rating(self):
        self.client.login(username='testuser', password='testpass123')
        response = self.client.post(f'/add-review/{self.item.uid}/', {
            'rating': 6, 'text': 'Too high'
        })
        self.assertEqual(response.status_code, 302)
        self.assertFalse(ItemReview.objects.filter(user=self.user, item=self.item).exists())


class ItemReviewModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="reviewer", password="pass123")
        self.cat, _ = ItemCategory.objects.get_or_create(category_name="Veg")
        self.item = Item.objects.create(category=self.cat, item_name="Pasta", price=300)
        self.review = ItemReview.objects.create(
            user=self.user, item=self.item, rating=4, text="Great pasta!"
        )

    def test_review_creation(self):
        self.assertEqual(str(self.review), "reviewer - Pasta (4)")

    def test_review_rating_range(self):
        field = ItemReview._meta.get_field('rating')
        self.assertEqual(field.choices, [(1, 1), (2, 2), (3, 3), (4, 4), (5, 5)])

    def test_unique_user_item(self):
        with self.assertRaises(Exception):
            ItemReview.objects.create(
                user=self.user, item=self.item, rating=3, text="Duplicate"
            )


class FavouriteItemModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="favuser", password="pass123")
        self.cat, _ = ItemCategory.objects.get_or_create(category_name="Veg")
        self.item = Item.objects.create(category=self.cat, item_name="Burger", price=200)
        self.fav = FavouriteItem.objects.create(user=self.user, item=self.item)

    def test_favourite_creation(self):
        self.assertEqual(str(self.fav), "favuser ♥ Burger")

    def test_unique_user_item(self):
        with self.assertRaises(Exception):
            FavouriteItem.objects.create(user=self.user, item=self.item)


class FavouriteViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username="testuser", password="testpass123")
        self.cat, _ = ItemCategory.objects.get_or_create(category_name="Veg")
        dummy_image = SimpleUploadedFile(name="test.jpg", content=b"", content_type="image/jpeg")
        self.item = Item.objects.create(category=self.cat, item_name="Samosa", price=30, image=dummy_image)

    def test_toggle_favourite_add(self):
        self.client.login(username='testuser', password='testpass123')
        response = self.client.post(f'/toggle-favourite/{self.item.uid}/')
        self.assertEqual(response.status_code, 302)
        self.assertTrue(FavouriteItem.objects.filter(user=self.user, item=self.item).exists())

    def test_toggle_favourite_remove(self):
        FavouriteItem.objects.create(user=self.user, item=self.item)
        self.client.login(username='testuser', password='testpass123')
        response = self.client.post(f'/toggle-favourite/{self.item.uid}/')
        self.assertEqual(response.status_code, 302)
        self.assertFalse(FavouriteItem.objects.filter(user=self.user, item=self.item).exists())

    def test_toggle_favourite_requires_post(self):
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(f'/toggle-favourite/{self.item.uid}/')
        self.assertEqual(response.status_code, 405)

    def test_favourites_filter(self):
        self.client.login(username='testuser', password='testpass123')
        FavouriteItem.objects.create(user=self.user, item=self.item)
        response = self.client.get('/all-items/', {'favourites': 'true'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Samosa")
        self.assertContains(response, "fa-heart")

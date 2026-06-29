from django.db import models
from django.contrib.auth.models import User
from django.db.models import Sum
import uuid
# Create your models here.


class BaseModel(models.Model):
    uid = models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class ItemCategory(BaseModel):
    category_name = models.CharField(max_length=100, unique=True)

    class Meta:
        verbose_name_plural = 'Categories'

    def __str__(self):
        return self.category_name


class DeliveryZone(BaseModel):
    name = models.CharField(max_length=100, unique=True)
    delivery_time = models.IntegerField(default=30, help_text="Delivery time in minutes")

    class Meta:
        verbose_name_plural = 'Delivery Zones'

    def __str__(self):
        return f"{self.name} (~{self.delivery_time} min)"


class Item(BaseModel):
    category = models.ForeignKey(ItemCategory, on_delete=models.SET_NULL, null=True, blank=True, related_name='items')
    item_name = models.CharField(max_length=100)
    description = models.CharField(max_length=500, default='')
    price = models.IntegerField(default=100)
    image = models.ImageField(upload_to='item')
    prep_time = models.IntegerField(default=15, help_text="Preparation time in minutes")

    def __str__(self):
        return self.item_name


STATUS_CHOICES = (
    ('Pending', 'Pending'),
    ('Accepted', 'Accepted'),
    ('Packed', 'Packed'),
    ('On the way', 'On the way'),
    ('Delivered', 'Delivered'),
    ('Cancel', 'Cancel'),
)


class DeliveryAddress(BaseModel):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='delivery_addresses')
    full_name = models.CharField(max_length=100)
    phone = models.CharField(max_length=20)
    street = models.CharField(max_length=255)
    city = models.CharField(max_length=100)
    zip_code = models.CharField(max_length=20, blank=True, default='')
    is_default = models.BooleanField(default=False)
    zone = models.ForeignKey(DeliveryZone, null=True, blank=True, on_delete=models.SET_NULL, related_name='addresses')

    class Meta:
        verbose_name_plural = 'Delivery Addresses'

    def __str__(self):
        return f"{self.full_name}, {self.street}, {self.city}"


class Coupon(BaseModel):
    code = models.CharField(max_length=50, unique=True)
    discount_percent = models.IntegerField(default=10, help_text="Discount percentage (1-100)")
    valid_from = models.DateTimeField()
    valid_to = models.DateTimeField()
    max_uses = models.IntegerField(default=100)
    used_count = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)

    def is_valid(self):
        from django.utils import timezone
        now = timezone.now()
        return (
            self.is_active
            and self.valid_from <= now <= self.valid_to
            and self.used_count < self.max_uses
        )

    def __str__(self):
        return self.code


class Cart(BaseModel):
    user = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='carts')
    is_paid = models.BooleanField(default=False)
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default='Pending')
    delivery_address = models.ForeignKey(DeliveryAddress, null=True, blank=True, on_delete=models.SET_NULL, related_name='carts')
    coupon = models.ForeignKey(Coupon, null=True, blank=True, on_delete=models.SET_NULL, related_name='carts')

    def get_cart_total(self):
        return CartItems.objects.filter(cart=self).aggregate(total=Sum(models.F('quantity') * models.F('item__price')))['total']

class CartItems(BaseModel):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name='cart_item')
    item = models.ForeignKey(Item, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)

    @property
    def total_cost(self):
        return self.quantity * self.item.price
    
class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    phone = models.CharField(max_length=20, blank=True, default='')
    avatar = models.ImageField(upload_to='avatars', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username}'s Profile"


from django.db.models.signals import post_save
from django.dispatch import receiver

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)


class ItemReview(BaseModel):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reviews')
    item = models.ForeignKey(Item, on_delete=models.CASCADE, related_name='reviews')
    rating = models.IntegerField(choices=[(i, i) for i in range(1, 6)])
    text = models.TextField(blank=True, default='')

    class Meta:
        unique_together = ['user', 'item']
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.username} - {self.item.item_name} ({self.rating})"


class FavouriteItem(BaseModel):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='favourites')
    item = models.ForeignKey(Item, on_delete=models.CASCADE, related_name='favourited_by')

    class Meta:
        unique_together = ['user', 'item']
        verbose_name_plural = 'Favourite Items'

    def __str__(self):
        return f"{self.user.username} ♥ {self.item.item_name}"


class OrderPlaced(BaseModel):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    item = models.ForeignKey(Item, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    ordered_date = models.DateTimeField(auto_now_add=True)
    status = models.CharField(choices= STATUS_CHOICES, max_length= 50, default='Pending')    

    @property
    def get_order_total(self):
        return self.quantity * self.item.price
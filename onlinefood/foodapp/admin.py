from django.contrib import admin
from .models import Cart, CartItems, Item, ItemCategory, OrderPlaced, DeliveryAddress, Profile, ItemReview, FavouriteItem, DeliveryZone, Coupon


class CartAdmin(admin.ModelAdmin):
    list_display = ['uid_short', 'user', 'is_paid', 'status', 'get_total', 'created_at']
    list_editable = ['status']
    list_filter = ['status', 'is_paid']
    search_fields = ['user__username', 'user__email']
    ordering = ['-created_at']

    def uid_short(self, obj):
        return str(obj.uid)[:8]
    uid_short.short_description = 'Order ID'

    def get_total(self, obj):
        return obj.get_cart_total()
    get_total.short_description = 'Total'


class CartItemsAdmin(admin.ModelAdmin):
    list_display = ['item', 'cart', 'quantity', 'total_cost']
    list_filter = ['cart__is_paid']


class OrderPlacedAdmin(admin.ModelAdmin):
    list_display = ['uid_short', 'user', 'item', 'quantity', 'status', 'ordered_date']
    list_editable = ['status']
    list_filter = ['status']
    search_fields = ['user__username', 'item__item_name']

    def uid_short(self, obj):
        return str(obj.uid)[:8]
    uid_short.short_description = 'Order ID'


admin.site.register(ItemCategory)
class ItemAdmin(admin.ModelAdmin):
    list_display = ['item_name', 'category', 'price', 'prep_time', 'created_at']
    list_filter = ['category']
    search_fields = ['item_name']


admin.site.register(Item, ItemAdmin)
admin.site.register(Cart, CartAdmin)
admin.site.register(CartItems, CartItemsAdmin)
admin.site.register(OrderPlaced, OrderPlacedAdmin)
admin.site.register(DeliveryAddress)
admin.site.register(Profile)
admin.site.register(ItemReview)
admin.site.register(FavouriteItem)
admin.site.register(DeliveryZone)
admin.site.register(Coupon)

import hashlib
import hmac
import base64
import csv
import uuid
from datetime import datetime

from django.contrib import messages
import random
from django.contrib.auth.models import User
from django.shortcuts import redirect, render
from django.http import HttpResponse
from django.core.mail import send_mail
from django.template.loader import render_to_string
from datetime import timedelta

from .models import Cart, CartItems, Item, ItemCategory, OrderPlaced, DeliveryAddress, Profile, ItemReview, FavouriteItem, DeliveryZone, Coupon, STATUS_CHOICES
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.core.paginator import Paginator
from django.db.models import Avg, Sum, Count, F, Max
from django.db.models.functions import TruncDate
from django.utils import timezone
from django.conf import settings

# Create your views here.
def home(request):
    queryset = list(Item.objects.all())
    featured_items = random.sample(queryset, min(len(queryset), 4))
    context = {"featured_items": featured_items}

    queryset = Item.objects.all()

    if request.GET.get("search"):
        queryset = queryset.filter(item_name__icontains = request.GET.get("search"))

        context = {"items": queryset}

        return render(request, "items.html", context)

    return render(request, "home.html", context)


def login_page(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')

        if not User.objects.filter(username=username).exists():
            messages.error(request, "Invalid Username.")
            return redirect('/')
        
        user = authenticate(username = username, password = password)

        if user is None:
            messages.error(request, "Invalid Password")
            return redirect('/')
        else:
            login(request, user)
            return redirect('/')
    return render(request, 'login.html')

def logout_page(request):
    logout(request)
    return redirect('/')

def register(request):
    if request.method == "POST":
        first_name = request.POST.get("first_name")
        last_name = request.POST.get("last_name")
        username = request.POST.get("username")
        password = request.POST.get("password")

        user = User.objects.filter(username = username)

        if user.exists():
            messages.info(request, "Username already taken.")
            return redirect("/register/") 

        user = User.objects.create(
            first_name= first_name, 
            last_name= last_name,
            username= username, 
        )

        user.set_password(password)
        user.save()
        messages.info(request, "Account created successfully")
        return redirect("/register/")

    return render(request, "register.html")
    
@require_POST
@login_required(login_url= "/login/")
def add_cart(request, item_uid):
    user = request.user
    item_obj = Item.objects.get(uid = item_uid)
    cart , created = Cart.objects.get_or_create(user= user, is_paid = False)

    cart_items , created = CartItems.objects.get_or_create(
        cart = cart,
        item = item_obj,
    )

    if not created:
        cart_items.quantity += 1
        cart_items.save()
    else:
        cart_items.save()

    return redirect(request.META.get('HTTP_REFERER', '/'))

@login_required(login_url= "/login/")
def cart(request):
    context = _get_cart_context(request.user)
    return render(request, 'cart.html', context)

def _get_cart_context(user):
    addresses = DeliveryAddress.objects.filter(user=user)
    zones = DeliveryZone.objects.all()

    try:
        cart = Cart.objects.get(is_paid=False, user=user)
        cartItems = CartItems.objects.filter(cart=cart)
        if not cartItems.exists():
            context = {'carts': cart, 'cart_items': None, 'total_amount': None, 'addresses': addresses, 'zones': zones, 'estimated_arrival': None, 'discount_amount': None, 'coupon': None}
        else:
            subtotal = cart.get_cart_total()
            if subtotal is None:
                context = {'carts': cart, 'cart_items': cartItems, 'total_amount': None, 'addresses': addresses, 'zones': zones, 'estimated_arrival': None, 'discount_amount': None, 'coupon': None}
            else:
                coupon = cart.coupon
                discount_amount = 0
                if coupon and coupon.is_valid():
                    discount_amount = int(subtotal * coupon.discount_percent / 100)

                taxable = subtotal - discount_amount
                tax_amount = int(taxable * settings.ESEWA_TAX_RATE / 100)
                total_with_tax = taxable + tax_amount

                transaction_uuid = str(uuid.uuid4())
                signature_data = f"total_amount={total_with_tax},transaction_uuid={transaction_uuid},product_code={settings.ESEWA_PRODUCT_CODE}"
                signature = base64.b64encode(
                    hmac.new(
                        settings.ESEWA_SECRET_KEY.encode(),
                        signature_data.encode(),
                        hashlib.sha256,
                    ).digest()
                ).decode()

                max_prep = cartItems.aggregate(max_prep=Max('item__prep_time'))['max_prep'] or 0
                estimated_arrival = None
                if cart.delivery_address and cart.delivery_address.zone:
                    zone_delivery = cart.delivery_address.zone.delivery_time
                    total_minutes = max_prep + zone_delivery
                    estimated_arrival = datetime.now() + timedelta(minutes=total_minutes)

                context = {
                    'carts': cart,
                    'cart_items': cartItems,
                    'subtotal': subtotal,
                    'total_amount': total_with_tax,
                    'tax_amount': tax_amount,
                    'tax_rate': settings.ESEWA_TAX_RATE,
                    'discount_amount': discount_amount,
                    'coupon': coupon,
                    'transaction_uuid': transaction_uuid,
                    'signature': signature,
                    'esewa_product_code': settings.ESEWA_PRODUCT_CODE,
                    'esewa_success_url': settings.ESEWA_SUCCESS_URL,
                    'esewa_failure_url': settings.ESEWA_FAILURE_URL,
                    'addresses': addresses,
                    'zones': zones,
                    'estimated_arrival': estimated_arrival,
                }
    except Cart.DoesNotExist:
        context = {'carts': None, 'cart_items': None, 'total_amount': None, 'addresses': addresses, 'zones': zones, 'estimated_arrival': None, 'discount_amount': None, 'coupon': None}

    return context

@require_POST
@login_required(login_url='/login/')
def apply_coupon(request):
    code = request.POST.get('code', '').strip()
    if not code:
        messages.error(request, "Please enter a coupon code.")
        return redirect('/cart/')

    try:
        coupon = Coupon.objects.get(code__iexact=code)
    except Coupon.DoesNotExist:
        messages.error(request, "Invalid coupon code.")
        return redirect('/cart/')

    if not coupon.is_valid():
        messages.error(request, "This coupon has expired or reached its usage limit.")
        return redirect('/cart/')

    try:
        cart = Cart.objects.get(user=request.user, is_paid=False)
        cart.coupon = coupon
        cart.save()
        messages.success(request, f"Coupon '{coupon.code}' applied! You saved {coupon.discount_percent}%.")
    except Cart.DoesNotExist:
        messages.error(request, "No active cart found.")

    return redirect('/cart/')


@require_POST
@login_required(login_url='/login/')
def remove_coupon(request):
    try:
        cart = Cart.objects.get(user=request.user, is_paid=False)
        cart.coupon = None
        cart.save()
        messages.info(request, "Coupon removed.")
    except Cart.DoesNotExist:
        pass
    return redirect('/cart/')


@require_POST
@login_required(login_url= "/login/")
def remove_cart_items(request, cart_item_uid):
    try:
        CartItems.objects.get(uid=cart_item_uid).delete()
        if request.headers.get('HX-Request'):
            context = _get_cart_context(request.user)
            return render(request, 'cart_content.html', context)
        return redirect('/cart/')
    except Exception as e:
        print(e)


@require_POST
@login_required(login_url="/login/")
def update_cart_item(request, cart_item_uid):
    action = request.POST.get('action')
    try:
        cart_item = CartItems.objects.get(uid=cart_item_uid)
        if cart_item.cart.user != request.user:
            if request.headers.get('HX-Request'):
                return HttpResponse(status=403)
            messages.error(request, "Permission denied.")
            return redirect('/cart/')

        if action == 'increase':
            cart_item.quantity += 1
            cart_item.save()
        elif action == 'decrease':
            if cart_item.quantity <= 1:
                cart_item.delete()
            else:
                cart_item.quantity -= 1
                cart_item.save()

        if request.headers.get('HX-Request'):
            context = _get_cart_context(request.user)
            return render(request, 'cart_content.html', context)
        return redirect('/cart/')
    except CartItems.DoesNotExist:
        if request.headers.get('HX-Request'):
            return HttpResponse(status=404)
        messages.error(request, "Cart item not found.")
        return redirect('/cart/')

@login_required(login_url='/login/')
def check_order_updates(request):
    orders = Cart.objects.filter(is_paid=True, user=request.user).values('uid', 'status', 'updated_at')
    data = [{'uid': str(o['uid'])[:8], 'status': o['status'], 'updated_at': o['updated_at'].isoformat()} for o in orders]
    return JsonResponse(data, safe=False)


@login_required(login_url= "/login/")
def orders(request):
    orders = Cart.objects.filter(is_paid=True, user=request.user).order_by('-created_at')
    status_flow = ['Pending', 'Accepted', 'Packed', 'On the way', 'Delivered']
    for order in orders:
        try:
            order.status_index = status_flow.index(order.status)
        except ValueError:
            order.status_index = -1
    context = {'orders': orders, 'status_flow': status_flow}
    return render(request, 'orders.html', context)

@login_required(login_url= "/login/")
def add_item(request):
    categories = ItemCategory.objects.all()
    if request.method == "POST":
        data = request.POST

        item_name = data.get("item_name")
        description = data.get("description")
        category_uid = data.get("category")
        price = data.get("price")
        image = request.FILES.get("image")
        prep_time = data.get("prep_time", 15)

        category = ItemCategory.objects.filter(uid=category_uid).first()
        
        Item.objects.create(
            item_name=item_name,
            description=description,
            category=category,
            price=price,
            image=image,
            prep_time=prep_time,
        )

        return redirect('/all-items/')
    
    return render(request, 'add_item.html', {'categories': categories})
    

def all_items(request):
    queryset = Item.objects.all().order_by('-created_at')
    queryset = queryset.annotate(avg_rating=Avg('reviews__rating'))
    categories = ItemCategory.objects.all()

    if request.GET.get("search"):
        queryset = queryset.filter(item_name__icontains=request.GET.get("search"))

    category_filter = request.GET.get("category")
    if category_filter:
        queryset = queryset.filter(category__category_name__iexact=category_filter)

    show_favourites = request.GET.get("favourites") == "true"
    if show_favourites and request.user.is_authenticated:
        fav_uids = FavouriteItem.objects.filter(user=request.user).values_list('item__uid', flat=True)
        queryset = queryset.filter(uid__in=fav_uids)

    paginator = Paginator(queryset, 8)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    active_category = category_filter if category_filter else ''

    favourite_uids = set()
    if request.user.is_authenticated:
        favourite_uids = set(
            FavouriteItem.objects.filter(user=request.user).values_list('item__uid', flat=True)
        )

    context = {
        "items": page_obj,
        "page_obj": page_obj,
        "categories": categories,
        "active_category": active_category,
        "favourite_uids": favourite_uids,
        "show_favourites": show_favourites,
    }
    return render(request, "items.html", context)


def search_suggestions(request):
    q = request.GET.get('search', '').strip()
    if len(q) < 1:
        return HttpResponse('<div class="no-results">Start typing to search</div>')

    items = Item.objects.filter(item_name__icontains=q)[:6]
    if not items:
        return HttpResponse('<div class="no-results">No results found</div>')

    html = ''.join(
        f'<a href="/all-items/?search={item.item_name}">'
        f'<span>{item.item_name}</span>'
        f'<span class="suggestion-price">NPR {item.price}</span>'
        f'</a>'
        for item in items
    )
    return HttpResponse(html)


@require_POST
@login_required(login_url= "/login/")
def delete_item(request, item_uid):
    queryset = Item.objects.get(uid = item_uid)
    queryset.delete()
    return redirect("/all-items/")

@login_required(login_url= "/login/")
def update_item(request, item_uid):
    queryset = Item.objects.get(uid = item_uid)
    categories = ItemCategory.objects.all()

    if request.method == "POST":
        data = request.POST
        item_name = data.get("item_name")
        description = data.get("description")
        category_uid = data.get("category")
        price = data.get("price")
        image = request.FILES.get("image")
        prep_time = data.get("prep_time", 15)

        category = ItemCategory.objects.filter(uid=category_uid).first()

        queryset.item_name = item_name
        queryset.description = description
        queryset.category = category
        queryset.price = price
        queryset.prep_time = prep_time
        if image:
            queryset.image = image

        queryset.save()
        return redirect("/all-items/")

    context = {"item": queryset, "categories": categories}
    return render(request, "update_items.html", context)

@login_required(login_url="/login/")
def success(request):
    data = request.GET.get('data')
    if not data:
        messages.error(request, "Invalid payment response.")
        return redirect('/cart/')

    try:
        decoded = base64.b64decode(data).decode()
        import json
        payment_info = json.loads(decoded)
        if payment_info.get('status') != 'COMPLETE':
            messages.error(request, "Payment was not completed.")
            return redirect('/cart/')

        cart = Cart.objects.get(user=request.user, is_paid=False)
        cart.is_paid = True
        cart.status = 'Accepted'
        cart.save()

        items_data = []
        for cart_item in cart.cart_item.all():
            OrderPlaced.objects.create(
                user=request.user,
                item=cart_item.item,
                quantity=cart_item.quantity,
            )
            items_data.append({
                'name': cart_item.item.item_name,
                'quantity': cart_item.quantity,
                'price': cart_item.item.price,
                'total': cart_item.quantity * cart_item.item.price,
            })

        total = cart.get_cart_total()
        if total is None:
            total = 0

        estimated = datetime.now() + timedelta(minutes=45)

        subject = f"Order Confirmed - Foodie Express #{str(cart.uid)[:8]}"
        html_message = render_to_string('emails/order_confirmation.html', {
            'user': request.user,
            'order_uid': str(cart.uid)[:8],
            'ordered_date': datetime.now().strftime('%B %d, %Y at %I:%M %p'),
            'items': items_data,
            'total': total,
            'address': cart.delivery_address,
            'estimated_delivery': estimated.strftime('%I:%M %p'),
        })
        plain_message = f"Thank you for your order! Your order #{str(cart.uid)[:8]} has been confirmed."

        try:
            send_mail(
                subject,
                plain_message,
                settings.DEFAULT_FROM_EMAIL,
                [request.user.email],
                html_message=html_message,
                fail_silently=True,
            )
        except Exception:
            pass

        messages.success(request, "Payment successful!")
        return render(request, "success.html")
    except Exception as e:
        messages.error(request, f"Payment verification failed: {e}")
        return redirect('/cart/')

@login_required(login_url='/login/')
def admin_dashboard(request):
    if not request.user.is_superuser:
        return redirect('/')

    today = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
    paid_carts = Cart.objects.filter(is_paid=True)

    today_carts = paid_carts.filter(created_at__gte=today)
    today_count = today_carts.count()

    paid_items = CartItems.objects.filter(cart__is_paid=True)
    today_items = paid_items.filter(cart__created_at__gte=today)

    today_revenue = today_items.aggregate(
        total=Sum(F('quantity') * F('item__price'))
    )['total'] or 0

    total_revenue = paid_items.aggregate(
        total=Sum(F('quantity') * F('item__price'))
    )['total'] or 0

    total_orders = paid_carts.count()

    popular = paid_items.values(
        'item__item_name', 'item__uid'
    ).annotate(total_qty=Sum('quantity')).order_by('-total_qty')[:5]

    status_counts = paid_carts.values('status').annotate(count=Count('uid'))

    seven_days_ago = timezone.now() - timedelta(days=6)
    daily = paid_carts.filter(
        created_at__date__gte=seven_days_ago.date()
    ).annotate(
        day=TruncDate('created_at')
    ).values('day').annotate(
        count=Count('uid'),
        revenue=Sum(F('cart_item__quantity') * F('cart_item__item__price'))
    ).order_by('day')

    daily_labels = []
    daily_counts = []
    daily_revenues = []
    day_data = {d['day']: d for d in daily}
    for i in range(7):
        day = seven_days_ago.date() + timedelta(days=i)
        daily_labels.append(day.strftime('%a'))
        if day in day_data:
            daily_counts.append(day_data[day]['count'])
            daily_revenues.append(float(day_data[day]['revenue'] or 0))
        else:
            daily_counts.append(0)
            daily_revenues.append(0)

    recent_orders = paid_carts.order_by('-created_at')[:10]

    context = {
        'today_count': today_count,
        'today_revenue': today_revenue,
        'total_revenue': total_revenue,
        'total_orders': total_orders,
        'popular': popular,
        'status_counts': status_counts,
        'daily_labels': daily_labels,
        'daily_counts': daily_counts,
        'daily_revenues': daily_revenues,
        'orders': recent_orders,
        'status_choices': STATUS_CHOICES,
    }
    return render(request, 'admin_dashboard.html', context)


def all_orders(request):
    orders = Cart.objects.filter(is_paid=True).order_by('-created_at')
    context = {'orders': orders, 'status_choices': STATUS_CHOICES}
    return render(request, 'all_orders.html', context)


@login_required(login_url='/login/')
def export_orders_csv(request):
    if not request.user.is_superuser:
        return redirect('/')

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="orders_export.csv"'

    writer = csv.writer(response)
    writer.writerow(['Order ID', 'Customer Name', 'Customer Email', 'Date', 'Items', 'Subtotal (NPR)', 'Status', 'Delivery Address'])

    orders = Cart.objects.filter(is_paid=True).order_by('-created_at')
    for order in orders:
        items_list = ', '.join(
            f"{ci.quantity}x {ci.item.item_name}" for ci in order.cart_item.all()
        )
        addr = order.delivery_address
        address_str = f"{addr.full_name}, {addr.street}, {addr.city}" if addr else 'N/A'
        writer.writerow([
            str(order.uid)[:8],
            order.user.get_full_name() or order.user.username,
            order.user.email,
            order.created_at.strftime('%Y-%m-%d %H:%M'),
            items_list,
            order.get_cart_total() or 0,
            order.status,
            address_str,
        ])

    return response


@require_POST
@login_required(login_url='/login/')
def update_order_status(request, order_uid):
    if not request.user.is_superuser:
        messages.error(request, "Permission denied.")
        return redirect(request.META.get('HTTP_REFERER', '/admin-dashboard/'))

    new_status = request.POST.get('status')
    valid_statuses = [s[0] for s in STATUS_CHOICES]
    if new_status not in valid_statuses:
        messages.error(request, "Invalid status.")
        return redirect(request.META.get('HTTP_REFERER', '/admin-dashboard/'))

    try:
        order = Cart.objects.get(uid=order_uid)
        order.status = new_status
        order.save()
        messages.success(request, f"Order #{str(order.uid)[:8]} status updated to {new_status}.")
    except Cart.DoesNotExist:
        messages.error(request, "Order not found.")

    return redirect(request.META.get('HTTP_REFERER', '/admin-dashboard/'))


@require_POST
@login_required(login_url='/login/')
def add_address(request):
    user = request.user
    address_uid = request.POST.get('address_uid')

    if address_uid:
        try:
            address = DeliveryAddress.objects.get(uid=address_uid, user=user)
            cart = Cart.objects.get(is_paid=False, user=user)
            cart.delivery_address = address
            cart.save()
            messages.success(request, "Delivery address selected.")
        except (DeliveryAddress.DoesNotExist, Cart.DoesNotExist):
            messages.error(request, "Invalid address or cart.")
        return redirect('/cart/')

    full_name = request.POST.get('full_name')
    phone = request.POST.get('phone')
    street = request.POST.get('street')
    city = request.POST.get('city')
    zip_code = request.POST.get('zip_code', '')
    zone_uid = request.POST.get('zone')

    if not all([full_name, phone, street, city]):
        messages.error(request, "Please fill in all required address fields.")
        return redirect('/cart/')

    zone = DeliveryZone.objects.filter(uid=zone_uid).first() if zone_uid else None

    has_addresses = DeliveryAddress.objects.filter(user=user).exists()
    address = DeliveryAddress.objects.create(
        user=user,
        full_name=full_name,
        phone=phone,
        street=street,
        city=city,
        zip_code=zip_code,
        zone=zone,
        is_default=not has_addresses,
    )

    try:
        cart = Cart.objects.get(is_paid=False, user=user)
        cart.delivery_address = address
        cart.save()
    except Cart.DoesNotExist:
        pass

    messages.success(request, "Address added successfully.")
    return redirect('/cart/')


@login_required(login_url='/login/')
def manage_addresses(request):
    user = request.user
    if request.method == 'POST':
        action = request.POST.get('action')
        address_uid = request.POST.get('address_uid')
        if action == 'delete' and address_uid:
            DeliveryAddress.objects.filter(uid=address_uid, user=user).delete()
            messages.success(request, "Address deleted.")
        elif action == 'set_default' and address_uid:
            DeliveryAddress.objects.filter(user=user).update(is_default=False)
            DeliveryAddress.objects.filter(uid=address_uid, user=user).update(is_default=True)
            messages.success(request, "Default address updated.")
        return redirect('/manage-addresses/')

    addresses = DeliveryAddress.objects.filter(user=user).order_by('-is_default', '-created_at')
    zones = DeliveryZone.objects.all()
    context = {'addresses': addresses, 'zones': zones}
    return render(request, 'manage_addresses.html', context)


@require_POST
@login_required(login_url='/login/')
def toggle_favourite(request, item_uid):
    try:
        item = Item.objects.get(uid=item_uid)
    except Item.DoesNotExist:
        messages.error(request, "Item not found.")
        return redirect('/all-items/')

    fav, created = FavouriteItem.objects.get_or_create(
        user=request.user, item=item
    )
    if not created:
        fav.delete()
        is_fav = False
    else:
        is_fav = True

    if request.headers.get('HX-Request'):
        colour = 'var(--accent)' if is_fav else '#ccc'
        icon = 'fas' if is_fav else 'far'
        html = (
            f'<span id="fav-{item_uid}" class="position-absolute top-0 start-0 m-2">'
            f'<button hx-post="/toggle-favourite/{item_uid}/" hx-target="#fav-{item_uid}" hx-swap="outerHTML" '
            f'class="btn btn-sm rounded-circle p-1" '
            f'style="width: 34px; height: 34px; background: rgba(255,255,255,0.85); border: none; font-size: 1.2rem; line-height: 1; color: {colour};">'
            f'<i class="{icon} fa-heart"></i>'
            f'</button>'
            f'</span>'
        )
        return HttpResponse(html)

    return redirect(request.META.get('HTTP_REFERER', '/all-items/'))


@require_POST
@login_required(login_url='/login/')
def add_review(request, item_uid):
    try:
        item = Item.objects.get(uid=item_uid)
    except Item.DoesNotExist:
        messages.error(request, "Item not found.")
        return redirect('/all-items/')

    rating = request.POST.get('rating')
    text = request.POST.get('text', '')

    if not rating or not rating.isdigit() or int(rating) < 1 or int(rating) > 5:
        messages.error(request, "Please select a rating from 1 to 5.")
        return redirect('/all-items/')

    ItemReview.objects.update_or_create(
        user=request.user,
        item=item,
        defaults={'rating': int(rating), 'text': text},
    )

    messages.success(request, f"Review posted for {item.item_name}.")
    return redirect('/all-items/')


@login_required(login_url='/login/')
def profile(request):
    profile = request.user.profile
    if request.method == 'POST':
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        email = request.POST.get('email')
        phone = request.POST.get('phone')
        avatar = request.FILES.get('avatar')

        user = request.user
        if first_name:
            user.first_name = first_name
        if last_name:
            user.last_name = last_name
        if email:
            user.email = email
        user.save()

        if phone:
            profile.phone = phone
        if avatar:
            profile.avatar = avatar
        profile.save()

        messages.success(request, "Profile updated successfully.")
        return redirect('/profile/')

    from django.db.models import Sum, Count
    order_count = Cart.objects.filter(user=request.user, is_paid=True).count()
    total_spent = CartItems.objects.filter(
        cart__user=request.user, cart__is_paid=True
    ).aggregate(total=Sum('item__price'))['total'] or 0

    context = {
        'profile': profile,
        'order_count': order_count,
        'total_spent': total_spent,
    }
    return render(request, 'profile.html', context)


@require_POST
@login_required(login_url='/login/')
def change_password(request):
    old_password = request.POST.get('old_password')
    new_password = request.POST.get('new_password')
    confirm_password = request.POST.get('confirm_password')

    if not request.user.check_password(old_password):
        messages.error(request, "Current password is incorrect.")
        return redirect('/profile/')

    if new_password != confirm_password:
        messages.error(request, "New passwords do not match.")
        return redirect('/profile/')

    if len(new_password) < 6:
        messages.error(request, "Password must be at least 6 characters.")
        return redirect('/profile/')

    request.user.set_password(new_password)
    request.user.save()
    messages.success(request, "Password changed successfully. Please login again.")
    return redirect('/login/')


def custom_404(request, exception):
    return render(request, '404.html', status=404)


def custom_500(request):
    return render(request, '500.html', status=500)
from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.core.paginator import Paginator
from django.contrib.auth.hashers import make_password, check_password
from django.db.models import Sum, Value
from django.db.models.functions import Coalesce
from .models import Product, Customer, Sale, Alert
import requests

N8N_WEBHOOK_URL = 'http://localhost:5678/webhook-test/buy-product'


def get_logged_in_customer(request):
    customer_id = request.session.get('customer_id')
    if not customer_id:
        return None
    return Customer.objects.filter(id=customer_id).first()


def get_cart(request):
    return request.session.setdefault('cart', {})


def save_cart(request, cart):
    request.session['cart'] = cart
    request.session.modified = True


def get_cart_items(request):
    cart = get_cart(request)
    items = []
    total = Decimal('0.00')
    for product_id, quantity in cart.items():
        try:
            product = Product.objects.get(id=int(product_id))
        except Product.DoesNotExist:
            continue
        item_total = product.price * quantity
        items.append({
            'product': product,
            'quantity': quantity,
            'total': item_total,
        })
        total += item_total
    return items, total


def home(request):
    customer = get_logged_in_customer(request)
    if not customer:
        return redirect('login')

    categories = Product.objects.order_by('category').values_list('category', flat=True).distinct()
    products = Product.objects.all().order_by('name')
    top_sellers = Product.objects.annotate(
        sold_qty=Coalesce(Sum('sale__quantity'), Value(0))
    ).order_by('-sold_qty', 'name')[:6]
    counts = {
        'products': products.count(),
        'customers': Customer.objects.count(),
        'sales': Sale.objects.count(),
        'alerts': Alert.objects.count(),
    }
    return render(request, 'home.html', {
        'products': products,
        'top_sellers': top_sellers,
        'categories': categories,
        'counts': counts,
        'customer': customer,
    })


def customers(request):
    customer = get_logged_in_customer(request)
    customers_list = Customer.objects.all()
    return render(request, 'customers.html', {
        'customers': customers_list,
        'customer': customer,
    })


def sales(request):
    customer = get_logged_in_customer(request)
    sales_list = Sale.objects.select_related('product', 'customer').all()
    return render(request, 'sales.html', {
        'sales': sales_list,
        'customer': customer,
    })


def alerts(request):
    customer = get_logged_in_customer(request)
    alerts_list = Alert.objects.select_related('product').all()
    return render(request, 'alerts.html', {
        'alerts': alerts_list,
        'customer': customer,
    })


def categories(request):
    customer = get_logged_in_customer(request)
    if not customer:
        return redirect('login')
    categories_list = Product.objects.order_by('category').values_list('category', flat=True).distinct()
    return render(request, 'categories.html', {
        'categories': categories_list,
        'customer': customer,
    })


def category_products(request, category_name):
    customer = get_logged_in_customer(request)
    if not customer:
        return redirect('login')
    categories_list = Product.objects.order_by('category').values_list('category', flat=True).distinct()
    products = Product.objects.filter(category=category_name).order_by('name')
    paginator = Paginator(products, 8)
    page = request.GET.get('page', 1)
    page_obj = paginator.get_page(page)
    return render(request, 'category_products.html', {
        'customer': customer,
        'categories': categories_list,
        'category_name': category_name,
        'products': page_obj,
        'page_obj': page_obj,
    })


def cart(request):
    customer = get_logged_in_customer(request)
    if not customer:
        return redirect('login')

    items, total = get_cart_items(request)
    cart_message = request.session.pop('cart_message', None)
    return render(request, 'cart.html', {
        'customer': customer,
        'items': items,
        'total': total,
        'cart_message': cart_message,
    })


def add_to_cart(request, product_id):
    customer = get_logged_in_customer(request)
    if not customer:
        return redirect('login')
    if request.method != 'POST':
        return redirect('home')

    try:
        quantity = int(request.POST.get('quantity', '1'))
    except ValueError:
        quantity = 1
    quantity = max(1, quantity)

    cart = get_cart(request)
    product_key = str(product_id)
    cart[product_key] = cart.get(product_key, 0) + quantity
    save_cart(request, cart)
    request.session['cart_message'] = f'Added {quantity} item(s) to your cart.'
    return redirect('cart')


def remove_from_cart(request, product_id):
    customer = get_logged_in_customer(request)
    if not customer:
        return redirect('login')
    cart = get_cart(request)
    cart.pop(str(product_id), None)
    save_cart(request, cart)
    return redirect('cart')


def update_cart(request):
    customer = get_logged_in_customer(request)
    if not customer:
        return redirect('login')
    if request.method == 'POST':
        cart = get_cart(request)
        for key in list(cart.keys()):
            qty_str = request.POST.get(f'quantity_{key}')
            if qty_str is None:
                continue
            try:
                qty = int(qty_str)
            except ValueError:
                qty = 0
            if qty > 0:
                cart[key] = qty
            else:
                cart.pop(key, None)
        save_cart(request, cart)
    return redirect('cart')


def purchase_cart(request):
    customer = get_logged_in_customer(request)
    if not customer:
        return redirect('login')

    items, total = get_cart_items(request)
    if not items:
        request.session['cart_message'] = 'Your cart is empty.'
        return redirect('cart')

    saved_address = customer.address.strip() if customer.address else ''
    errors = []

    if request.method == 'POST':
        new_address = request.POST.get('new_address', '').strip()
        address_choice = request.POST.get('address_choice', 'saved')
        if new_address:
            customer.address = new_address
            customer.save()
            shipping_address = new_address
        elif saved_address and address_choice == 'saved':
            shipping_address = saved_address
        else:
            errors.append('Please provide a shipping address.')
            shipping_address = ''

        if not errors:
            for item in items:
                product = item['product']
                quantity = item['quantity']
                if quantity < 1:
                    errors.append(f'Invalid quantity for {product.name}.')
                elif product.stock < quantity:
                    errors.append(f'Not enough stock for {product.name}.')

        if not errors:
            for item in items:
                product = item['product']
                quantity = item['quantity']
                requests.post(N8N_WEBHOOK_URL, json={
                    'id': product.id,
                    'quantity': quantity,
                    'customer_id': customer.id,
                    'shipping_address': shipping_address,
                })
            save_cart(request, {})
            request.session['cart_message'] = 'Purchase request sent to backend successfully.'
            return redirect('cart')

    return render(request, 'purchase.html', {
        'customer': customer,
        'items': items,
        'total': total,
        'saved_address': saved_address,
        'errors': errors,
        'cart_mode': True,
    })


def purchase_product(request, product_id):
    customer = get_logged_in_customer(request)
    if not customer:
        return redirect('login')

    product = get_object_or_404(Product, id=product_id)
    saved_address = customer.address.strip() if customer.address else ''
    errors = []
    quantity = 1

    if request.method == 'POST':
        try:
            quantity = int(request.POST.get('quantity', '1'))
        except ValueError:
            quantity = 1
        if product.stock < 1:
            errors.append('This product is out of stock.')
            quantity = 0
        else:
            quantity = max(1, min(quantity, product.stock))

        new_address = request.POST.get('new_address', '').strip()
        address_choice = request.POST.get('address_choice', 'saved')
        if new_address:
            customer.address = new_address
            customer.save()
            shipping_address = new_address
        elif saved_address and address_choice == 'saved':
            shipping_address = saved_address
        else:
            errors.append('Please provide a shipping address.')
            shipping_address = ''

        if not errors:
            requests.post(N8N_WEBHOOK_URL, json={
                'id': product.id,
                'quantity': quantity,
                'customer_id': customer.id,
                'shipping_address': shipping_address,
            })
            request.session['cart_message'] = 'Purchase request sent to backend successfully.'
            return redirect('home')

    return render(request, 'purchase.html', {
        'customer': customer,
        'product': product,
        'saved_address': saved_address,
        'errors': errors,
        'quantity': quantity,
        'cart_mode': False,
    })


from django.http import JsonResponse

def checkout(request):
    if request.method == 'POST':
        return JsonResponse({'status': 'success', 'message': 'Checkout completed successfully!'})
    products = Product.objects.all()
    return render(request, 'checkout.html', {'products': products})


def signup(request):
    customer = get_logged_in_customer(request)
    if customer:
        return redirect('home')

    errors = []

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        email = request.POST.get('email', '').strip().lower()
        phone = request.POST.get('phone', '').strip()
        birthdate = request.POST.get('birthdate', '').strip()
        password = request.POST.get('password', '')
        password_confirm = request.POST.get('password_confirm', '')

        if not name or not email or not password or not password_confirm or not birthdate:
            errors.append('All fields are required.')
        if password != password_confirm:
            errors.append('Passwords do not match.')
        if Customer.objects.filter(email=email).exists():
            errors.append('A customer with that email already exists.')

        if not errors:
            try:
                new_customer = Customer.objects.create(
                    name=name,
                    email=email,
                    phone=phone,
                    birthdate=birthdate,
                    address='',
                    password=make_password(password),
                )
            except ValueError:
                errors.append('Please enter a valid birthdate.')
            else:
                request.session['customer_id'] = new_customer.id
                return redirect('home')

    return render(request, 'signup.html', {
        'customer': customer,
        'errors': errors,
    })


def login(request):
    customer = get_logged_in_customer(request)
    if customer:
        return redirect('home')

    errors = []

    if request.method == 'POST':
        email = request.POST.get('email', '').strip().lower()
        password = request.POST.get('password', '')

        if not email or not password:
            errors.append('Email and password are required.')
        else:
            account = Customer.objects.filter(email=email).first()
            if not account or not check_password(password, account.password):
                errors.append('Invalid email or password.')
            else:
                request.session['customer_id'] = account.id
                return redirect('home')

    return render(request, 'login.html', {
        'customer': customer,
        'errors': errors,
    })


def logout(request):
    request.session.pop('customer_id', None)
    return redirect('login')


def buy_product(request, product_id):
    return redirect('purchase_product', product_id=product_id)

def admin_dashboard(request):
    # Gather high-level stats for the top cards
    counts = {
        'products': Product.objects.count(),
        'customers': Customer.objects.count(),
        'sales': Sale.objects.count(),
        'alerts': Alert.objects.count(),
    }
    
    # Grab the 5 most recent alerts to show on the dashboard
    # (Assuming your Alert model has a standard 'id' or timestamp)
    recent_alerts = Alert.objects.select_related('product').all().order_by('-id')[:5]

    return render(request, 'admin_dashboard.html', {
        'counts': counts,
        'recent_alerts': recent_alerts
    })

def admin_inventory(request):
    # Fetch all products, prioritizing items with the lowest stock
    products = Product.objects.all().order_by('stock')
    
    return render(request, 'admin_inventory.html', {
        'products': products
    })

def admin_suppliers(request):
    # Note: Once you create a Supplier database model, you will query it here
    # suppliers = Supplier.objects.all()
    # return render(request, 'admin_suppliers.html', {'suppliers': suppliers})
    
    return render(request, 'admin_suppliers.html')

def admin_accounting(request):
    if request.method == 'POST':
        # This is where we will eventually catch the uploaded invoice file
        # and forward it to your n8n OCR webhook for data extraction.
        # For now, it just passes.
        pass
        
    return render(request, 'admin_accounting.html')

def admin_reports(request):
    # Calculate some quick native stats for the top cards
    total_revenue = Sale.objects.aggregate(
        total=Sum('product__price', default=0)
    )['total']
    
    total_sales_count = Sale.objects.count()
    
    return render(request, 'admin_reports.html', {
        'total_revenue': total_revenue,
        'total_sales_count': total_sales_count
    })

def admin_settings(request):
    if request.method == 'POST':
        # Handle saving settings (like WhatsApp numbers or n8n URLs) here later
        pass
        
    return render(request, 'admin_settings.html')
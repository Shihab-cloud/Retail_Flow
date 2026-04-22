import json
from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.core.paginator import Paginator
from django.contrib.auth.hashers import make_password, check_password
from django.db.models import F, Sum, Value
from django.db.models.functions import Coalesce
from .models import Product, Customer, Sale, Alert, Invoice, Supplier
import requests
from django.http import HttpResponse
from django.template.loader import get_template
from xhtml2pdf import pisa
import datetime
from django.contrib import messages

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
    # --- 1. Check n8n Status ---
    n8n_is_active = False
    try:
        # Ping the default n8n health check endpoint (assuming it runs on port 5678)
        response = requests.get('http://localhost:5678/healthz', timeout=1)
        if response.status_code == 200:
            n8n_is_active = True
    except (requests.ConnectionError, requests.Timeout):
        n8n_is_active = False

    # --- 2. Fetch Dashboard Data ---
    active_alerts = Alert.objects.all()
    alert_count = active_alerts.count()

    context = {
        'n8n_is_active': n8n_is_active,
        'active_alerts': active_alerts,
        'alert_count': alert_count,
        'product_count': Product.objects.count(),
        'customer_count': Customer.objects.count(),
        'sales_count': Sale.objects.count(),
    }
    return render(request, 'admin_dashboard.html', context)

def admin_inventory(request):
    # Fetch all products, prioritizing items with the lowest stock
    products = Product.objects.all().order_by('stock')
    
    return render(request, 'admin_inventory.html', {
        'products': products
    })

def admin_suppliers(request):
    # Handle the "Add New Vendor" form submission
    if request.method == 'POST':
        name = request.POST.get('name')
        email = request.POST.get('email')
        
        # Save to the new database table
        Supplier.objects.create(
            name=name,
            email=email,
            reliability_score=99, # Defaulting to 99% for new vendors
            avg_delivery_days=2   # Defaulting to 2 days
        )
        return redirect('admin_suppliers')

    # Fetch all suppliers to display in the Vendor Directory
    suppliers = Supplier.objects.all()
    
    return render(request, 'admin_suppliers.html', {'suppliers': suppliers})

def admin_accounting(request):
    # --- 1. HANDLE THE FILE UPLOAD (AI OCR Agent) ---
    if request.method == 'POST' and request.FILES.get('invoice_file'):
        uploaded_file = request.FILES['invoice_file']
        n8n_url = 'http://localhost:5678/webhook-test/invoice-ocr'
        files = {'invoice': (uploaded_file.name, uploaded_file.read(), uploaded_file.content_type)}
        
        try:
            requests.post(n8n_url, files=files)
        except Exception as e:
            print(f"Error sending to n8n: {e}")

    # --- 2. FETCH DASHBOARD DATA ---
    # The 'or 0.00' ensures the page doesn't crash if the tables are completely empty

    total_expenses = Invoice.objects.aggregate(Sum('amount'))['amount__sum'] or 0.00
    total_sales = Sale.objects.aggregate(
        total=Sum(F('product__price') * F('quantity'))
    )['total'] or 0.00
    
    # Calculate net profit
    net_profit = float(total_sales) - float(total_expenses)

    # Grab the 5 most recent invoices to display in your table
    recent_invoices = Invoice.objects.order_by('-date')[:5]

    # --- 3. SEND DATA TO HTML ---
    context = {
        'total_expenses': total_expenses,
        'total_sales': total_sales,
        'net_profit': net_profit,
        'recent_invoices': recent_invoices,
    }

    return render(request, 'admin_accounting.html', context)

def admin_reports(request):
    # 1. Top Cards Data (Live from DB)
    total_revenue = Sale.objects.aggregate(total=Sum('product__price', default=0))['total']
    total_sales_count = Sale.objects.count()
    stockouts_prevented = Alert.objects.count() 

    # 2. Demand Forecasting Line Chart (Presentation Data)
    chart_labels = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    chart_data = [12, 19, 15, 25, 22, 30, 28] # Realistic upward trend for the demo

    # 3. Expense & Fraud Pie Chart (Live from DB)
    pie_labels = ["Normal Sales", "Anomalies/Alerts"]
    pie_data = [total_sales_count, stockouts_prevented]

    context = {
        'total_revenue': total_revenue,
        'total_sales_count': total_sales_count,
        'stockouts_prevented': stockouts_prevented,
        # json.dumps() converts Python lists into JavaScript arrays
        'chart_labels': json.dumps(chart_labels),
        'chart_data': json.dumps(chart_data),
        'pie_labels': json.dumps(pie_labels),
        'pie_data': json.dumps(pie_data),
    }
    
    return render(request, 'admin_reports.html', context)

def admin_settings(request):
    if request.method == 'POST':
        # Handle saving settings (like WhatsApp numbers or n8n URLs) here later
        pass
        
    return render(request, 'admin_settings.html')

#def export_monthly_report(request):
    # 1. Setup the HTTP response to tell the browser to download a CSV file
    #response = HttpResponse(content_type='text/csv')
    #response['Content-Disposition'] = 'attachment; filename="RetailFlow_AI_Monthly_Report.csv"'

    #writer = csv.writer(response)

    # 2. Write the Executive Summary Header & Stats
    #writer.writerow(['RETAILFLOW AI - EXECUTIVE SUMMARY'])
    #writer.writerow(['-----------------------------------'])
    
    #total_revenue = Sale.objects.aggregate(total=Sum('product__price', default=0))['total']
    #total_sales_count = Sale.objects.count()
    #stockouts_prevented = Alert.objects.count()

    #writer.writerow(['Total Revenue ($)', total_revenue if total_revenue else 0.00])
    #writer.writerow(['Total Transactions', total_sales_count])
    #writer.writerow(['Stockouts Prevented', stockouts_prevented])
    
    #writer.writerow([]) # Add a blank line for spacing
    #writer.writerow([])

    # 3. Write the AI Alerts Log
    #writer.writerow(['AI SYSTEM ALERTS & ACTIONS'])
    #writer.writerow(['-----------------------------------'])
    #writer.writerow(['Timestamp', 'Product ID', 'AI Message'])

    # Fetch all alerts, newest first
    #alerts = Alert.objects.all().order_by('-created_at')
    #for alert in alerts:
        # Format the timestamp to be easily readable in Excel
        #formatted_date = alert.created_at.strftime("%Y-%m-%d %H:%M") if alert.created_at else "N/A"
        #writer.writerow([formatted_date, alert.product_id, alert.message])

    #return response

def export_monthly_report(request):
    # 1. Fetch live data
    total_revenue = Sale.objects.aggregate(total=Sum('product__price', default=0))['total']
    total_sales_count = Sale.objects.count()
    stockouts_prevented = Alert.objects.count()
    alerts = Alert.objects.all().order_by('-created_at')

    # 2. Prepare the context for the PDF template
    context = {
        'total_revenue': total_revenue if total_revenue else 0.00,
        'total_sales_count': total_sales_count,
        'stockouts_prevented': stockouts_prevented,
        'alerts': alerts,
        'current_date': datetime.datetime.now().strftime("%B %Y")
    }

    # 3. Render the HTML template
    template = get_template('report_pdf.html')
    html = template.render(context)

    # 4. Create the PDF response
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="RetailFlow_Monthly_Report.pdf"'

    # 5. Convert HTML to PDF
    pisa_status = pisa.CreatePDF(html, dest=response)
    
    if pisa_status.err:
        return HttpResponse('We had some errors generating the PDF')
    return response

def resolve_alert(request, alert_id):
    try:
        alert = Alert.objects.get(id=alert_id)
        alert.delete() # Removes the alert from the database
    except Alert.DoesNotExist:
        pass
    
    # Refresh the dashboard instantly
    return redirect('admin_dashboard')

def run_reorder_agent(request, product_id):
    """Triggers the n8n reorder agent for a specific product"""
    product = get_object_or_404(Product, id=product_id)
    
    # YOUR EXACT PRODUCTION URL:
    n8n_webhook_url = 'http://localhost:5678/webhook/buy-product'
    
    # The Payload: This is the data Django sends to n8n so the AI knows what to buy!
    payload = {
        'product_id': product.id,
        'product_name': product.name,
        # Change 'stock' to whatever your actual database field is named (e.g., 'quantity')
        'current_stock': product.stock, 
        'price': str(product.price)
    }

    try:
        # We use POST because we are sending data (the payload)
        response = requests.post(n8n_webhook_url, json=payload, timeout=3)
        if response.status_code == 200:
            messages.success(request, f"Success: AI Reorder Agent deployed for {product.name}!")
        else:
            messages.warning(request, "n8n received the request but returned an error.")
    except requests.exceptions.RequestException:
        messages.error(request, "Connection Error: Could not reach n8n. Is the workflow Active?")

    return redirect('admin_inventory') # Redirects back to the same page


def sync_n8n(request):
    """Triggers the global n8n inventory sync"""
    # For your Global Sync button, you will eventually want a separate workflow/URL.
    # For now, we will use a placeholder so the button works without crashing.
    n8n_webhook_url = 'http://localhost:5678/webhook/sync-inventory' 
    
    try:
        response = requests.get(n8n_webhook_url, timeout=2)
        messages.success(request, "Global Inventory Sync triggered!")
    except requests.exceptions.RequestException:
        messages.error(request, "Connection Error: Sync webhook not found yet.")

    return redirect('admin_inventory')
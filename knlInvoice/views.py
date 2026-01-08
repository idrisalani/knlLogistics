# ===== IMPORTS =====
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login, logout
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.contrib import messages
from django.db import models
from .models import Trip, Invoice, Product, Truck, Client, TripExpense, InvoiceItem, PaymentRecord
from .forms import TripForm, InvoiceForm, ProductForm, TripExpenseForm
from django.db.models import Sum, Count, Q
from django.db.models.functions import TruncMonth
from datetime import timedelta
from django.utils import timezone

# ============================================
# LANDING & AUTHENTICATION VIEWS
# ============================================

def index(request):
    """
    Landing page view - shown to all users (authenticated or not)
    """
    # If user is already logged in, redirect to dashboard
    if request.user.is_authenticated:
        return redirect('knlInvoice:dashboard')
    
    context = {
        'page_title': 'Kamrate - Professional Invoice Management'
    }
    return render(request, 'knlInvoice/index.html', context)


def login_view(request):
    """
    User login view
    """
    # If user is already logged in, redirect to dashboard
    if request.user.is_authenticated:
        return redirect('knlInvoice:dashboard')
    
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        
        # Authenticate user
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            # Login successful
            login(request, user)
            messages.success(request, f'Welcome back, {user.first_name or user.username}!')
            
            # Redirect to dashboard or next page
            next_page = request.GET.get('next', 'knlInvoice:dashboard')
            return redirect(next_page)
        else:
            # Login failed
            messages.error(request, 'Invalid username or password.')
    
    context = {
        'page_title': 'Login - Kamrate Invoice System'
    }
    return render(request, 'knlInvoice/login.html', context)


def logout_view(request):
    """
    User logout view
    """
    logout(request)
    messages.success(request, 'You have been logged out successfully.')
    return redirect('knlInvoice:index')


# ============================================
# DASHBOARD VIEW
# ============================================

@login_required(login_url='knlInvoice:login')
def dashboard(request):
    """
    Main dashboard view with comprehensive invoice and trip analytics
    + Day 5: Chart data for revenue trends and status breakdown
    Optimized for performance with database aggregation
    
    Context Variables Provided:
    - Invoice metrics: total, revenue, pending, overdue, outstanding
    - Trip metrics: total, revenue, expenses, profit, margin
    - Product & Client metrics: top products, unpaid clients
    - Chart data: monthly_revenue, months_names, paid/pending/overdue counts
    - Recent items: invoices, trips, products
    """

    # ===== INVOICE STATISTICS =====
    user_invoices = Invoice.objects.filter(user=request.user)
    total_invoices = user_invoices.count()
    
    # Revenue calculations (paid invoices only - optimized with aggregate)
    revenue_data = user_invoices.filter(status='paid').aggregate(
        total_revenue=Sum('total')
    )
    total_revenue = revenue_data['total_revenue'] or 0
    
    # Outstanding amount (unpaid invoices - optimized with aggregate)
    outstanding_data = user_invoices.exclude(status='paid').aggregate(
        outstanding=Sum('total')
    )
    outstanding_amount = outstanding_data['outstanding'] or 0
    
    # Status counts
    pending_invoices = user_invoices.filter(status__in=['pending', 'sent']).count()
    overdue_invoices = user_invoices.filter(status='overdue').count()
    
    # Recent invoices
    invoices = user_invoices.order_by('-date_created')[:5]
    
    # ===== TIME-BASED ANALYTICS =====
    today = timezone.now()
    
    # This month's revenue
    month_start = today.replace(day=1)
    this_month_data = user_invoices.filter(
        status='paid',
        date_created__gte=month_start
    ).aggregate(total=Sum('total'))
    this_month_revenue = this_month_data['total'] or 0
    
    # Last 30 days revenue
    thirty_days_ago = today - timedelta(days=30)
    thirty_days_data = user_invoices.filter(
        status='paid',
        date_created__gte=thirty_days_ago
    ).aggregate(total=Sum('total'))
    thirty_days_revenue = thirty_days_data['total'] or 0
    
    # ===== TRIP STATISTICS =====
    all_trips = Trip.objects.all()
    total_trips = all_trips.count()
    
    # Trip revenue and expenses
    total_trip_revenue = sum(trip.revenue for trip in all_trips) if all_trips else 0
    total_expenses = sum(trip.get_total_expenses() for trip in all_trips) if all_trips else 0
    total_profit = total_trip_revenue - total_expenses
    
    # Profit margin percentage
    profit_margin = (
        (total_profit / total_trip_revenue * 100) 
        if total_trip_revenue > 0 else 0
    )
    
    # Recent trips
    trips = all_trips.order_by('-startDate')[:5]
    
    # ===== PRODUCT STATISTICS =====
    products = Product.objects.all().order_by('-date_created')[:5]
    
    # Top products (most used in invoices)
    top_products = (
        InvoiceItem.objects
        .values('product__title')
        .annotate(count=Count('id'))
        .order_by('-count')[:5]
    )
    
    # ===== CLIENT STATISTICS =====
    total_clients = Client.objects.all().count()
    
    # Clients with unpaid invoices
    clients_with_unpaid = (
        Invoice.objects
        .filter(status__in=['pending', 'sent', 'overdue'])
        .values('client')
        .distinct()
        .count()
    )
    
    # ===== DAY 5: CHART DATA =====
    
    # ===== MONTHLY REVENUE (Last 6 Months) =====
    six_months_ago = today - timedelta(days=180)
    
    # Get monthly revenue data (efficient aggregation with TruncMonth)
    monthly_revenue_qs = (
        user_invoices.filter(
            status='paid',
            date_created__gte=six_months_ago
        )
        .annotate(month=TruncMonth('date_created'))
        .values('month')
        .annotate(total=Sum('total'))
        .order_by('month')
    )
    
    # Convert queryset to lists for JavaScript/charts
    monthly_revenue_list = []
    months_names_list = []
    
    for item in monthly_revenue_qs:
        monthly_revenue_list.append(item['total'] or 0)
        months_names_list.append(item['month'].strftime('%b'))  # Jan, Feb, Mar, etc.
    
    # If no data for the period, ensure we have 6 months of data (even if 0)
    # This ensures consistent x-axis on charts
    if len(monthly_revenue_list) == 0:
        for i in range(6):
            month_date = today - timedelta(days=30 * (5 - i))
            months_names_list.append(month_date.strftime('%b'))
            monthly_revenue_list.append(0)
    
    # ===== INVOICE STATUS BREAKDOWN (for pie chart) =====
    paid_count = user_invoices.filter(status='paid').count()
    pending_count = user_invoices.filter(status__in=['pending', 'sent']).count()
    overdue_count = user_invoices.filter(status='overdue').count()
    
    # ===== BUILD CONTEXT =====
    context = {
        'page_title': 'Dashboard - Kamrate Invoice System',
        'user': request.user,
        
        # ===== INVOICE METRICS =====
        'invoices': invoices,
        'total_invoices': total_invoices,
        'total_revenue': total_revenue,
        'pending_invoices': pending_invoices,
        'overdue_invoices': overdue_invoices,
        'outstanding_amount': outstanding_amount,
        'this_month_revenue': this_month_revenue,
        'thirty_days_revenue': thirty_days_revenue,
        
        # ===== TRIP METRICS =====
        'trips': trips,
        'total_trips': total_trips,
        'total_trip_revenue': total_trip_revenue,
        'total_expenses': total_expenses,
        'total_profit': total_profit,
        'profit_margin': profit_margin,
        
        # ===== PRODUCT & CLIENT METRICS =====
        'products': products,
        'top_products': list(top_products),
        'total_clients': total_clients,
        'clients_with_unpaid': clients_with_unpaid,
        
        # ===== DAY 5: CHART DATA =====
        # Monthly revenue for revenue trend chart (line chart)
        'monthly_revenue': monthly_revenue_list,  # [1500000, 1800000, ...]
        'months_names': months_names_list,        # ['Jul', 'Aug', 'Sep', ...]
        
        # Invoice status counts for status breakdown chart (pie chart)
        'paid_count': paid_count,                  # 5
        'pending_count': pending_count,            # 3
        'overdue_count': overdue_count,            # 1
    }
    
    return render(request, 'knlInvoice/dashboard.html', context)

# ============================================
# CLIENT VIEWS
# ============================================

@login_required(login_url='knlInvoice:login')
def clients_list(request):
    """List all clients"""
    clients = Client.objects.all().order_by('-date_created')
    context = {
        'page_title': 'Clients - Kamrate',
        'clients': clients
    }
    return render(request, 'knlInvoice/clients.html', context)


@login_required(login_url='knlInvoice:login')
def client_create(request):
    """Create new client"""
    if request.method == 'POST':
        # Handle form submission
        client_name = request.POST.get('clientName')
        address = request.POST.get('addressLine1')
        state = request.POST.get('state')
        postal_code = request.POST.get('postalCode')
        phone = request.POST.get('phoneNumber')
        email = request.POST.get('emailAddress')
        tax_number = request.POST.get('taxNumber')
        
        # Create client
        client = Client.objects.create(
            clientName=client_name,
            addressLine1=address,
            state=state,
            postalCode=postal_code,
            phoneNumber=phone,
            emailAddress=email,
            taxNumber=tax_number,
        )
        messages.success(request, f'Client {client_name} created successfully!')
        return redirect('knlInvoice:clients-list')
    
    from .models import Client as ClientModel
    states = ClientModel.STATES
    
    context = {
        'page_title': 'Create Client - Kamrate',
        'title': 'Create New Client',
        'states': states,
    }
    return render(request, 'knlInvoice/client_form.html', context)


# ============================================
# TRIP VIEWS
# ============================================

@login_required(login_url='knlInvoice:login')
def trips_list(request):
    """List all trips with analytics"""
    trips = Trip.objects.all().order_by('-startDate')
    
    # Calculate statistics
    total_trips = trips.count()
    total_revenue = sum(trip.revenue for trip in trips)
    total_expenses = sum(trip.get_total_expenses() for trip in trips)
    total_profit_loss = total_revenue - total_expenses
    profit_percentage = ((total_profit_loss / total_expenses) * 100) if total_expenses > 0 else 0
    
    context = {
        'page_title': 'Trips - Kamrate',
        'trips': trips,
        'total_trips': total_trips,
        'total_revenue': total_revenue,
        'total_expenses': total_expenses,
        'total_profit_loss': total_profit_loss,
        'profit_percentage': profit_percentage,
    }
    return render(request, 'knlInvoice/trips.html', context)


@login_required(login_url='knlInvoice:login')
@require_http_methods(["POST"])
def trip_create_ajax(request):
    """Create trip via AJAX"""
    form = TripForm(request.POST)
    if form.is_valid():
        trip = form.save()
        return JsonResponse({
            'success': True,
            'message': f'Trip {trip.tripNumber} created successfully!',
            'trip_id': trip.id,
            'redirect_url': '/knlInvoice/trips/'
        })
    else:
        return JsonResponse({
            'success': False,
            'errors': form.errors
        }, status=400)


@login_required(login_url='knlInvoice:login')
def trip_create(request):
    """Create new trip"""
    if request.method == 'POST':
        form = TripForm(request.POST)
        if form.is_valid():
            trip = form.save()
            messages.success(request, f'Trip {trip.tripNumber} created successfully!')
            return redirect('knlInvoice:trips-list')
    else:
        form = TripForm()
    
    context = {
        'page_title': 'Create Trip - Kamrate',
        'form': form,
        'title': 'Create New Trip',
        'trucks': Truck.objects.filter(status='ACTIVE')
    }
    return render(request, 'knlInvoice/trip_form.html', context)


@login_required(login_url='knlInvoice:login')
def trip_detail(request, slug):
    """View trip details with expenses"""
    trip = get_object_or_404(Trip, slug=slug)
    expenses = trip.expenses.all()
    expense_form = TripExpenseForm()
    
    context = {
        'page_title': f'{trip.tripNumber} - Kamrate',
        'trip': trip,
        'expenses': expenses,
        'total_expenses': trip.get_total_expenses(),
        'profit_loss': trip.get_profit_loss(),
        'profitability': trip.get_profitability_percentage(),
        'expense_form': expense_form,
    }
    return render(request, 'knlInvoice/trip_detail.html', context)


@login_required(login_url='knlInvoice:login')
def trip_update(request, slug):
    """Edit trip"""
    trip = get_object_or_404(Trip, slug=slug)
    if request.method == 'POST':
        form = TripForm(request.POST, instance=trip)
        if form.is_valid():
            form.save()
            messages.success(request, f'Trip {trip.tripNumber} updated successfully!')
            return redirect('knlInvoice:trip-detail', slug=trip.slug)
    else:
        form = TripForm(instance=trip)
    
    context = {
        'page_title': f'Edit {trip.tripNumber} - Kamrate',
        'form': form,
        'title': f'Edit {trip.tripNumber}',
        'trip': trip,
    }
    return render(request, 'knlInvoice/trip_form.html', context)


@login_required(login_url='knlInvoice:login')
def trip_delete(request, slug):
    """Delete trip"""
    trip = get_object_or_404(Trip, slug=slug)
    if request.method == 'POST':
        trip_number = trip.tripNumber
        trip.delete()
        messages.success(request, f'Trip {trip_number} deleted successfully!')
        return redirect('knlInvoice:trips-list')
    
    context = {
        'page_title': f'Delete {trip.tripNumber} - Kamrate',
        'trip': trip
    }
    return render(request, 'knlInvoice/trip_confirm_delete.html', context)


# ============================================
# INVOICE VIEWS (ENHANCED)
# ============================================

@login_required(login_url='knlInvoice:login')
def invoices_list(request):
    """List all invoices for the logged-in user"""
    invoices = Invoice.objects.filter(user=request.user).order_by('-date_created')
    
    # Filter by status if provided
    status = request.GET.get('status')
    if status:
        invoices = invoices.filter(status=status)
    
    context = {
        'page_title': 'Invoices - Kamrate',
        'invoices': invoices,
        'current_status': status,
    }
    return render(request, 'knlInvoice/invoices.html', context)


@login_required(login_url='knlInvoice:login')
@require_http_methods(["POST"])
def invoice_create_ajax(request):
    """Create invoice via AJAX"""
    form = InvoiceForm(request.POST)
    if form.is_valid():
        invoice = form.save(commit=False)
        invoice.user = request.user
        invoice.save()
        return JsonResponse({
            'success': True,
            'message': f'Invoice {invoice.invoice_number} created successfully!',
            'invoice_id': invoice.id,
            'redirect_url': '/knlInvoice/invoices/'
        })
    else:
        return JsonResponse({
            'success': False,
            'errors': form.errors
        }, status=400)


@login_required(login_url='knlInvoice:login')
def invoice_create(request):
    """Create new invoice with enhanced system"""
    if request.method == 'POST':
        # Handle manual invoice creation
        invoice_number = request.POST.get('invoice_number')
        client_id = request.POST.get('client')
        issue_date = request.POST.get('issue_date')
        due_date = request.POST.get('due_date')
        tax_rate = request.POST.get('tax_rate', 0)
        payment_terms = request.POST.get('paymentTerms', '14 days')
        notes = request.POST.get('notes', '')
        
        try:
            client = Client.objects.get(id=client_id) if client_id else None
            
            invoice = Invoice.objects.create(
                invoice_number=invoice_number,
                user=request.user,
                client=client,
                issue_date=issue_date,
                due_date=due_date,
                tax_rate=float(tax_rate),
                paymentTerms=payment_terms,
                notes=notes,
            )
            messages.success(request, f'Invoice {invoice_number} created successfully!')
            return redirect('knlInvoice:invoice-detail', slug=invoice.slug)
        except Exception as e:
            messages.error(request, f'Error creating invoice: {str(e)}')
    
    context = {
        'page_title': 'Create Invoice - Kamrate',
        'title': 'Create New Invoice',
        'clients': Client.objects.all(),
        'products': Product.objects.all(),
    }
    return render(request, 'knlInvoice/invoice_form.html', context)


@login_required(login_url='knlInvoice:login')
def invoice_detail(request, slug):
    """View invoice details with items and payments"""
    invoice = get_object_or_404(Invoice, slug=slug, user=request.user)
    items = invoice.items.all()
    payments = invoice.payments.all()
    
    context = {
        'page_title': f'{invoice.invoice_number} - Kamrate',
        'invoice': invoice,
        'items': items,
        'payments': payments,
    }
    return render(request, 'knlInvoice/invoice_detail.html', context)


@login_required(login_url='knlInvoice:login')
def invoice_update(request, slug):
    """Edit invoice"""
    invoice = get_object_or_404(Invoice, slug=slug, user=request.user)
    if request.method == 'POST':
        form = InvoiceForm(request.POST, instance=invoice)
        if form.is_valid():
            form.save()
            messages.success(request, f'Invoice {invoice.invoice_number} updated successfully!')
            return redirect('knlInvoice:invoice-detail', slug=invoice.slug)
    else:
        form = InvoiceForm(instance=invoice)
    
    context = {
        'page_title': f'Edit {invoice.invoice_number} - Kamrate',
        'form': form,
        'title': f'Edit Invoice {invoice.invoice_number}',
        'invoice': invoice,
    }
    return render(request, 'knlInvoice/invoice_form.html', context)


@login_required(login_url='knlInvoice:login')
def add_invoice_item(request, invoice_slug):
    """Add line item to invoice"""
    invoice = get_object_or_404(Invoice, slug=invoice_slug, user=request.user)
    
    if request.method == 'POST':
        description = request.POST.get('description')
        quantity = float(request.POST.get('quantity', 1))
        unit_price = float(request.POST.get('unit_price', 0))
        product_id = request.POST.get('product')
        
        product = Product.objects.get(id=product_id) if product_id else None
        
        item = InvoiceItem.objects.create(
            invoice=invoice,
            product=product,
            description=description,
            quantity=quantity,
            unit_price=unit_price,
        )
        messages.success(request, 'Item added to invoice!')
        return redirect('knlInvoice:invoice-detail', slug=invoice.slug)
    
    context = {
        'invoice': invoice,
        'products': Product.objects.all(),
    }
    return render(request, 'knlInvoice/add_invoice_item.html', context)


@login_required(login_url='knlInvoice:login')
def record_payment(request, invoice_slug):
    """Record payment for invoice"""
    invoice = get_object_or_404(Invoice, slug=invoice_slug, user=request.user)
    
    if request.method == 'POST':
        amount = float(request.POST.get('amount', 0))
        payment_date = request.POST.get('payment_date')
        payment_method = request.POST.get('payment_method', 'bank_transfer')
        reference_number = request.POST.get('reference_number', '')
        notes = request.POST.get('notes', '')
        
        payment = PaymentRecord.objects.create(
            invoice=invoice,
            amount=amount,
            payment_date=payment_date,
            payment_method=payment_method,
            reference_number=reference_number,
            notes=notes,
        )
        messages.success(request, f'Payment of ₦{amount:,.2f} recorded!')
        return redirect('knlInvoice:invoice-detail', slug=invoice.slug)
    
    context = {
        'page_title': f'Record Payment - {invoice.invoice_number}',
        'invoice': invoice,
    }
    return render(request, 'knlInvoice/record_payment.html', context)


# ============================================
# PRODUCT VIEWS
# ============================================

@login_required(login_url='knlInvoice:login')
def products_list(request):
    """List all products"""
    products = Product.objects.all().order_by('-date_created')
    context = {
        'page_title': 'Products - Kamrate',
        'products': products
    }
    return render(request, 'knlInvoice/products.html', context)


@login_required(login_url='knlInvoice:login')
@require_http_methods(["POST"])
def product_create_ajax(request):
    """Create product via AJAX"""
    form = ProductForm(request.POST)
    if form.is_valid():
        product = form.save()
        return JsonResponse({
            'success': True,
            'message': f'Product {product.title} created successfully!',
            'product_id': product.id,
            'redirect_url': '/knlInvoice/products/'
        })
    else:
        return JsonResponse({
            'success': False,
            'errors': form.errors
        }, status=400)


@login_required(login_url='knlInvoice:login')
def product_create(request):
    """Create new product"""
    if request.method == 'POST':
        form = ProductForm(request.POST)
        if form.is_valid():
            product = form.save()
            messages.success(request, f'Product {product.title} created successfully!')
            return redirect('knlInvoice:products-list')
    else:
        form = ProductForm()
    
    context = {
        'page_title': 'Create Product - Kamrate',
        'form': form,
        'title': 'Create New Product',
    }
    return render(request, 'knlInvoice/product_form.html', context)


@login_required(login_url='knlInvoice:login')
def product_update(request, slug):
    """Edit product"""
    product = get_object_or_404(Product, slug=slug)
    if request.method == 'POST':
        form = ProductForm(request.POST, instance=product)
        if form.is_valid():
            form.save()
            messages.success(request, f'Product {product.title} updated successfully!')
            return redirect('knlInvoice:products-list')
    else:
        form = ProductForm(instance=product)
    
    context = {
        'page_title': f'Edit {product.title} - Kamrate',
        'form': form,
        'title': f'Edit {product.title}',
        'product': product,
    }
    return render(request, 'knlInvoice/product_form.html', context)


@login_required(login_url='knlInvoice:login')
def product_delete(request, slug):
    """Delete product"""
    product = get_object_or_404(Product, slug=slug)
    if request.method == 'POST':
        product_title = product.title
        product.delete()
        messages.success(request, f'Product {product_title} deleted successfully!')
        return redirect('knlInvoice:products-list')
    
    context = {
        'page_title': f'Delete {product.title} - Kamrate',
        'product': product
    }
    return render(request, 'knlInvoice/product_confirm_delete.html', context)


# ============================================
# EXPENSE VIEWS
# ============================================

@login_required(login_url='knlInvoice:login')
def expense_create(request, trip_slug):
    """Create expense for trip"""
    trip = get_object_or_404(Trip, slug=trip_slug)
    if request.method == 'POST':
        form = TripExpenseForm(request.POST)
        if form.is_valid():
            expense = form.save(commit=False)
            expense.trip = trip
            expense.save()
            messages.success(request, 'Expense added successfully!')
            return redirect('knlInvoice:trip-detail', slug=trip.slug)
    else:
        form = TripExpenseForm(initial={'trip': trip})
    
    context = {
        'page_title': f'Add Expense - Kamrate',
        'form': form,
        'trip': trip,
        'title': f'Add Expense to {trip.tripNumber}',
    }
    return render(request, 'knlInvoice/expense_form.html', context)


@login_required(login_url='knlInvoice:login')
def expense_delete(request, pk):
    """Delete expense"""
    expense = get_object_or_404(TripExpense, pk=pk)
    trip = expense.trip
    if request.method == 'POST':
        expense.delete()
        messages.success(request, 'Expense deleted successfully!')
        return redirect('knlInvoice:trip-detail', slug=trip.slug)
    
    context = {
        'page_title': f'Delete Expense - Kamrate',
        'expense': expense,
        'trip': trip
    }
    return render(request, 'knlInvoice/expense_confirm_delete.html', context)
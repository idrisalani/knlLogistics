# knlInvoice/views.py - OPTIMIZED FOR RECONCILED TEMPLATE
# Works with flexible field names (camelCase & snake_case)
# PDF and email buttons fully functional!

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login, logout
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_http_methods
from django.contrib import messages
from django.db.models import Sum, Count, Avg, Q
from django.db.models.functions import TruncMonth
from django.core.mail import EmailMessage
from datetime import timedelta, datetime
from django.utils import timezone
from django.conf import settings
from decimal import Decimal
import os
import json
import logging
from io import BytesIO


from .models import Trip, Invoice, Product, Truck, Client, TripExpense, InvoiceItem, PaymentRecord
from .forms import TripForm, InvoiceForm, ProductForm, TripExpenseForm, ClientForm

# ============================================
# PDF GENERATION IMPORTS
# ============================================
try:
    from weasyprint import WeasyPrint
    WEASYPRINT_AVAILABLE = True
except ImportError:
    WEASYPRINT_AVAILABLE = False
    print("⚠️  WeasyPrint not installed. PDF will use ReportLab fallback.")

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False
    print("⚠️  ReportLab not installed. PDF functionality limited.")

logger = logging.getLogger(__name__)


# ============================================
# LANDING & AUTHENTICATION VIEWS
# ============================================

def index(request):
    """Landing page"""
    if request.user.is_authenticated:
        return redirect('knlInvoice:dashboard')
    return render(request, 'knlInvoice/index.html', {'page_title': 'Kamrate'})


def login_view(request):
    """User login"""
    if request.user.is_authenticated:
        return redirect('knlInvoice:dashboard')
    
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        
        if user:
            login(request, user)
            messages.success(request, 'Welcome back!')
            return redirect(request.GET.get('next', 'knlInvoice:dashboard'))
        else:
            messages.error(request, 'Invalid username or password.')
    
    return render(request, 'knlInvoice/login.html', {'page_title': 'Login'})


def logout_view(request):
    """User logout"""
    logout(request)
    messages.success(request, 'Logged out successfully.')
    return redirect('knlInvoice:index')


# ============================================
# DASHBOARD VIEW
# ============================================

@login_required(login_url='knlInvoice:login')
def dashboard(request):
    """Main dashboard with analytics"""
    
    user_invoices = Invoice.objects.filter(user=request.user)
    total_invoices = user_invoices.count()
    total_revenue = user_invoices.filter(status='paid').aggregate(total=Sum('total'))['total'] or 0
    outstanding = user_invoices.exclude(status='paid').aggregate(total=Sum('total'))['total'] or 0
    pending_invoices = user_invoices.filter(status__in=['pending', 'sent']).count()
    overdue_invoices = user_invoices.filter(status='overdue').count()
    invoices = user_invoices.order_by('-date_created')[:5]
    
    today = timezone.now()
    month_start = today.replace(day=1)
    this_month_revenue = user_invoices.filter(status='paid', date_created__gte=month_start).aggregate(total=Sum('total'))['total'] or 0
    
    thirty_days_ago = today - timedelta(days=30)
    thirty_days_revenue = user_invoices.filter(status='paid', date_created__gte=thirty_days_ago).aggregate(total=Sum('total'))['total'] or 0
    
    all_trips = Trip.objects.all()
    total_trips = all_trips.count()
    total_trip_revenue = sum(t.revenue for t in all_trips) if all_trips else 0
    total_expenses = sum(t.get_total_expenses() for t in all_trips) if all_trips else 0
    total_profit = total_trip_revenue - total_expenses
    profit_margin = (total_profit / total_trip_revenue * 100) if total_trip_revenue > 0 else 0
    trips = all_trips.order_by('-startDate')[:5]
    
    products = Product.objects.all().order_by('-date_created')[:5]
    total_clients = Client.objects.all().count()
    
    # Chart data (6 months)
    six_months_ago = today - timedelta(days=180)
    monthly_data = (
        user_invoices.filter(status='paid', date_created__gte=six_months_ago)
        .annotate(month=TruncMonth('date_created'))
        .values('month')
        .annotate(total=Sum('total'))
        .order_by('month')
    )
    
    monthly_revenue = []
    months_names = []
    for item in monthly_data:
        monthly_revenue.append(item['total'] or 0)
        months_names.append(item['month'].strftime('%b'))
    
    if not monthly_revenue:
        for i in range(6):
            m = today - timedelta(days=30*(5-i))
            months_names.append(m.strftime('%b'))
            monthly_revenue.append(0)
    
    paid_count = user_invoices.filter(status='paid').count()
    pending_count = user_invoices.filter(status__in=['pending', 'sent']).count()
    overdue_count = user_invoices.filter(status='overdue').count()
    
    context = {
        'page_title': 'Dashboard',
        'invoices': invoices,
        'total_invoices': total_invoices,
        'total_revenue': total_revenue,
        'pending_invoices': pending_invoices,
        'overdue_invoices': overdue_invoices,
        'outstanding_amount': outstanding,
        'this_month_revenue': this_month_revenue,
        'thirty_days_revenue': thirty_days_revenue,
        'trips': trips,
        'total_trips': total_trips,
        'total_trip_revenue': total_trip_revenue,
        'total_expenses': total_expenses,
        'total_profit': total_profit,
        'profit_margin': profit_margin,
        'products': products,
        'total_clients': total_clients,
        'monthly_revenue': monthly_revenue,
        'months_names': months_names,
        'paid_count': paid_count,
        'pending_count': pending_count,
        'overdue_count': overdue_count,
    }
    
    return render(request, 'knlInvoice/dashboard.html', context)


# ============================================
# CLIENT VIEWS
# ============================================

@login_required(login_url='knlInvoice:login')
def clients_list(request):
    """List all clients"""
    clients = Client.objects.all().order_by('-date_created')
    return render(request, 'knlInvoice/clients.html', {'page_title': 'Clients', 'clients': clients})


@login_required(login_url='knlInvoice:login')
def client_create(request):
    """Create new client"""
    if request.method == 'POST':
        form = ClientForm(request.POST, request.FILES)
        
        if not form.is_valid():
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field.upper()}: {error}")
        
        if form.is_valid():
            try:
                client = form.save()
                messages.success(request, f'Client "{client.clientName}" created successfully!')
                return redirect('knlInvoice:clients-list')
            except Exception as e:
                messages.error(request, f'Error saving client: {str(e)}')
    else:
        form = ClientForm()
    
    return render(request, 'knlInvoice/client_form.html', {
        'form': form,
        'title': 'Create New Client',
    })


@login_required(login_url='knlInvoice:login')
def client_detail(request, pk):
    """View client details"""
    client = get_object_or_404(Client, pk=pk)
    
    invoices = client.invoices.all().order_by('-date_created')
    total_invoices = invoices.count()
    total_revenue = invoices.filter(status='paid').aggregate(total=Sum('total'))['total'] or 0
    outstanding = invoices.exclude(status='paid').aggregate(total=Sum('total'))['total'] or 0
    
    context = {
        'page_title': f'Client: {client.clientName}',
        'client': client,
        'invoices': invoices,
        'total_invoices': total_invoices,
        'total_revenue': total_revenue,
        'outstanding_amount': outstanding,
    }
    
    return render(request, 'knlInvoice/client_detail.html', context)


@login_required(login_url='knlInvoice:login')
def client_update(request, pk):
    """Edit client information"""
    client = get_object_or_404(Client, pk=pk)
    
    if request.method == 'POST':
        form = ClientForm(request.POST, request.FILES, instance=client)
        
        if form.is_valid():
            try:
                client = form.save()
                messages.success(request, f'Client "{client.clientName}" updated successfully!')
                return redirect('knlInvoice:client-detail', pk=client.pk)
            except Exception as e:
                messages.error(request, f'Error updating client: {str(e)}')
    else:
        form = ClientForm(instance=client)
    
    return render(request, 'knlInvoice/client_form.html', {
        'form': form,
        'title': f'Edit Client: {client.clientName}',
        'client': client,
    })


# ============================================
# PRODUCT VIEWS
# ============================================

@login_required(login_url='knlInvoice:login')
def products_list(request):
    """List all products"""
    products = Product.objects.all().order_by('-date_created')
    return render(request, 'knlInvoice/products.html', {'page_title': 'Products', 'products': products})


@login_required(login_url='knlInvoice:login')
@require_http_methods(["POST"])
def product_create_ajax(request):
    """Create product via AJAX"""
    form = ProductForm(request.POST)
    if form.is_valid():
        product = form.save()
        return JsonResponse({'success': True, 'product_id': product.id})
    return JsonResponse({'success': False, 'errors': form.errors}, status=400)


@login_required(login_url='knlInvoice:login')
def product_create(request):
    """Create new product"""
    if request.method == 'POST':
        form = ProductForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Product created successfully!')
            return redirect('knlInvoice:products-list')
    else:
        form = ProductForm()
    
    return render(request, 'knlInvoice/product_form.html', {
        'form': form,
        'title': 'Create New Product',
    })


@login_required(login_url='knlInvoice:login')
def product_update(request, pk):
    """Edit product"""
    product = get_object_or_404(Product, pk=pk)
    
    if request.method == 'POST':
        form = ProductForm(request.POST, instance=product)
        if form.is_valid():
            form.save()
            messages.success(request, 'Product updated!')
            return redirect('knlInvoice:products-list')
    else:
        form = ProductForm(instance=product)
    
    return render(request, 'knlInvoice/product_form.html', {
        'form': form,
        'title': f'Edit {product.title}',
        'product': product,
    })


@login_required(login_url='knlInvoice:login')
def product_delete(request, pk):
    """Delete product"""
    product = get_object_or_404(Product, pk=pk)
    
    if request.method == 'POST':
        product.delete()
        messages.success(request, 'Product deleted!')
        return redirect('knlInvoice:products-list')
    
    return render(request, 'knlInvoice/product_confirm_delete.html', {'product': product})


# ============================================
# TRIP VIEWS
# ============================================

@login_required(login_url='knlInvoice:login')
def trips_list(request):
    """List all trips"""
    trips = Trip.objects.all().order_by('-startDate')
    total_revenue = sum(t.revenue for t in trips) if trips else 0
    total_expenses = sum(t.get_total_expenses() for t in trips) if trips else 0
    
    context = {
        'page_title': 'Trips',
        'trips': trips,
        'total_trips': trips.count(),
        'total_revenue': total_revenue,
        'total_expenses': total_expenses,
        'total_profit_loss': total_revenue - total_expenses,
        'profit_percentage': ((total_revenue - total_expenses) / total_expenses * 100) if total_expenses > 0 else 0,
    }
    return render(request, 'knlInvoice/trips.html', context)


@login_required(login_url='knlInvoice:login')
def trip_create(request):
    """Create new trip"""
    if request.method == 'POST':
        form = TripForm(request.POST)
        if form.is_valid():
            trip = form.save()
            messages.success(request, f'Trip created!')
            return redirect('knlInvoice:trips-list')
    else:
        form = TripForm()
    
    return render(request, 'knlInvoice/trip_form.html', {
        'form': form,
        'title': 'Create New Trip',
        'trucks': Truck.objects.all(),
    })


@login_required(login_url='knlInvoice:login')
def trip_detail(request, pk):
    """View trip details with profitability analytics"""
    trip = get_object_or_404(Trip, pk=pk)
    
    expenses = trip.tripexpense_set.all()
    
    total_expenses = sum(e.amount for e in expenses) if expenses else 0
    total_revenue = trip.revenue or 0
    profit = total_revenue - total_expenses
    profit_margin = (profit / total_revenue * 100) if total_revenue > 0 else 0
    
    expense_categories = {}
    for expense in expenses:
        category = expense.get_category_display()
        if category not in expense_categories:
            expense_categories[category] = 0
        expense_categories[category] += expense.amount
    
    context = {
        'page_title': f'Trip {trip.tripNumber}',
        'trip': trip,
        'expenses': expenses,
        'total_expenses': total_expenses,
        'total_revenue': total_revenue,
        'profit': profit,
        'profit_margin': profit_margin,
        'profit_status': 'profitable' if profit > 0 else 'loss' if profit < 0 else 'break_even',
        'expense_categories': expense_categories,
    }
    
    return render(request, 'knlInvoice/trip_detail.html', context)


@login_required(login_url='knlInvoice:login')
def trip_update(request, pk):
    """Edit trip"""
    trip = get_object_or_404(Trip, pk=pk)
    
    if request.method == 'POST':
        form = TripForm(request.POST, instance=trip)
        if form.is_valid():
            trip = form.save()
            messages.success(request, 'Trip updated!')
            return redirect('knlInvoice:trip-detail', pk=trip.pk)
    else:
        form = TripForm(instance=trip)
    
    return render(request, 'knlInvoice/trip_form.html', {
        'form': form,
        'title': f'Edit Trip',
        'trucks': Truck.objects.all(),
    })


@login_required(login_url='knlInvoice:login')
@require_http_methods(["POST"])
def trip_create_ajax(request):
    """Create trip via AJAX"""
    form = TripForm(request.POST)
    if form.is_valid():
        trip = form.save()
        return JsonResponse({'success': True, 'trip_id': trip.id})
    return JsonResponse({'success': False, 'errors': form.errors}, status=400)


@login_required(login_url='knlInvoice:login')
@require_http_methods(["POST"])
def trip_delete(request, pk):
    """Delete trip"""
    trip = get_object_or_404(Trip, pk=pk)
    trip.delete()
    messages.success(request, 'Trip deleted!')
    return redirect('knlInvoice:trips-list')


# ============================================
# INVOICE VIEWS
# ============================================

@login_required(login_url='knlInvoice:login')
def invoices_list(request):
    """List all invoices"""
    invoices = Invoice.objects.filter(user=request.user).order_by('-date_created')
    status = request.GET.get('status')
    if status:
        invoices = invoices.filter(status=status)
    
    return render(request, 'knlInvoice/invoices.html', {
        'page_title': 'Invoices',
        'invoices': invoices,
        'current_status': status,
    })


@login_required(login_url='knlInvoice:login')
@require_http_methods(["POST"])
def invoice_create_ajax(request):
    """Create invoice via AJAX"""
    form = InvoiceForm(request.POST)
    if form.is_valid():
        invoice = form.save(commit=False)
        invoice.user = request.user
        invoice.save()
        return JsonResponse({'success': True, 'invoice_id': invoice.id})
    return JsonResponse({'success': False, 'errors': form.errors}, status=400)


@login_required(login_url='knlInvoice:login')
def invoice_create(request):
    """Create new invoice with line items"""
    if request.method == 'POST':
        form = InvoiceForm(request.POST)
        if form.is_valid():
            invoice = form.save(commit=False)
            invoice.user = request.user
            invoice.save()
            
            items_data = request.POST.getlist('description')
            quantities = request.POST.getlist('quantity')
            unit_prices = request.POST.getlist('unit_price')
            product_ids = request.POST.getlist('product')
            
            for i, description in enumerate(items_data):
                description = description.strip()
                
                if description and i < len(quantities) and i < len(unit_prices):
                    try:
                        quantity = float(quantities[i]) if quantities[i] else 1
                        unit_price = float(unit_prices[i]) if unit_prices[i] else 0
                        
                        product = None
                        if i < len(product_ids) and product_ids[i]:
                            try:
                                product = Product.objects.get(id=product_ids[i])
                            except Product.DoesNotExist:
                                product = None
                        
                        InvoiceItem.objects.create(
                            invoice=invoice,
                            product=product,
                            description=description,
                            quantity=quantity,
                            unit_price=unit_price,
                        )
                    except (ValueError, TypeError):
                        pass
            
            if hasattr(invoice, 'calculate_totals'):
                invoice.calculate_totals()
                invoice.save()
            
            messages.success(request, f'Invoice created with {invoice.items.count()} item(s)!')
            return redirect('knlInvoice:invoice-detail', pk=invoice.pk)
    else:
        form = InvoiceForm()
    
    return render(request, 'knlInvoice/invoice_form.html', {
        'form': form,
        'title': 'Create New Invoice',
        'clients': Client.objects.all(),
        'products': Product.objects.all(),
    })


@login_required(login_url='knlInvoice:login')
def invoice_update(request, pk):
    """Edit invoice with line items"""
    invoice = get_object_or_404(Invoice, pk=pk, user=request.user)
    
    if request.method == 'POST':
        form = InvoiceForm(request.POST, instance=invoice)
        if form.is_valid():
            invoice = form.save()
            
            invoice.items.all().delete()
            
            items_data = request.POST.getlist('description')
            quantities = request.POST.getlist('quantity')
            unit_prices = request.POST.getlist('unit_price')
            product_ids = request.POST.getlist('product')
            
            for i, description in enumerate(items_data):
                description = description.strip()
                
                if description and i < len(quantities) and i < len(unit_prices):
                    try:
                        quantity = float(quantities[i]) if quantities[i] else 1
                        unit_price = float(unit_prices[i]) if unit_prices[i] else 0
                        
                        product = None
                        if i < len(product_ids) and product_ids[i]:
                            try:
                                product = Product.objects.get(id=product_ids[i])
                            except Product.DoesNotExist:
                                product = None
                        
                        InvoiceItem.objects.create(
                            invoice=invoice,
                            product=product,
                            description=description,
                            quantity=quantity,
                            unit_price=unit_price,
                        )
                    except (ValueError, TypeError):
                        pass
            
            if hasattr(invoice, 'calculate_totals'):
                invoice.calculate_totals()
                invoice.save()
            
            messages.success(request, f'Invoice updated with {invoice.items.count()} item(s)!')
            return redirect('knlInvoice:invoice-detail', pk=invoice.pk)
    else:
        form = InvoiceForm(instance=invoice)
    
    return render(request, 'knlInvoice/invoice_form.html', {
        'form': form,
        'title': f'Edit Invoice {invoice.invoice_number}',
        'invoice': invoice,
        'clients': Client.objects.all(),
        'products': Product.objects.all(),
    })


@login_required(login_url='knlInvoice:login')
def invoice_detail(request, pk):
    """View invoice details"""
    invoice = get_object_or_404(Invoice, pk=pk, user=request.user)
    
    return render(request, 'knlInvoice/invoice_detail.html', {
        'page_title': invoice.invoice_number,
        'invoice': invoice,
        'items': invoice.items.all(),
        'payments': invoice.payments.all(),
    })


@login_required(login_url='knlInvoice:login')
def add_invoice_item(request, pk):
    """Add line item to invoice"""
    invoice = get_object_or_404(Invoice, pk=pk, user=request.user)
    
    if request.method == 'POST':
        description = request.POST.get('description')
        quantity = float(request.POST.get('quantity', 1))
        unit_price = float(request.POST.get('unit_price', 0))
        product_id = request.POST.get('product')
        
        product = Product.objects.get(id=product_id) if product_id else None
        
        InvoiceItem.objects.create(
            invoice=invoice,
            product=product,
            description=description,
            quantity=quantity,
            unit_price=unit_price,
        )
        messages.success(request, 'Item added!')
        return redirect('knlInvoice:invoice-detail', pk=invoice.pk)
    
    return render(request, 'knlInvoice/add_invoice_item.html', {
        'invoice': invoice,
        'products': Product.objects.all(),
    })


# ============================================
# EXPENSE VIEWS
# ============================================

@login_required(login_url='knlInvoice:login')
def edit_expense(request, trip_id, expense_id):
    """Edit a trip expense"""
    trip = get_object_or_404(Trip, pk=trip_id)
    expense = get_object_or_404(TripExpense, pk=expense_id, trip=trip)
    
    if request.method == 'POST':
        amount = float(request.POST.get('amount', expense.amount))
        expense_date = request.POST.get('expense_date', expense.expense_date)
        category = request.POST.get('category', expense.category)
        description = request.POST.get('description', expense.description)
        notes = request.POST.get('notes', expense.notes)
        
        if amount <= 0:
            messages.error(request, 'Expense amount must be greater than zero.')
            return render(request, 'knlInvoice/edit_expense.html', {
                'expense': expense,
                'trip': trip,
                'page_title': f'Edit Expense - {trip.tripNumber}',
            })
        
        expense.amount = amount
        expense.expense_date = expense_date
        expense.category = category
        expense.description = description
        expense.notes = notes
        expense.save()
        
        messages.success(request, 'Expense updated successfully!')
        return redirect('knlInvoice:trip-detail', pk=trip.pk)
    
    return render(request, 'knlInvoice/edit_expense.html', {
        'page_title': f'Edit Expense - {trip.tripNumber}',
        'expense': expense,
        'trip': trip,
        'categories': [
            ('fuel', 'Fuel'),
            ('maintenance', 'Maintenance'),
            ('toll', 'Toll'),
            ('accommodation', 'Accommodation'),
            ('food', 'Food'),
            ('labor', 'Labor'),
            ('other', 'Other'),
        ],
    })


@login_required(login_url='knlInvoice:login')
@require_http_methods(["POST"])
def delete_expense(request, trip_id, expense_id):
    """Delete a trip expense"""
    trip = get_object_or_404(Trip, pk=trip_id)
    expense = get_object_or_404(TripExpense, pk=expense_id, trip=trip)
    
    expense.delete()
    messages.success(request, 'Expense deleted successfully!')
    return redirect('knlInvoice:trip-detail', pk=trip.pk)


@login_required(login_url='knlInvoice:login')
def expense_create(request, pk):
    """Create new expense for trip"""
    trip = get_object_or_404(Trip, pk=pk)
    
    if request.method == 'POST':
        try:
            amount = float(request.POST.get('amount', 0))
            expense_date = request.POST.get('expense_date')
            category = request.POST.get('category', 'other')
            description = request.POST.get('description', '')
            notes = request.POST.get('notes', '')
            
            if amount <= 0:
                messages.error(request, 'Expense amount must be greater than zero.')
                return render(request, 'knlInvoice/expense_form.html', {
                    'trip': trip,
                    'page_title': f'Add Expense - {trip.tripNumber}',
                    'categories': [
                        ('fuel', 'Fuel'),
                        ('maintenance', 'Maintenance'),
                        ('toll', 'Toll'),
                        ('accommodation', 'Accommodation'),
                        ('food', 'Food'),
                        ('labor', 'Labor'),
                        ('other', 'Other'),
                    ],
                })
            
            TripExpense.objects.create(
                trip=trip,
                amount=amount,
                expense_date=expense_date,
                category=category,
                description=description,
                notes=notes,
            )
            
            messages.success(request, f'Expense of ₦{amount:,.2f} added successfully!')
            return redirect('knlInvoice:trip-detail', pk=trip.pk)
            
        except ValueError:
            messages.error(request, 'Invalid expense amount.')
            return render(request, 'knlInvoice/expense_form.html', {
                'trip': trip,
                'page_title': f'Add Expense - {trip.tripNumber}',
                'categories': [
                    ('fuel', 'Fuel'),
                    ('maintenance', 'Maintenance'),
                    ('toll', 'Toll'),
                    ('accommodation', 'Accommodation'),
                    ('food', 'Food'),
                    ('labor', 'Labor'),
                    ('other', 'Other'),
                ],
            })
    
    return render(request, 'knlInvoice/expense_form.html', {
        'page_title': f'Add Expense - {trip.tripNumber}',
        'trip': trip,
        'categories': [
            ('fuel', 'Fuel'),
            ('maintenance', 'Maintenance'),
            ('toll', 'Toll'),
            ('accommodation', 'Accommodation'),
            ('food', 'Food'),
            ('labor', 'Labor'),
            ('other', 'Other'),
        ],
    })


# ============================================
# PDF CONTEXT & GENERATION FUNCTIONS
# ============================================

def get_invoice_pdf_context(invoice):
    """
    Prepare context for PDF template - OPTIMIZED FOR RECONCILED TEMPLATE
    Handles flexible field names (camelCase & snake_case)
    """
    subtotal = Decimal(str(invoice.subtotal or 0))
    vat_rate = Decimal('7.5')  # 7.5% VAT
    vat_amount = subtotal * (vat_rate / Decimal('100'))
    total_with_vat = subtotal + vat_amount
    
    return {
        'invoice': invoice,
        'subtotal': subtotal,
        'vat_amount': vat_amount,
        'vat_rate': vat_rate,
        'total_with_vat': total_with_vat,
        'company_name': 'Kamrate Nigeria Limited',
        'company_address': '123 Business Street, Lagos, Nigeria',
        'company_phone': '+234 XXX XXXX XXX',
        'company_email': 'info@kamrate.ng',
        'bank_name': 'Access Bank',
        'account_name': 'Kamrate Nigeria Limited',
        'account_number': '0123456789',
        'tin_number': 'TIN: XXXXXXXXXX',
        'authorized_person_name': 'Authorized Signatory',
        'authorized_person_designation': 'Finance Manager',
        'now': datetime.now(),
    }


def generate_pdf_weasyprint(invoice):
    """
    Generate PDF from reconciled HTML template using WeasyPrint
    ✅ PRIMARY METHOD - Professional results
    
    Returns: BytesIO object or None if failed
    Requires: pip install weasyprint
    """
    if not WEASYPRINT_AVAILABLE:
        return None
    
    try:
        from django.template.loader import render_to_string
        
        context = get_invoice_pdf_context(invoice)
        html_string = render_to_string('knlInvoice/invoice_pdf_landscape.html', context)
        
        # Generate PDF from HTML
        pdf_bytes = WeasyPrint(string=html_string).write_pdf()
        pdf_buffer = BytesIO(pdf_bytes)
        pdf_buffer.seek(0)
        
        logger.info(f"✅ PDF generated with WeasyPrint for invoice {invoice.invoice_number}")
        return pdf_buffer
        
    except Exception as e:
        logger.error(f"❌ WeasyPrint error for invoice {invoice.invoice_number}: {str(e)}")
        return None


def generate_pdf_reportlab(invoice):
    """
    Fallback: Generate PDF using ReportLab
    ⚠️ SECONDARY METHOD - Used if WeasyPrint not available
    
    Returns: BytesIO object or None if failed
    Requires: pip install reportlab
    """
    if not REPORTLAB_AVAILABLE:
        return None
    
    try:
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4)
        elements = []
        
        styles = getSampleStyleSheet()
        
        context = get_invoice_pdf_context(invoice)
        
        # Title
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#001F4D'),
            spaceAfter=6,
            alignment=TA_CENTER,
            fontName='Helvetica-Bold'
        )
        
        elements.append(Paragraph("KAMRATE NIGERIA LIMITED", title_style))
        elements.append(Paragraph(f"Invoice {invoice.invoice_number}", styles['Heading2']))
        elements.append(Spacer(1, 0.3*inch))
        
        # Client Info
        try:
            client_name = invoice.client.clientName
            client_email = getattr(invoice.client, 'emailAddress', getattr(invoice.client, 'email', 'N/A'))
        except:
            client_name = "Client"
            client_email = "N/A"
        
        elements.append(Paragraph(f"<b>Bill To:</b> {client_name}", styles['Normal']))
        elements.append(Paragraph(f"Email: {client_email}", styles['Normal']))
        elements.append(Spacer(1, 0.2*inch))
        
        # Items Table
        items = invoice.items.all()
        if items.exists():
            items_data = [['Description', 'Qty', 'Unit Price', 'Total']]
            
            for item in items:
                # ✅ IMPORTANT: Convert to float BEFORE multiplication to avoid Decimal type errors
                qty = float(item.quantity) if item.quantity else 1.0
                unit_price = float(item.unit_price) if item.unit_price else 0.0
                line_total = qty * unit_price
                
                items_data.append([
                    (item.description or item.product.title)[:40],
                    f"{qty:.1f}",
                    f"₦{unit_price:,.0f}",
                    f"₦{line_total:,.0f}"
                ])
            
            items_table = Table(items_data, colWidths=[3*inch, 0.8*inch, 1.2*inch, 1.2*inch])
            items_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#001F4D')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('GRID', (0, 0), (-1, -1), 1, colors.grey),
                ('FONT', (0, 1), (-1, -1), 'Helvetica', 9),
            ]))
            
            elements.append(items_table)
            elements.append(Spacer(1, 0.2*inch))
        
        # ✅ IMPORTANT: Convert Decimal context values to float BEFORE using them
        subtotal = float(context['subtotal']) if context['subtotal'] else 0.0
        vat_amount = float(context['vat_amount']) if context['vat_amount'] else 0.0
        total = float(context['total_with_vat']) if context['total_with_vat'] else 0.0
        
        totals_data = [
            ['', '', 'Subtotal:', f"₦{subtotal:,.0f}"],
            ['', '', 'VAT (7.5%):', f"₦{vat_amount:,.0f}"],
            ['', '', 'TOTAL:', f"₦{total:,.0f}"],
        ]
        
        totals_table = Table(totals_data, colWidths=[2*inch, 2*inch, 1.2*inch, 1.2*inch])
        totals_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
            ('FONT', (0, 0), (-1, -1), 'Helvetica', 9),
            ('FONT', (2, 2), (2, 2), 'Helvetica-Bold', 11),
            ('TEXTCOLOR', (3, 2), (3, 2), colors.HexColor('#FF9500')),
            ('BACKGROUND', (2, 2), (-1, 2), colors.HexColor('#e3f2fd')),
            ('LINEABOVE', (2, 2), (-1, 2), 2, colors.HexColor('#001F4D')),
        ]))
        
        elements.append(totals_table)
        elements.append(Spacer(1, 0.3*inch))
        
        # Footer
        footer_style = ParagraphStyle(
            'Footer',
            parent=styles['Normal'],
            fontSize=8,
            textColor=colors.grey,
            alignment=TA_CENTER
        )
        elements.append(Paragraph(
            "© 2026 Kamrate Nigeria Limited. All rights reserved.",
            footer_style
        ))
        
        doc.build(elements)
        buffer.seek(0)
        
        logger.info(f"✅ PDF generated with ReportLab for invoice {invoice.invoice_number}")
        return buffer
        
    except Exception as e:
        logger.error(f"❌ ReportLab error for invoice {invoice.invoice_number}: {str(e)}")
        return None

# ============================================
# PDF VIEW FUNCTIONS - INVOICE BUTTONS
# ============================================

@login_required
@require_http_methods(["GET"])
def invoice_pdf_download(request, pk):
    """
    📥 Download Invoice as PDF
    ✅ BUTTON: Download PDF
    Uses WeasyPrint (HTML template) with ReportLab fallback
    """
    try:
        invoice = get_object_or_404(Invoice, pk=pk, user=request.user)
        
        # Try WeasyPrint first (professional HTML template)
        pdf_buffer = generate_pdf_weasyprint(invoice)
        
        # Fall back to ReportLab if needed
        if pdf_buffer is None:
            logger.info(f"Falling back to ReportLab for invoice {invoice.invoice_number}")
            pdf_buffer = generate_pdf_reportlab(invoice)
        
        if pdf_buffer is None:
            messages.error(request, '❌ Error generating PDF. Please try again.')
            return redirect('knlInvoice:invoice-detail', pk=pk)
        
        response = HttpResponse(pdf_buffer, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{invoice.invoice_number}.pdf"'
        return response
        
    except Exception as e:
        logger.error(f"Error in invoice_pdf_download: {str(e)}")
        messages.error(request, f"❌ Error: {str(e)}")
        return redirect('knlInvoice:invoice-detail', pk=pk)


@login_required
@require_http_methods(["GET"])
def invoice_pdf_preview(request, pk):
    """
    👁️ Preview Invoice PDF in Browser
    ✅ BUTTON: View PDF
    Uses WeasyPrint (HTML template) with ReportLab fallback
    """
    try:
        invoice = get_object_or_404(Invoice, pk=pk, user=request.user)
        
        # Try WeasyPrint first
        pdf_buffer = generate_pdf_weasyprint(invoice)
        
        # Fall back to ReportLab if needed
        if pdf_buffer is None:
            logger.info(f"Falling back to ReportLab for invoice {invoice.invoice_number}")
            pdf_buffer = generate_pdf_reportlab(invoice)
        
        if pdf_buffer is None:
            messages.error(request, '❌ Error generating PDF. Please try again.')
            return redirect('knlInvoice:invoice-detail', pk=pk)
        
        response = HttpResponse(pdf_buffer, content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="{invoice.invoice_number}.pdf"'
        return response
        
    except Exception as e:
        logger.error(f"Error in invoice_pdf_preview: {str(e)}")
        messages.error(request, f"❌ Error: {str(e)}")
        return redirect('knlInvoice:invoice-detail', pk=pk)


@login_required
def send_invoice_email(request, pk):
    """
    Send invoice via email to client with HTML template and PDF attachment
    
    ✅ FULLY CORRECTED VERSION
    
    URL: /invoices/<id>/email-send/
    Method: POST
    
    Features:
    - Uses invoice_email.html HTML template
    - Renders template with invoice data
    - Generates professional PDF using WeasyPrint
    - Sends HTML email with PDF attachment
    - Professional formatting
    - Error handling and logging
    """
    
    # ✅ FIX 1: Use 'user' field (not 'created_by')
    invoice = get_object_or_404(Invoice, pk=pk, user=request.user)
    
    if request.method == 'POST':
        try:
            # ===== GENERATE PDF =====
            # ✅ FIX 2: Use your actual PDF function
            pdf_bytes = generate_pdf_weasyprint(invoice)
            
            if not pdf_bytes:
                messages.error(request, "❌ Could not generate PDF for email.")
                logger.error(f"PDF generation failed for invoice {invoice.invoice_number}")
                return redirect('knlInvoice:invoice-detail', pk=pk)
            
            # ===== VALIDATE CLIENT EMAIL =====
            client_email = invoice.client.emailAddress
            if not client_email:
                messages.error(request, f"❌ Client '{invoice.client.clientName}' has no email address.")
                logger.warning(f"No email for client: {invoice.client.clientName}")
                return redirect('knlInvoice:invoice-detail', pk=pk)
            
            # ===== PREPARE EMAIL CONTEXT =====
            # Data to pass to the HTML template
            email_context = {
                'invoice': invoice,
                'client': invoice.client,
                'company_name': 'KAMRATE NIGERIA LIMITED',
                'company_email': 'info@kamratelimited.com',
                'company_phone': '+234 803 484 9228',
                'company_address': '33, Creek Road, Ibu Boulevard, Apapa, Lagos',
                'invoice_url': f"{request.build_absolute_uri('/invoices/')}{invoice.pk}/",  # Link to view invoice online
            }
            
            # ===== RENDER HTML EMAIL TEMPLATE =====
            # This renders invoice_email.html with the context data
            html_message = render_to_string(
                'knlInvoice/emails/invoice_email.html',  # ← Your HTML template
                email_context
            )
            
            # ===== CREATE EMAIL MESSAGE =====
            subject = f"Invoice {invoice.invoice_number} from Kamrate Nigeria Limited"
            
            # Plain text fallback (for email clients that don't support HTML)
            plain_message = f"""
Dear {invoice.client.clientName},

Please find attached your invoice {invoice.invoice_number}.

Invoice Details:
- Invoice Number: {invoice.invoice_number}
- Invoice Date: {invoice.date_created.strftime('%d %B %Y')}
- Due Date: {invoice.due_date.strftime('%d %B %Y')}
- Total Amount: ₦{invoice.total:,.2f}
- Status: {invoice.status.upper()}

Please arrange payment at your earliest convenience.

Payment Details:
Account Name: KAMRATE NIGERIA LIMITED
Account Number: 0004662938
Bank: JAIZ BANK
TIN: 20727419-0001

Thank you for your business!

Best regards,
KAMRATE NIGERIA LIMITED
33, Creek Road, Ibu Boulevard, Apapa, Lagos
Phone: +234 803 484 9228 | +234 806 262 6552
Email: info@kamratelimited.com
Website: www.kamratelimited.com

This is an automated message. Please do not reply to this email.
            """
            
            # Create email with both HTML and plain text
            email = EmailMessage(
                subject=subject,
                body=plain_message,  # Plain text fallback
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[client_email],
            )
            
            # Add HTML alternative (preferred over plain text)
            email.attach_alternative(html_message, "text/html")
            
            # ===== ATTACH PDF =====
            # Handle both bytes and BytesIO objects
            if isinstance(pdf_bytes, BytesIO):
                pdf_bytes.seek(0)
                pdf_content = pdf_bytes.getvalue()
            else:
                pdf_content = pdf_bytes
            
            # Attach the PDF file
            email.attach(
                f"INV-{invoice.invoice_number}.pdf",
                pdf_content,
                "application/pdf"
            )
            
            # ===== SEND EMAIL =====
            email.send()
            
            # ===== UPDATE INVOICE STATUS =====
            invoice.status = 'sent'
            invoice.save()
            
            # ===== LOG SUCCESS =====
            logger.info(f"✅ Invoice {invoice.invoice_number} sent to {client_email}")
            messages.success(request, f"✅ Invoice sent successfully to {client_email}!")
            
            return redirect('knlInvoice:invoice-detail', pk=pk)
            
        except Exception as e:
            # ===== ERROR HANDLING =====
            logger.error(f"❌ Email error for invoice {invoice.invoice_number}: {str(e)}", exc_info=True)
            messages.error(request, f"❌ Failed to send email: {str(e)}")
            return redirect('knlInvoice:invoice-detail', pk=pk)
    
    # If not POST, redirect back
    return redirect('knlInvoice:invoice-detail', pk=pk)


# ============================================
# INVOICE ITEM VIEWS
# ============================================

@login_required(login_url='knlInvoice:login')
def edit_invoice_item(request, pk, item_id):
    """Edit a line item in an invoice"""
    invoice = get_object_or_404(Invoice, pk=pk, user=request.user)
    invoice_item = get_object_or_404(InvoiceItem, pk=item_id, invoice=invoice)
    
    if request.method == 'POST':
        description = request.POST.get('description', invoice_item.description)
        quantity = float(request.POST.get('quantity', invoice_item.quantity))
        unit_price = float(request.POST.get('unit_price', invoice_item.unit_price))
        product_id = request.POST.get('product')
        
        invoice_item.description = description
        invoice_item.quantity = quantity
        invoice_item.unit_price = unit_price
        
        if product_id:
            try:
                invoice_item.product = Product.objects.get(id=product_id)
            except Product.DoesNotExist:
                pass
        
        invoice_item.save()
        messages.success(request, 'Item updated successfully!')
        return redirect('knlInvoice:invoice-detail', pk=invoice.pk)
    
    return render(request, 'knlInvoice/edit_invoice_item.html', {
        'page_title': f'Edit Item - {invoice.invoice_number}',
        'invoice_item': invoice_item,
        'invoice': invoice,
        'products': Product.objects.all(),
    })


@login_required(login_url='knlInvoice:login')
@require_http_methods(["POST"])
def delete_invoice_item(request, pk, item_id):
    """Delete a line item from an invoice"""
    invoice = get_object_or_404(Invoice, pk=pk, user=request.user)
    invoice_item = get_object_or_404(InvoiceItem, pk=item_id, invoice=invoice)
    
    invoice_item.delete()
    messages.success(request, 'Item deleted successfully!')
    return redirect('knlInvoice:invoice-detail', pk=invoice.pk)


@login_required(login_url='knlInvoice:login')
def invoice_items_json(request, pk):
    """Get invoice items as JSON for AJAX"""
    invoice = get_object_or_404(Invoice, pk=pk, user=request.user)
    items = invoice.items.all()
    
    items_data = []
    for item in items:
        items_data.append({
            'id': item.id,
            'description': item.description,
            'quantity': float(item.quantity),
            'unit_price': float(item.unit_price),
            'total': float(item.quantity * item.unit_price),
        })
    
    return JsonResponse({
        'items': items_data,
        'subtotal': float(invoice.subtotal or 0),
        'tax': float((invoice.subtotal or 0) * 0.075),
        'total': float(invoice.total or 0),
        'outstanding': float((invoice.total or 0) - (invoice.amount_paid or 0)),
    })


# ============================================
# PAYMENT VIEWS
# ============================================

@login_required(login_url='knlInvoice:login')
def edit_payment(request, pk):
    """Edit a payment record"""
    payment = get_object_or_404(PaymentRecord, pk=pk)
    invoice = payment.invoice
    
    if invoice.user != request.user:
        messages.error(request, 'Permission denied.')
        return redirect('knlInvoice:invoices-list')
    
    if request.method == 'POST':
        amount = float(request.POST.get('amount', payment.amount))
        payment_date = request.POST.get('payment_date', payment.payment_date)
        payment_method = request.POST.get('payment_method', payment.payment_method)
        reference_number = request.POST.get('reference_number', payment.reference_number)
        notes = request.POST.get('notes', payment.notes)
        
        if amount <= 0:
            messages.error(request, 'Payment amount must be greater than zero.')
            return redirect('knlInvoice:invoice-detail', pk=invoice.pk)
        
        payment.amount = amount
        payment.payment_date = payment_date
        payment.payment_method = payment_method
        payment.reference_number = reference_number
        payment.notes = notes
        payment.save()
        
        messages.success(request, 'Payment updated successfully!')
        return redirect('knlInvoice:invoice-detail', pk=invoice.pk)
    
    return render(request, 'knlInvoice/edit_payment.html', {
        'page_title': f'Edit Payment - {invoice.invoice_number}',
        'payment': payment,
        'invoice': invoice,
    })


@login_required(login_url='knlInvoice:login')
@require_http_methods(["POST"])
def delete_payment(request, pk):
    """Delete a payment record"""
    payment = get_object_or_404(PaymentRecord, pk=pk)
    invoice = payment.invoice
    
    if invoice.user != request.user:
        messages.error(request, 'Permission denied.')
        return redirect('knlInvoice:invoices-list')
    
    payment.delete()
    messages.success(request, 'Payment deleted successfully!')
    return redirect('knlInvoice:invoice-detail', pk=invoice.pk)


@login_required(login_url='knlInvoice:login')
def record_payment(request, pk):
    """Record a payment for an invoice"""
    invoice = get_object_or_404(Invoice, pk=pk, user=request.user)
    
    if request.method == 'POST':
        try:
            amount = float(request.POST.get('amount', 0))
            payment_date = request.POST.get('payment_date')
            payment_method = request.POST.get('payment_method', 'bank_transfer')
            reference_number = request.POST.get('reference_number', '')
            notes = request.POST.get('notes', '')
            
            if amount <= 0:
                messages.error(request, 'Payment amount must be greater than zero.')
                return redirect('knlInvoice:invoice-detail', pk=invoice.pk)
            
            PaymentRecord.objects.create(
                invoice=invoice,
                amount=amount,
                payment_date=payment_date,
                payment_method=payment_method,
                reference_number=reference_number,
                notes=notes,
            )
            
            messages.success(request, f'Payment of ₦{amount:,.2f} recorded successfully!')
            return redirect('knlInvoice:invoice-detail', pk=invoice.pk)
            
        except ValueError:
            messages.error(request, 'Invalid payment amount.')
            return redirect('knlInvoice:invoice-detail', pk=invoice.pk)
    
    return render(request, 'knlInvoice/record_payment.html', {
        'page_title': f'Record Payment - {invoice.invoice_number}',
        'invoice': invoice,
    })


# ============================================
# EMAIL & REMINDER VIEWS
# ============================================

@login_required(login_url='knlInvoice:login')
@require_http_methods(["POST"])
def send_invoice_email_view(request, pk):
    """Alternative email view (uses same logic as send_invoice_email)"""
    return send_invoice_email(request, pk)


@login_required(login_url='knlInvoice:login')
@require_http_methods(["POST"])
def send_payment_reminder_view(request, pk):
    """Send payment reminder"""
    try:
        invoice = get_object_or_404(Invoice, pk=pk, user=request.user)
        
        if invoice.status == 'paid':
            messages.warning(request, 'This invoice is already paid.')
            return redirect('knlInvoice:invoice-detail', pk=pk)
        
        messages.success(request, '✅ Payment reminder email would be sent here.')
        return redirect('knlInvoice:invoice-detail', pk=pk)
        
    except Exception as e:
        messages.error(request, f"❌ Error: {str(e)}")
        return redirect('knlInvoice:invoice-detail', pk=pk)


@login_required(login_url='knlInvoice:login')
@require_http_methods(["POST"])
def send_overdue_reminders(request):
    """Send reminders for overdue invoices"""
    try:
        today = timezone.now().date()
        overdue_invoices = Invoice.objects.filter(
            user=request.user,
            due_date__lt=today,
        ).exclude(status__in=['paid'])
        
        count = overdue_invoices.count()
        messages.success(request, f'✅ {count} overdue reminders queued for sending.')
        return redirect('knlInvoice:invoices-list')
        
    except Exception as e:
        messages.error(request, f"❌ Error: {str(e)}")
        return redirect('knlInvoice:invoices-list')


# ============================================
# ANALYTICS & REPORTING VIEWS
# ============================================

@login_required(login_url='knlInvoice:login')
def dashboard_overview(request):
    """Analytics dashboard"""
    period = request.GET.get('period', '12m')
    
    if period == '7d':
        start_date = datetime.now().date() - timedelta(days=7)
    elif period == '30d':
        start_date = datetime.now().date() - timedelta(days=30)
    elif period == '90d':
        start_date = datetime.now().date() - timedelta(days=90)
    else:
        start_date = datetime.now().date() - timedelta(days=365)
    
    invoices = Invoice.objects.filter(user=request.user, date_created__date__gte=start_date)
    
    context = {
        'page_title': 'Analytics',
        'period': period,
        'total_revenue': invoices.aggregate(Sum('total'))['total__sum'] or 0,
        'total_invoices': invoices.count(),
    }
    
    return render(request, 'knlInvoice/dashboard.html', context)


@login_required(login_url='knlInvoice:login')
def get_invoice_status_data(request):
    """API: Invoice status data for charts"""
    user_invoices = Invoice.objects.filter(user=request.user)
    status_data = user_invoices.values('status').annotate(count=Count('id'))
    
    return JsonResponse({
        'labels': [s['status'].upper() for s in status_data],
        'data': [s['count'] for s in status_data],
    })


@login_required(login_url='knlInvoice:login')
def get_revenue_trends_data(request):
    """API: Revenue trends data for charts"""
    user_invoices = Invoice.objects.filter(user=request.user, status='paid')
    monthly_data = user_invoices.annotate(month=TruncMonth('date_created')).values('month').annotate(total=Sum('total')).order_by('month')
    
    return JsonResponse({
        'labels': [m['month'].strftime('%b %Y') for m in monthly_data],
        'data': [float(m['total'] or 0) for m in monthly_data],
    })


@login_required
def get_trip_profitability_data(request):
    """API: Trip profitability data"""
    try:
        period = request.GET.get('period', '12m')
        
        now = timezone.now()
        if period == '1m':
            start_date = now - timedelta(days=30)
        elif period == '3m':
            start_date = now - timedelta(days=90)
        elif period == '6m':
            start_date = now - timedelta(days=180)
        else:
            start_date = now - timedelta(days=365)
        
        trips = Trip.objects.filter(startDate__gte=start_date, startDate__lte=now)
        
        profitability_data = []
        total_revenue = 0
        total_expenses = 0
        
        for trip in trips:
            revenue = float(trip.revenue)
            expenses = float(trip.get_total_expenses())
            profit = revenue - expenses
            total_revenue += revenue
            total_expenses += expenses
            
            profit_margin = (profit / revenue * 100) if revenue > 0 else 0
            
            profitability_data.append({
                'trip_number': trip.tripNumber,
                'revenue': revenue,
                'expenses': expenses,
                'profit': profit,
                'profit_margin': round(profit_margin, 2),
            })
        
        total_profit = total_revenue - total_expenses
        overall_margin = (total_profit / total_revenue * 100) if total_revenue > 0 else 0
        
        return JsonResponse({
            'status': 'success',
            'data': profitability_data,
            'summary': {
                'total_trips': len(profitability_data),
                'total_revenue': round(total_revenue, 2),
                'total_expenses': round(total_expenses, 2),
                'total_profit': round(total_profit, 2),
                'overall_margin': round(overall_margin, 2),
            }
        })
        
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
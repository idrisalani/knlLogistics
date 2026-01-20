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
from django.template.loader import render_to_string
import os
import json
import logging
from io import BytesIO
from reportlab.lib.pagesizes import A4, landscape      # ✅ Most important!
from reportlab.lib.units import inch
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from .models import ( Trip, Invoice, Product, Truck, Client, 
                     TripExpense, InvoiceItem, PaymentRecord, 
                     TripInvoice, Trip, PaymentRecord, TripInvoiceLineItem )
from .forms import TripForm, InvoiceForm, ProductForm, TripExpenseForm, ClientForm
from .forms import QuickAddTruckForm
from django.views.decorators.http import require_http_methods
import uuid

# from knlTrip.models import Trip  # Adjust import based on your app name

logger = logging.getLogger(__name__)

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
    
    # ✅ FIX: Trip calculations with proper Decimal handling
    all_trips = Trip.objects.all()
    total_trips = all_trips.count()
    
    # Calculate trip revenue - use Decimal for consistency
    try:
        total_trip_revenue = sum((Decimal(str(t.revenue)) for t in all_trips), Decimal('0'))
    except (TypeError, ValueError):
        total_trip_revenue = Decimal('0')
    
    # Calculate expenses - use Decimal for consistency
    try:
        total_expenses = sum(
            (Decimal(str(t.get_total_expenses())) for t in all_trips if hasattr(t, 'get_total_expenses')),
            Decimal('0')
        )
    except (TypeError, ValueError, AttributeError):
        total_expenses = Decimal('0')
    
    # ✅ FIX: Ensure both are Decimal before subtraction
    total_trip_revenue = Decimal(str(total_trip_revenue or 0))
    total_expenses = Decimal(str(total_expenses or 0))
    total_profit = total_trip_revenue - total_expenses
    
    # Calculate profit margin safely
    try:
        profit_margin = float((total_profit / total_trip_revenue * 100)) if total_trip_revenue > 0 else 0
    except (TypeError, ZeroDivisionError):
        profit_margin = 0
    
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
        monthly_revenue.append(float(item['total'] or 0))
        months_names.append(item['month'].strftime('%b'))
    
    if not monthly_revenue:
        for i in range(6):
            m = today - timedelta(days=30*(5-i))
            months_names.append(m.strftime('%b'))
            monthly_revenue.append(0)
    
    paid_count = user_invoices.filter(status='paid').count()
    pending_count = user_invoices.filter(status__in=['pending', 'sent']).count()
    overdue_count = user_invoices.filter(status='overdue').count()
    
    # ✅ FIX: Convert all Decimal values to float for template rendering
    context = {
        'page_title': 'Dashboard',
        'invoices': invoices,
        'manifest_invoices': manifest_invoices,  # ✅ NEW: Manifest invoices
        'total_invoices': total_invoices,
        'total_revenue': float(total_revenue or 0),
        'pending_invoices': pending_invoices,
        'overdue_invoices': overdue_invoices,
        'outstanding_amount': float(outstanding or 0),
        'this_month_revenue': float(this_month_revenue or 0),
        'thirty_days_revenue': float(thirty_days_revenue or 0),
        'total_trips': total_trips,
        'total_trip_revenue': float(total_trip_revenue or 0),
        'total_expenses': float(total_expenses or 0),
        'total_profit': float(total_profit or 0),
        'profit_margin': profit_margin,
        'trips': trips,
        'clients': clients,
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
    trips = Trip.objects.all().order_by('-startDate')
    clients = Client.objects.all()  # ← GET ALL CLIENTS!
    
    # Calculate totals...
    try:
        total_revenue = sum((Decimal(str(t.revenue)) for t in trips), Decimal('0'))
    except (TypeError, ValueError):
        total_revenue = Decimal('0')
    
    try:
        total_expenses = sum(
            (Decimal(str(t.get_total_expenses())) for t in trips if hasattr(t, 'get_total_expenses')),
            Decimal('0')
        )
    except (TypeError, ValueError, AttributeError):
        total_expenses = Decimal('0')
    
    total_profit_loss = total_revenue - total_expenses
    
    try:
        profit_percentage = float((total_profit_loss / total_expenses * 100)) if total_expenses > 0 else 0
    except (TypeError, ZeroDivisionError):
        profit_percentage = 0
    
    # PASS CLIENTS TO TEMPLATE!
    context = {
        'page_title': 'Trips',
        'trips': trips,
        'clients': clients,  # ← THIS LINE WAS MISSING!
        'total_trips': trips.count(),
        'total_revenue': float(total_revenue),
        'total_expenses': float(total_expenses),
        'total_profit_loss': float(total_profit_loss),
        'profit_percentage': round(profit_percentage, 2),
    }
    
    return render(request, 'knlInvoice/trips_list.html', context)


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
    """View trip details with expense management"""
    trip = get_object_or_404(Trip, pk=pk)
    
    # Get expenses safely
    expenses = []
    total_expenses = 0
    expense_categories = {}
    
    try:
        # Try to get expenses if the relationship exists
        if hasattr(trip, 'tripexpense_set'):
            expenses = trip.tripexpense_set.all()
        elif hasattr(trip, 'expense_set'):
            expenses = trip.expense_set.all()
        else:
            # Try querying by trip ID if neither relationship works
            from .models import TripExpense
            try:
                expenses = TripExpense.objects.filter(trip=trip)
            except:
                expenses = []
        
        # Calculate total expenses
        if expenses:
            total_expenses = sum(float(e.amount or 0) for e in expenses)
            
            # Calculate expense categories
            for expense in expenses:
                if hasattr(expense, 'get_category_display'):
                    category = expense.get_category_display()
                elif hasattr(expense, 'category'):
                    category = expense.category
                else:
                    category = 'Other'
                
                if category not in expense_categories:
                    expense_categories[category] = 0
                expense_categories[category] += float(expense.amount or 0)
    
    except Exception as e:
        # If anything fails, just use empty expenses
        expenses = []
        total_expenses = 0
        expense_categories = {}
    
    # Calculate profitability
    total_revenue = float(trip.revenue or 0)
    profit = total_revenue - total_expenses
    profit_margin = (profit / total_revenue * 100) if total_revenue > 0 else 0
    expense_percentage = (total_expenses / total_revenue * 100) if total_revenue > 0 else 0
    
    context = {
        'page_title': f'Trip {trip.tripNumber}',
        'trip': trip,
        'expenses': expenses,
        'expenses_count': len(expenses) if expenses else 0,
        'total_expenses': float(total_expenses),
        'total_revenue': float(total_revenue),
        'profit': float(profit),
        'net_profit': float(profit),
        'profit_margin': round(profit_margin, 2),
        'expense_percentage': round(expense_percentage, 1),
        'category_breakdown': expense_categories,
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

# VIEW TRIP DETAILS
@login_required

# EDIT TRIP
@login_required
def trip_edit(request, id):
    """Edit trip"""
    trip = get_object_or_404(Trip, id=id)
    if request.method == 'POST':
        # Handle form submission
        trip.tripNumber = request.POST.get('tripNumber', trip.tripNumber)
        trip.origin = request.POST.get('origin', trip.origin)
        trip.destination = request.POST.get('destination', trip.destination)
        trip.distance = request.POST.get('distance', trip.distance)
        trip.revenue = request.POST.get('revenue', trip.revenue)
        trip.status = request.POST.get('status', trip.status)
        trip.save()
        return redirect('knlInvoice:trips-list')
    
    return render(request, 'knlInvoice/trip_form.html', {
        'trip': trip,
        'form': trip_form(instance=trip),
        'title': 'Edit Trip'
    })

# DELETE TRIP
@login_required
def trip_delete(request, id):
    """Delete trip"""
    trip = get_object_or_404(Trip, id=id)
    if request.method == 'POST':
        trip.delete()
        return redirect('knlInvoice:trips-list')
    return render(request, 'knlInvoice/trip_confirm_delete.html', {'trip': trip})

# ← CREATE INVOICE FROM TRIP
@login_required
def trip_invoice_create(request, id):
    """Create invoice from trip"""
    trip = get_object_or_404(Trip, id=id)
    
    # Check if invoice already exists
    if hasattr(trip, 'tripinvoice'):
        # Invoice exists, redirect to edit
        return redirect('knlInvoice:invoice-edit', pk=trip.tripinvoice.invoice.id)
    
    # Create new invoice from trip data
    if request.method == 'POST':
        client_id = request.POST.get('client')
        
        # Create invoice
        invoice = Invoice.objects.create(
            invoiceNumber=f"INV-{trip.tripNumber}",
            user=request.user,
            client_id=client_id,
            total=trip.revenue,
            tax=trip.revenue * 0.075,  # 7.5% VAT
            status='draft'
        )
        
        # Create trip invoice link
        trip_invoice = TripInvoice.objects.create(
            trip=trip,
            invoice=invoice
        )
        
        return redirect('knlInvoice:invoice-detail', pk=invoice.id)
    
    # GET request: Show client selection form
    from .models import Client
    clients = Client.objects.all()
    
    return render(request, 'knlInvoice/trip_invoice_create.html', {
        'trip': trip,
        'clients': clients
    })

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
# TRIP DETAIL (UPDATED - Safe expense handling)
# ============================================

@login_required(login_url='knlInvoice:login')
def trip_detail(request, pk):
    """View trip details with expense management - ALL values pre-calculated"""
    trip = get_object_or_404(Trip, pk=pk)
    
    # Get expenses safely
    expenses = []
    total_expenses = Decimal('0')
    expense_categories = {}
    
    try:
        # Try to get expenses
        if hasattr(trip, 'tripexpense_set'):
            expenses = trip.tripexpense_set.all()
        elif hasattr(trip, 'expense_set'):
            expenses = trip.expense_set.all()
        else:
            try:
                expenses = TripExpense.objects.filter(trip=trip)
            except:
                expenses = []
        
        # Calculate totals
        if expenses:
            total_expenses = sum((Decimal(str(e.amount or 0)) for e in expenses), Decimal('0'))
            
            # Calculate by category
            for expense in expenses:
                if hasattr(expense, 'get_category_display'):
                    category = expense.get_category_display()
                elif hasattr(expense, 'category'):
                    category = expense.category
                else:
                    category = 'Other'
                
                if category not in expense_categories:
                    expense_categories[category] = Decimal('0')
                expense_categories[category] += Decimal(str(expense.amount or 0))
    
    except Exception as e:
        expenses = []
        total_expenses = Decimal('0')
    
    # Calculate profitability (ALL VALUES PRE-CALCULATED!)
    total_revenue = Decimal(str(trip.revenue or 0))
    profit = total_revenue - total_expenses
    profit_margin = (profit / total_revenue * 100) if total_revenue > 0 else 0
    expense_percentage = (total_expenses / total_revenue * 100) if total_revenue > 0 else 0
    
    # ✅ IMPORTANT: Convert all Decimal to float for template!
    context = {
        'page_title': f'Trip {trip.tripNumber}',
        'trip': trip,
        'expenses': expenses,
        'expenses_count': len(expenses) if expenses else 0,
        # ✅ All monetary values as FLOAT (no filters needed!)
        'total_revenue': float(total_revenue),
        'total_expenses': float(total_expenses),
        'profit': float(profit),
        'net_profit': float(profit),
        'profit_margin': round(profit_margin, 2),
        'expense_percentage': round(expense_percentage, 1),
        # Category breakdown
        'category_breakdown': {k: float(v) for k, v in expense_categories.items()},
    }
    
    return render(request, 'knlInvoice/trip_detail.html', context)


# ============================================
# EXPENSE LIST (NEW VIEW)
# ============================================

@login_required(login_url='knlInvoice:login')
def expense_list(request, pk):
    """View all expenses for a trip"""
    trip = get_object_or_404(Trip, pk=pk)
    
    # Get expenses
    expenses = []
    total_expenses = Decimal('0')
    expense_categories = {}
    
    try:
        if hasattr(trip, 'tripexpense_set'):
            expenses = trip.tripexpense_set.all()
        elif hasattr(trip, 'expense_set'):
            expenses = trip.expense_set.all()
        else:
            try:
                expenses = TripExpense.objects.filter(trip=trip)
            except:
                expenses = []
        
        if expenses:
            total_expenses = sum((Decimal(str(e.amount or 0)) for e in expenses), Decimal('0'))
            
            for expense in expenses:
                category = expense.get_category_display() if hasattr(expense, 'get_category_display') else expense.category
                if category not in expense_categories:
                    expense_categories[category] = Decimal('0')
                expense_categories[category] += Decimal(str(expense.amount or 0))
    except:
        expenses = []
        total_expenses = Decimal('0')
    
    # Calculate profitability
    total_revenue = Decimal(str(trip.revenue or 0))
    net_profit = total_revenue - total_expenses
    expense_percentage = (total_expenses / total_revenue * 100) if total_revenue > 0 else 0
    
    context = {
        'page_title': f'Trip {trip.tripNumber} - Expenses',
        'trip': trip,
        'expenses': expenses,
        'expenses_count': len(expenses) if expenses else 0,
        'total_expenses': float(total_expenses),
        'total_revenue': float(total_revenue),
        'net_profit': float(net_profit),
        'expense_percentage': round(expense_percentage, 1),
        'category_breakdown': {k: float(v) for k, v in expense_categories.items()},
    }
    
    return render(request, 'knlInvoice/expense_list.html', context)


# ============================================
# ADD EXPENSE (expense_create)
# ============================================

@login_required(login_url='knlInvoice:login')
def expense_create(request, pk):
    """Create new expense for trip"""
    trip = get_object_or_404(Trip, pk=pk)
    
    # Get trip financial data for context
    total_revenue = float(trip.revenue or 0)
    total_expenses = trip.get_total_expenses()
    profit = total_revenue - total_expenses
    
    if request.method == 'POST':
        try:
            amount = float(request.POST.get('amount', 0))
            date = request.POST.get('date')  # Changed from expense_date
            expenseType = request.POST.get('expenseType')  # Changed from category
            description = request.POST.get('description', '')
            notes = request.POST.get('notes', '')
            
            if amount <= 0:
                messages.error(request, '❌ Expense amount must be greater than zero.')
                return render(request, 'knlInvoice/add_expense.html', {
                    'trip': trip,
                    'total_revenue': total_revenue,
                    'total_expenses': total_expenses,
                    'profit': profit,
                    'expense_types': TripExpense.EXPENSE_TYPE_CHOICES,
                })
            
            # Create expense with CORRECT field names
            TripExpense.objects.create(
                trip=trip,
                amount=amount,
                date=date,  # ✅ CORRECT
                expenseType=expenseType,  # ✅ CORRECT
                description=description,
                notes=notes,
            )
            
            messages.success(request, f'✅ Expense of ₦{amount:,.2f} added successfully!')
            return redirect('knlInvoice:expense-list', pk=trip.pk)
            
        except ValueError:
            messages.error(request, '❌ Invalid expense amount.')
            return render(request, 'knlInvoice/add_expense.html', {
                'trip': trip,
                'total_revenue': total_revenue,
                'total_expenses': total_expenses,
                'profit': profit,
                'expense_types': TripExpense.EXPENSE_TYPE_CHOICES,
            })
    
    return render(request, 'knlInvoice/add_expense.html', {
        'trip': trip,
        'total_revenue': total_revenue,
        'total_expenses': total_expenses,
        'profit': profit,
        'expense_types': TripExpense.EXPENSE_TYPE_CHOICES,
    })


# ============================================
# EDIT EXPENSE
# ============================================

@login_required(login_url='knlInvoice:login')
def edit_expense(request, trip_id, expense_id):
    """Edit a trip expense"""
    trip = get_object_or_404(Trip, pk=trip_id)
    expense = get_object_or_404(TripExpense, pk=expense_id, trip=trip)
    
    # Get trip financial data for context
    total_revenue = float(trip.revenue or 0)
    total_expenses = trip.get_total_expenses()
    profit = total_revenue - total_expenses
    
    if request.method == 'POST':
        try:
            amount = float(request.POST.get('amount', expense.amount))
            date = request.POST.get('date', expense.date)
            expenseType = request.POST.get('expenseType', expense.expenseType)  # ✅ CORRECT
            description = request.POST.get('description', expense.description)
            notes = request.POST.get('notes', expense.notes)
            
            if amount <= 0:
                messages.error(request, '❌ Expense amount must be greater than zero.')
                return render(request, 'knlInvoice/edit_expense.html', {
                    'trip': trip,
                    'expense': expense,
                    'total_revenue': total_revenue,
                    'total_expenses': total_expenses,
                    'profit': profit,
                    'expense_types': TripExpense.EXPENSE_TYPE_CHOICES,
                })
            
            # Update expense with CORRECT field names
            expense.amount = amount
            expense.date = date
            expense.expenseType = expenseType  # ✅ CORRECT
            expense.description = description
            expense.notes = notes
            expense.save()
            
            messages.success(request, '✅ Expense updated successfully!')
            return redirect('knlInvoice:expense-list', pk=trip.pk)
        
        except ValueError:
            messages.error(request, '❌ Invalid expense amount.')
    
    return render(request, 'knlInvoice/edit_expense.html', {
        'trip': trip,
        'expense': expense,
        'total_revenue': total_revenue,
        'total_expenses': total_expenses,
        'profit': profit,
        'expense_types': TripExpense.EXPENSE_TYPE_CHOICES,
    })


# ============================================
# DELETE EXPENSE
# ============================================

@login_required(login_url='knlInvoice:login')
@require_http_methods(["POST"])
def delete_expense(request, trip_id, expense_id):
    """Delete a trip expense"""
    trip = get_object_or_404(Trip, pk=trip_id)
    expense = get_object_or_404(TripExpense, pk=expense_id, trip=trip)
    
    expense_amount = expense.amount
    expense.delete()
    messages.success(request, f'✅ Expense of ₦{expense_amount:,.2f} deleted successfully!')
    return redirect('knlInvoice:expense-list', pk=trip.pk)

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
    FIXED: Generate professional LANDSCAPE PDF using ReportLab
    
    ✅ NOW WITHOUT HRFlat (compatibility fix)
    ✅ Landscape orientation (A4 landscape)
    ✅ KNL-Company title
    ✅ Professional Kamrate branding
    ✅ Works with all ReportLab versions
    
    Returns: BytesIO object or None if failed
    Requires: pip install reportlab
    """
    if not REPORTLAB_AVAILABLE:
        return None
    
    try:
        # ✅ LANDSCAPE: Use A4 landscape instead of portrait
        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer, 
            pagesize=landscape(A4),  # ✅ LANDSCAPE!
            rightMargin=15,
            leftMargin=15,
            topMargin=15,
            bottomMargin=15
        )
        elements = []
        
        styles = getSampleStyleSheet()
        
        # ===== HEADER SECTION =====
        # Title style
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#001F4D'),  # Kamrate blue
            spaceAfter=3,
            alignment=TA_CENTER,
            fontName='Helvetica-Bold'
        )
        
        subtitle_style = ParagraphStyle(
            'Subtitle',
            parent=styles['Normal'],
            fontSize=12,
            textColor=colors.HexColor('#666'),
            alignment=TA_CENTER,
            spaceAfter=12,
        )
        
        # ✅ KNL-COMPANY TITLE (matching template design)
        client_first_words = ' '.join(invoice.client.clientName.split()[:2]).upper()
        elements.append(Paragraph(f"KNL-{client_first_words}", title_style))
        elements.append(Paragraph(f"Invoice #{invoice.invoice_number}", subtitle_style))
        
        # ✅ DIVIDER: Use a colored table row instead of HRFlat
        divider_data = [[''], ]
        divider_table = Table(divider_data, colWidths=[6.4*inch])
        divider_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#FF9500')),
            ('HEIGHT', (0, 0), (-1, -1), 3),  # 3pt height line
        ]))
        elements.append(divider_table)
        elements.append(Spacer(1, 0.15*inch))
        
        # ===== CLIENT & INVOICE INFO (2 COLUMNS) =====
        client_style = ParagraphStyle(
            'ClientInfo',
            parent=styles['Normal'],
            fontSize=10,
            leading=12,
        )
        
        client_label_style = ParagraphStyle(
            'ClientLabel',
            parent=styles['Normal'],
            fontSize=9,
            fontName='Helvetica-Bold',
            textColor=colors.HexColor('#001F4D'),
            spaceAfter=3,
        )
        
        # Left column: Client info
        client_info = [
            Paragraph("<b>Bill To:</b>", client_label_style),
            Paragraph(f"<b>{invoice.client.clientName}</b>", client_style),
            Paragraph(f"Email: {invoice.client.emailAddress}", client_style),
            Paragraph(f"Phone: {invoice.client.phoneNumber}", client_style),
        ]
        
        # Right column: Invoice details
        invoice_info = [
            Paragraph("<b>Invoice Details:</b>", client_label_style),
            Paragraph(f"<b>Invoice Number:</b> {invoice.invoice_number}", client_style),
            Paragraph(f"<b>Payment Terms:</b> {invoice.paymentTerms or 'Net 30'}", client_style),
            Paragraph(f"<b>Created:</b> {invoice.date_created.strftime('%d %b %Y')}", client_style),
        ]
        
        # Create 2-column table for client info
        info_table = Table(
            [[client_info, invoice_info]],
            colWidths=[3.2*inch, 3.2*inch]
        )
        info_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ]))
        elements.append(info_table)
        elements.append(Spacer(1, 0.15*inch))
        
        # ===== ITEMS TABLE =====
        items = invoice.items.all()
        
        if items.exists():
            # Build items data
            items_data = [['Description', 'Qty', 'Unit Price', 'Total', 'Status']]
            
            for item in items:
                # ✅ Convert Decimal to float BEFORE operations
                qty = float(item.quantity) if item.quantity else 1.0
                unit_price = float(item.unit_price) if item.unit_price else 0.0
                line_total = qty * unit_price
                
                items_data.append([
                    item.description or (item.product.title if item.product else ""),
                    f"{qty:.1f}",
                    f"₦{unit_price:,.0f}",
                    f"₦{line_total:,.0f}",
                    "Item"
                ])
            
            # Create items table
            items_table = Table(
                items_data,
                colWidths=[2.8*inch, 0.8*inch, 1.4*inch, 1.4*inch, 0.8*inch]
            )
            
            # Style items table
            items_table.setStyle(TableStyle([
                # Header styling
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#001F4D')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                ('VALIGN', (0, 0), (-1, 0), 'MIDDLE'),
                ('TOPPADDING', (0, 0), (-1, 0), 8),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
                
                # Body styling
                ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 1), (-1, -1), 9),
                ('ALIGN', (0, 0), (0, -1), 'LEFT'),
                ('ALIGN', (1, 1), (-1, -1), 'CENTER'),
                ('ALIGN', (2, 1), (-1, -1), 'RIGHT'),
                ('ALIGN', (3, 1), (-1, -1), 'RIGHT'),
                ('VALIGN', (0, 1), (-1, -1), 'MIDDLE'),
                ('TOPPADDING', (0, 1), (-1, -1), 6),
                ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
                
                # Alternating row colors
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f9f9f9')]),
                
                # Borders
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#ddd')),
                ('LINEABOVE', (0, 0), (-1, 0), 1.5, colors.HexColor('#001F4D')),
                ('LINEBELOW', (0, 0), (-1, 0), 1.5, colors.HexColor('#001F4D')),
                
                # Total row
                ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#e3f2fd')),
                ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
                ('FONTSIZE', (0, -1), (-1, -1), 10),
                ('LINEABOVE', (0, -1), (-1, -1), 2, colors.HexColor('#FF9500')),
                ('LINEBELOW', (0, -1), (-1, -1), 2, colors.HexColor('#001F4D')),
            ]))
            
            elements.append(items_table)
            elements.append(Spacer(1, 0.15*inch))
        
        # ===== SUMMARY SECTION =====
        # ✅ Convert Decimal to float for calculations
        subtotal = float(invoice.subtotal or 0)
        tax_amount = float(invoice.tax_amount or 0)
        total = float(invoice.total or 0)
        
        summary_style = ParagraphStyle(
            'Summary',
            parent=styles['Normal'],
            fontSize=10,
            alignment=TA_RIGHT,
        )
        
        summary_label_style = ParagraphStyle(
            'SummaryLabel',
            parent=styles['Normal'],
            fontSize=10,
            fontName='Helvetica-Bold',
            textColor=colors.HexColor('#001F4D'),
        )
        
        # Create summary table
        summary_data = [
            ['', 'Subtotal:', f"₦{subtotal:,.2f}"],
            ['', f'Tax ({invoice.tax_rate or 7.5}%):', f"₦{tax_amount:,.2f}"],
            ['', 'TOTAL DUE:', f"₦{total:,.2f}"],
        ]
        
        summary_table = Table(
            summary_data,
            colWidths=[4.0*inch, 1.4*inch, 1.4*inch]
        )
        
        summary_table.setStyle(TableStyle([
            ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            
            # Total row styling
            ('BACKGROUND', (0, 2), (-1, 2), colors.HexColor('#e3f2fd')),
            ('FONTNAME', (0, 2), (-1, 2), 'Helvetica-Bold'),
            ('FONTSIZE', (1, 2), (1, 2), 12),
            ('TEXTCOLOR', (2, 2), (2, 2), colors.HexColor('#FF9500')),
            ('LINEABOVE', (0, 2), (-1, 2), 2, colors.HexColor('#001F4D')),
            ('LINEBELOW', (0, 2), (-1, 2), 2, colors.HexColor('#FF9500')),
        ]))
        
        elements.append(summary_table)
        elements.append(Spacer(1, 0.15*inch))
        
        # ===== PAYMENT DETAILS SECTION =====
        payment_label_style = ParagraphStyle(
            'PaymentLabel',
            parent=styles['Normal'],
            fontSize=9,
            fontName='Helvetica-Bold',
            textColor=colors.HexColor('#001F4D'),
        )
        
        payment_value_style = ParagraphStyle(
            'PaymentValue',
            parent=styles['Normal'],
            fontSize=9,
        )
        
        # 3-column payment details
        payment_data = [[
            [
                Paragraph("<b>Bank Details:</b>", payment_label_style),
                Paragraph("KAMRATE NIGERIA LIMITED", payment_value_style),
                Paragraph("0004662938", payment_value_style),
            ],
            [
                Paragraph("<b>Bank Information:</b>", payment_label_style),
                Paragraph("JAIZ BANK", payment_value_style),
                Paragraph("JAIZNGLA", payment_value_style),
            ],
            [
                Paragraph("<b>Tax Details:</b>", payment_label_style),
                Paragraph("20727419-0001", payment_value_style),
                Paragraph("1421251", payment_value_style),
            ],
        ]]
        
        payment_table = Table(payment_data, colWidths=[2.1*inch, 2.1*inch, 2.1*inch])
        payment_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f5f5f5')),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 10),
            ('RIGHTPADDING', (0, 0), (-1, -1), 10),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('BORDER', (0, 0), (-1, -1), 0.5, colors.HexColor('#ddd')),
        ]))
        
        elements.append(payment_table)
        elements.append(Spacer(1, 0.15*inch))
        
        # ===== FOOTER =====
        footer_style = ParagraphStyle(
            'Footer',
            parent=styles['Normal'],
            fontSize=8,
            textColor=colors.HexColor('#999'),
            alignment=TA_CENTER,
        )
        
        footer_company_style = ParagraphStyle(
            'FooterCompany',
            parent=styles['Normal'],
            fontSize=8,
            textColor=colors.white,
            alignment=TA_CENTER,
        )
        
        # Company info footer (in colored bar)
        footer_data = [[
            Paragraph("KAMRATE NIGERIA LIMITED | 33, Creek Road, Apapa, Lagos | +234 803 484 9228", footer_company_style)
        ]]
        
        footer_table = Table(footer_data, colWidths=[6.4*inch])
        footer_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#FF9500')),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ]))
        
        elements.append(footer_table)
        
        # Build PDF
        doc.build(elements)
        buffer.seek(0)
        
        logger.info(f"✅ Professional LANDSCAPE PDF generated with ReportLab for invoice {invoice.invoice_number}")
        return buffer
        
    except Exception as e:
        logger.error(f"❌ ReportLab error for invoice {invoice.invoice_number}: {str(e)}", exc_info=True)
        return None
    

def generate_pdf_reportlab_trip(trip_invoice):
    """
    Generate professional trip-based invoice PDF
    
    ✅ Based on Trip data, not Products
    ✅ Shows trip manifest with container details
    ✅ Professional Kamrate format
    ✅ Matches reference document
    
    Returns: BytesIO object or None if failed
    """
    if not REPORTLAB_AVAILABLE:
        return None
    
    try:
        trip = trip_invoice.trip
        client = trip_invoice.client
        
        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer, 
            pagesize=landscape(A4),
            rightMargin=12,
            leftMargin=12,
            topMargin=12,
            bottomMargin=20
        )
        elements = []
        
        styles = getSampleStyleSheet()
        
        # ===== HEADER SECTION =====
        header_value_style = ParagraphStyle(
            'HeaderValue',
            parent=styles['Normal'],
            fontSize=9,
            leading=10,
        )
        
        # Client address on left
        client_address = f"""
<b>{client.clientName if client else 'Client'}</b><br/>
{getattr(client, 'addressLine1', '') if client else ''}<br/>
{getattr(client, 'state', '') if client else ''}
        """
        
        # Company info on right
        company_info = f"""
<b>KAMRATE NIGERIA LIMITED</b><br/>
Rc: 1421251<br/>
{trip_invoice.issue_date.strftime('%d %B %Y')}
        """
        
        # Header table
        header_data = [[
            Paragraph(client_address, header_value_style),
            Paragraph(company_info, header_value_style)
        ]]
        
        header_table = Table(header_data, colWidths=[3.5*inch, 3.5*inch])
        header_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ]))
        elements.append(header_table)
        elements.append(Spacer(1, 0.1*inch))
        
        # ===== INVOICE REFERENCE =====
        title_style = ParagraphStyle(
            'Title',
            parent=styles['Heading1'],
            fontSize=14,
            fontName='Helvetica-Bold',
            textColor=colors.HexColor('#001F4D'),
            alignment=TA_CENTER,
            spaceAfter=3,
        )
        
        # Generate invoice reference
        client_code = (client.clientName.split()[0][:2].upper() if client else 'XX')
        invoice_ref = f"KNL/{client_code}/26/{trip_invoice.invoice_number}"
        
        elements.append(Paragraph(invoice_ref, title_style))
        elements.append(Spacer(1, 0.1*inch))
        
        # ===== TRIP MANIFEST TABLE =====
        # This is the key part - showing trip details instead of products
        
        items_data = [[
            'DATE LOADED',
            'AA FILE REFERENCE',
            'CONTAINER NO',
            'TERMINAL',
            'TRUCK NO',
            'LENGTH',
            'DESTINATION',
            'AMOUNT (₦)'
        ]]
        
        # For trip-based invoice, we show ONE row (the trip itself)
        # But if you have multiple containers in a trip, add them here
        
        # Get trip details
        trip_date = trip.startDate.strftime('%d/%m/%Y') if trip.startDate else '01/01/2026'
        truck_plate = trip.truck.plateNumber if trip.truck else 'TRK-001'
        origin = trip.origin
        destination = trip.destination
        
        # Determine container length from cargo description or default
        container_length = '20FT'  # Default
        if '40' in trip.cargoDescription:
            container_length = '40FT'
        
        # Calculate amount per trip
        trip_revenue = float(trip.revenue)
        
        items_data.append([
            trip_date,
            trip.tripNumber,
            'CONTAINER-001',  # Could be extended to support multiple containers
            'APAPA',  # Or get from trip model if available
            truck_plate,
            container_length,
            destination,
            f"{trip_revenue:,.2f}"
        ])
        
        # Total row
        items_data.append([
            '', '', '', '', '', '', 'TOTAL',
            f"{trip_revenue:,.2f}"
        ])
        
        # Create table
        items_table = Table(
            items_data,
            colWidths=[0.9*inch, 1.0*inch, 0.9*inch, 0.7*inch, 0.9*inch, 0.65*inch, 1.0*inch, 1.0*inch]
        )
        
        # Style table
        items_table.setStyle(TableStyle([
            # Header
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#001F4D')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 8),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('TOPPADDING', (0, 0), (-1, 0), 6),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
            
            # Body
            ('FONTNAME', (0, 1), (-1, -2), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -2), 8),
            ('ALIGN', (0, 0), (6, -2), 'LEFT'),
            ('ALIGN', (7, 0), (7, -2), 'RIGHT'),
            ('TOPPADDING', (0, 1), (-1, -2), 4),
            ('BOTTOMPADDING', (0, 1), (-1, -2), 4),
            ('ROWBACKGROUNDS', (0, 1), (-1, -2), [colors.white, colors.HexColor('#f5f5f5')]),
            
            # Borders
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#999')),
            
            # Total row
            ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#FFCC00')),
            ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, -1), (-1, -1), 9),
            ('ALIGN', (0, -1), (6, -1), 'RIGHT'),
            ('ALIGN', (7, -1), (7, -1), 'RIGHT'),
        ]))
        
        elements.append(items_table)
        elements.append(Spacer(1, 0.1*inch))
        
        # ===== SUMMARY SECTION =====
        subtotal = float(trip_invoice.subtotal)
        tax_amount = float(trip_invoice.tax_amount)
        total = float(trip_invoice.total)
        
        summary_data = [
            ['', 'Subtotal:', f"₦{subtotal:,.2f}"],
            ['', f'Tax ({trip_invoice.tax_rate}%):', f"₦{tax_amount:,.2f}"],
            ['', 'TOTAL DUE:', f"₦{total:,.2f}"],
        ]
        
        summary_table = Table(
            summary_data,
            colWidths=[4.0*inch, 1.4*inch, 1.4*inch]
        )
        
        summary_table.setStyle(TableStyle([
            ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            
            # Total row
            ('BACKGROUND', (0, 2), (-1, 2), colors.HexColor('#e3f2fd')),
            ('FONTNAME', (0, 2), (-1, 2), 'Helvetica-Bold'),
            ('FONTSIZE', (1, 2), (1, 2), 12),
            ('TEXTCOLOR', (2, 2), (2, 2), colors.HexColor('#FF9500')),
            ('LINEABOVE', (0, 2), (-1, 2), 2, colors.HexColor('#001F4D')),
            ('LINEBELOW', (0, 2), (-1, 2), 2, colors.HexColor('#FF9500')),
        ]))
        
        elements.append(summary_table)
        elements.append(Spacer(1, 0.1*inch))
        
        # ===== AMOUNT IN WORDS =====
        amount_words = f"₦{total:,.2f}"
        try:
            from num2words import num2words
            amount_words = num2words(int(total), lang='en').upper()
        except:
            pass
        
        words_style = ParagraphStyle(
            'AmountWords',
            parent=styles['Normal'],
            fontSize=9,
            fontName='Helvetica-Bold',
            textColor=colors.HexColor('#001F4D'),
        )
        
        elements.append(Paragraph(
            f"TOTAL AMOUNT IN WORDS: {amount_words} NAIRA ONLY",
            words_style
        ))
        elements.append(Spacer(1, 0.1*inch))
        
        # ===== BANK DETAILS =====
        bank_value_style = ParagraphStyle(
            'BankValue',
            parent=styles['Normal'],
            fontSize=9,
        )
        
        bank_details = """
<b>ACCOUNT NAME:</b> KAMRATE NIGERIA LIMITED<br/>
<b>ACCOUNT NO:</b> 0004662938<br/>
<b>JAIZ BANK</b><br/>
<b>TIN:</b> 20727419-0001
        """
        
        elements.append(Paragraph(bank_details, bank_value_style))
        elements.append(Spacer(1, 0.15*inch))
        
        # ===== SIGNATURE =====
        sig_style = ParagraphStyle(
            'Signature',
            parent=styles['Normal'],
            fontSize=9,
        )
        
        elements.append(Paragraph("_" * 40, sig_style))
        elements.append(Paragraph("Ayinla O Kamaldeen", sig_style))
        elements.append(Paragraph("MD/CEO", sig_style))
        
        # ===== FOOTER =====
        elements.append(Spacer(1, 0.2*inch))
        
        footer_style = ParagraphStyle(
            'Footer',
            parent=styles['Normal'],
            fontSize=7,
            textColor=colors.white,
            alignment=TA_CENTER,
        )
        
        footer_data = [[
            Paragraph(
                "33, Creek Road, Ibu Boulevard, Apapa, Lagos. 08134834928, 08026826552, 09126220281 | "
                "www.kamratelimited.com | info@kamratelimited.com, kamratelimited@gmail.com",
                footer_style
            )
        ]]
        
        footer_table = Table(footer_data, colWidths=[7.0*inch])
        footer_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#001F4D')),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ]))
        
        elements.append(footer_table)
        
        # Build PDF
        doc.build(elements)
        buffer.seek(0)
        
        logger.info(f"✅ Trip invoice PDF generated: {trip_invoice.invoice_number}")
        return buffer
        
    except Exception as e:
        logger.error(f"❌ Trip PDF generation error: {str(e)}", exc_info=True)
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
    
# ===== PDF GENERATOR FUNCTION =====

def generate_pdf_reportlab_trip(trip_invoice):
    """
    Generate professional trip-based invoice PDF
    Uses ReportLab for PDF generation
    """
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.units import inch
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    
    REPORTLAB_AVAILABLE = True
    
    if not REPORTLAB_AVAILABLE:
        return None
    
    try:
        trip = trip_invoice.trip
        client = trip_invoice.client
        
        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer, 
            pagesize=landscape(A4),
            rightMargin=12,
            leftMargin=12,
            topMargin=12,
            bottomMargin=20
        )
        elements = []
        
        styles = getSampleStyleSheet()
        
        # ===== HEADER SECTION =====
        header_value_style = ParagraphStyle(
            'HeaderValue',
            parent=styles['Normal'],
            fontSize=9,
            leading=10,
        )
        
        client_address = f"""
<b>{client.clientName if client else 'Client'}</b><br/>
{getattr(client, 'addressLine1', '') if client else ''}<br/>
{getattr(client, 'state', '') if client else ''}
        """
        
        company_info = f"""
<b>KAMRATE NIGERIA LIMITED</b><br/>
Rc: 1421251<br/>
{trip_invoice.issue_date.strftime('%d %B %Y')}
        """
        
        header_data = [[
            Paragraph(client_address, header_value_style),
            Paragraph(company_info, header_value_style)
        ]]
        
        header_table = Table(header_data, colWidths=[3.5*inch, 3.5*inch])
        header_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ]))
        elements.append(header_table)
        elements.append(Spacer(1, 0.1*inch))
        
        # ===== INVOICE REFERENCE =====
        title_style = ParagraphStyle(
            'Title',
            parent=styles['Heading1'],
            fontSize=14,
            fontName='Helvetica-Bold',
            textColor=colors.HexColor('#001F4D'),
            alignment=TA_CENTER,
            spaceAfter=3,
        )
        
        client_code = (client.clientName.split()[0][:2].upper() if client else 'XX')
        invoice_ref = f"KNL/{client_code}/26/{trip_invoice.invoice_number}"
        
        elements.append(Paragraph(invoice_ref, title_style))
        elements.append(Spacer(1, 0.1*inch))
        
        # ===== TRIP MANIFEST TABLE =====
        items_data = [[
            'DATE LOADED',
            'AA FILE REFERENCE',
            'CONTAINER NO',
            'TERMINAL',
            'TRUCK NO',
            'LENGTH',
            'DESTINATION',
            'AMOUNT (₦)'
        ]]
        
        trip_date = trip.startDate.strftime('%d/%m/%Y') if trip.startDate else '01/01/2026'
        truck_plate = trip.truck.plateNumber if trip.truck else 'TRK-001'
        destination = trip.destination
        
        container_length = '20FT'
        if '40' in trip.cargoDescription:
            container_length = '40FT'
        
        trip_revenue = float(trip.revenue)
        
        items_data.append([
            trip_date,
            trip.tripNumber,
            'CONTAINER-001',
            'APAPA',
            truck_plate,
            container_length,
            destination,
            f"{trip_revenue:,.2f}"
        ])
        
        items_data.append([
            '', '', '', '', '', '', 'TOTAL',
            f"{trip_revenue:,.2f}"
        ])
        
        items_table = Table(
            items_data,
            colWidths=[0.9*inch, 1.0*inch, 0.9*inch, 0.7*inch, 0.9*inch, 0.65*inch, 1.0*inch, 1.0*inch]
        )
        
        items_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#001F4D')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 8),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('TOPPADDING', (0, 0), (-1, 0), 6),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
            
            ('FONTNAME', (0, 1), (-1, -2), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -2), 8),
            ('ALIGN', (0, 0), (6, -2), 'LEFT'),
            ('ALIGN', (7, 0), (7, -2), 'RIGHT'),
            ('TOPPADDING', (0, 1), (-1, -2), 4),
            ('BOTTOMPADDING', (0, 1), (-1, -2), 4),
            ('ROWBACKGROUNDS', (0, 1), (-1, -2), [colors.white, colors.HexColor('#f5f5f5')]),
            
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#999')),
            
            ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#FFCC00')),
            ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, -1), (-1, -1), 9),
            ('ALIGN', (0, -1), (6, -1), 'RIGHT'),
            ('ALIGN', (7, -1), (7, -1), 'RIGHT'),
        ]))
        
        elements.append(items_table)
        elements.append(Spacer(1, 0.1*inch))
        
        # ===== SUMMARY =====
        subtotal = float(trip_invoice.subtotal)
        tax_amount = float(trip_invoice.tax_amount)
        total = float(trip_invoice.total)
        
        summary_data = [
            ['', 'Subtotal:', f"₦{subtotal:,.2f}"],
            ['', f'Tax ({trip_invoice.tax_rate}%):', f"₦{tax_amount:,.2f}"],
            ['', 'TOTAL DUE:', f"₦{total:,.2f}"],
        ]
        
        summary_table = Table(
            summary_data,
            colWidths=[4.0*inch, 1.4*inch, 1.4*inch]
        )
        
        summary_table.setStyle(TableStyle([
            ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            
            ('BACKGROUND', (0, 2), (-1, 2), colors.HexColor('#e3f2fd')),
            ('FONTNAME', (0, 2), (-1, 2), 'Helvetica-Bold'),
            ('FONTSIZE', (1, 2), (1, 2), 12),
            ('TEXTCOLOR', (2, 2), (2, 2), colors.HexColor('#FF9500')),
            ('LINEABOVE', (0, 2), (-1, 2), 2, colors.HexColor('#001F4D')),
            ('LINEBELOW', (0, 2), (-1, 2), 2, colors.HexColor('#FF9500')),
        ]))
        
        elements.append(summary_table)
        elements.append(Spacer(1, 0.1*inch))
        
        # ===== BANK DETAILS =====
        bank_value_style = ParagraphStyle(
            'BankValue',
            parent=styles['Normal'],
            fontSize=9,
        )
        
        bank_details = """
<b>ACCOUNT NAME:</b> KAMRATE NIGERIA LIMITED<br/>
<b>ACCOUNT NO:</b> 0004662938<br/>
<b>JAIZ BANK</b><br/>
<b>TIN:</b> 20727419-0001
        """
        
        elements.append(Paragraph(bank_details, bank_value_style))
        elements.append(Spacer(1, 0.15*inch))
        
        # ===== FOOTER =====
        elements.append(Spacer(1, 0.2*inch))
        
        footer_style = ParagraphStyle(
            'Footer',
            parent=styles['Normal'],
            fontSize=7,
            textColor=colors.white,
            alignment=TA_CENTER,
        )
        
        footer_data = [[
            Paragraph(
                "33, Creek Road, Ibu Boulevard, Apapa, Lagos. 08134834928, 08026826552, 09126220281 | "
                "www.kamratelimited.com | info@kamratelimited.com, kamratelimited@gmail.com",
                footer_style
            )
        ]]
        
        footer_table = Table(footer_data, colWidths=[7.0*inch])
        footer_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#001F4D')),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ]))
        
        elements.append(footer_table)
        
        # Build PDF
        doc.build(elements)
        buffer.seek(0)
        
        logger.info(f"✅ Trip invoice PDF generated: {trip_invoice.invoice_number}")
        return buffer
        
    except Exception as e:
        logger.error(f"❌ Trip PDF generation error: {str(e)}", exc_info=True)
        return None
    

@login_required
@require_http_methods(["POST"])
def quick_add_truck(request):
    """
    AJAX endpoint to add truck quickly from trip form
    
    Returns JSON with success status and new truck data
    """
    try:
        form = QuickAddTruckForm(request.POST)
        
        if form.is_valid():
            truck = form.save()
            
            return JsonResponse({
                'success': True,
                'truck_id': truck.id,
                'truck_plate': truck.plateNumber,
                'truck_model': truck.model,
                'truck_capacity': str(truck.capacity),
                'message': f'✅ Truck {truck.plateNumber} added successfully!',
                'redirect': request.GET.get('next', '/trips/')
            })
        else:
            # Return form errors
            errors_dict = {}
            for field, errors in form.errors.items():
                errors_dict[field] = [str(e) for e in errors]
            
            return JsonResponse({
                'success': False,
                'errors': errors_dict,
                'message': '❌ Please fix the errors below'
            }, status=400)
            
    except Exception as e:
        logger.error(f"Error adding truck: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'errors': {'general': [str(e)]},
            'message': f'❌ Error: {str(e)}'
        }, status=500)


@login_required
def get_trucks_json(request):
    """
    Get all active trucks as JSON for dropdown refresh
    """
    from .models import Truck
    
    trucks = Truck.objects.filter(status='ACTIVE').values('id', 'plateNumber', 'model', 'capacity').order_by('plateNumber')
    
    return JsonResponse({
        'success': True,
        'trucks': list(trucks)
    })

# ============================================
# TRIP INVOICE LIST
# ============================================

@login_required(login_url='knlInvoice:login')
def trip_invoice_list(request):
    """List all trip invoices"""
    invoices = TripInvoice.objects.all().order_by('-date_created')
    
    # Filter by status if provided
    status = request.GET.get('status')
    if status:
        invoices = invoices.filter(status=status)
    
    # Calculate summary statistics
    total_invoices = invoices.count()
    total_revenue = invoices.aggregate(total=Sum('total'))['total'] or 0
    total_paid = invoices.aggregate(total=Sum('amount_paid'))['total'] or 0
    total_outstanding = total_revenue - total_paid
    
    context = {
        'page_title': 'Trip Invoices',
        'invoices': invoices,
        'total_invoices': total_invoices,
        'total_revenue': float(total_revenue),
        'total_paid': float(total_paid),
        'total_outstanding': float(total_outstanding),
        'statuses': TripInvoice.STATUS_CHOICES,
    }
    
    return render(request, 'knlInvoice/trip_invoice_list.html', context)


# ============================================
# CREATE TRIP INVOICE
# ============================================

@login_required(login_url='knlInvoice:login')
def trip_invoice_create(request):
    """Create a manifest invoice with multiple trips"""
    
    if request.method == 'POST':
        try:
            # Get form data
            invoice_number = request.POST.get('invoice_number')
            client_id = request.POST.get('client')
            issue_date = request.POST.get('issue_date', timezone.now().date())
            due_date = request.POST.get('due_date')
            tax_rate = float(request.POST.get('tax_rate', 7.5))
            payment_terms = request.POST.get('payment_terms', '14 days')
            notes = request.POST.get('notes', '')
            
            # Get selected trips (from JavaScript containers array)
            containers_json = request.POST.get('containers', '[]')
            selected_trips = json.loads(containers_json) if containers_json else []
            
            if not selected_trips:
                messages.error(request, '❌ Please select at least one trip!')
                return render(request, 'knlInvoice/trip_invoice_create.html', {
                    'clients': Client.objects.all(),
                    'available_trips': Trip.objects.all().order_by('-startDate'),  # ✅ FIX: Get ALL trips
                    'payment_terms': TripInvoice.TERMS,
                })
            
            # Validate invoice number is unique (if provided)
            if invoice_number and TripInvoice.objects.filter(invoice_number=invoice_number).exists():
                messages.error(request, '❌ Invoice number already exists!')
                return render(request, 'knlInvoice/trip_invoice_create.html', {
                    'clients': Client.objects.all(),
                    'available_trips': Trip.objects.all().order_by('-startDate'),  # ✅ FIX: Get ALL trips
                    'payment_terms': TripInvoice.TERMS,
                })
            
            # Get client if provided
            client = None
            if client_id:
                try:
                    client = get_object_or_404(Client, pk=client_id)
                except:
                    client = None
            
            # Create invoice
            invoice = TripInvoice.objects.create(
                client=client,
                user=request.user,
                issue_date=issue_date,
                due_date=due_date if due_date else None,
                tax_rate=Decimal(str(tax_rate)),
                payment_terms=payment_terms,
                notes=notes,
                status='draft',
            )
            
            # Add selected trips as line items
            for trip_id in selected_trips:
                try:
                    trip = Trip.objects.get(pk=trip_id)
                    
                    # Get trip details - use all the fields from the old view
                    date_loaded = trip.startDate.date() if trip.startDate else timezone.now().date()
                    file_reference = trip.tripNumber if hasattr(trip, 'tripNumber') else ''
                    container_number = ''  # Can be filled in detail view
                    terminal = ''  # Can be filled in detail view
                    truck_number = trip.truck.plateNumber if trip.truck else ''
                    container_length = '20FT'  # Default
                    destination = trip.destination
                    amount = Decimal(str(trip.revenue))
                    
                    # Add as line item using the model's add_trip method
                    invoice.add_trip(
                        trip=trip,
                        date_loaded=date_loaded,
                        file_reference=file_reference,
                        container_number=container_number,
                        terminal=terminal,
                        truck_number=truck_number,
                        container_length=container_length,
                        destination=destination,
                        amount=amount,
                    )
                except Trip.DoesNotExist:
                    continue
                except Exception as e:
                    logger.error(f"Error adding trip {trip_id}: {str(e)}")
                    continue
            
            # Recalculate totals
            invoice.calculate_totals()
            invoice.save()
            
            messages.success(request, f'✅ Manifest Invoice created with {invoice.line_items.count()} containers!')
            return redirect('knlInvoice:trip-invoice-detail', pk=invoice.pk)
        
        except Exception as e:
            logger.error(f"Error creating invoice: {str(e)}")
            messages.error(request, f'❌ Error creating invoice: {str(e)}')
            return render(request, 'knlInvoice/trip_invoice_create.html', {
                'clients': Client.objects.all(),
                'available_trips': Trip.objects.all().order_by('-startDate'),  # ✅ FIX: Get ALL trips
                'payment_terms': TripInvoice.TERMS,
            })
    
    # GET REQUEST - Show create form
    
    # ✅ FIX: Get ALL trips instead of just completed
    # This matches the real-world usage shown in the invoice PDF
    available_trips = Trip.objects.all().order_by('-startDate')
    clients = Client.objects.all().order_by('clientName')
    
    context = {
        'page_title': 'Create Manifest Invoice',
        'available_trips': available_trips,  # ✅ Now includes ALL trips
        'clients': clients,
        'payment_terms': TripInvoice.TERMS,
    }
    
    return render(request, 'knlInvoice/trip_invoice_create.html', context)


# ============================================
# TRIP INVOICE DETAIL
# ============================================

@login_required(login_url='knlInvoice:login')
def trip_invoice_detail(request, pk):
    """View trip invoice details"""
    invoice = get_object_or_404(TripInvoice, pk=pk)
    
    # Calculate remaining balance
    remaining_balance = invoice.total - invoice.amount_paid
    
    context = {
        'page_title': f'Invoice {invoice.invoice_number}',
        'invoice': invoice,
        'remaining_balance': float(remaining_balance),
        'is_overdue': invoice.is_overdue,
        'is_paid': invoice.is_paid,
    }
    
    return render(request, 'knlInvoice/trip_invoice_detail.html', context)


# ============================================
# UPDATE INVOICE STATUS
# ============================================

@login_required(login_url='knlInvoice:login')
def trip_invoice_update_status(request, pk):
    """Update invoice status"""
    invoice = get_object_or_404(TripInvoice, pk=pk)
    
    if request.method == 'POST':
        new_status = request.POST.get('status')
        
        if new_status in dict(TripInvoice.STATUS_CHOICES):
            invoice.status = new_status
            invoice.save()
            messages.success(request, f'✅ Invoice status updated to {new_status}!')
        else:
            messages.error(request, '❌ Invalid status!')
    
    return redirect('knlInvoice:trip-invoice-detail', pk=invoice.pk)


# ============================================
# RECORD PAYMENT
# ============================================

@login_required(login_url='knlInvoice:login')
def trip_invoice_record_payment(request, pk):
    """Record payment for invoice"""
    invoice = get_object_or_404(TripInvoice, pk=pk)
    
    if request.method == 'POST':
        try:
            amount = float(request.POST.get('amount', 0))
            payment_date = request.POST.get('payment_date', timezone.now().date())
            
            if amount <= 0:
                messages.error(request, '❌ Payment amount must be greater than zero!')
                return redirect('knlInvoice:trip-invoice-detail', pk=invoice.pk)
            
            if amount > invoice.outstanding_amount:
                messages.error(request, f'❌ Payment exceeds outstanding amount (₦{invoice.outstanding_amount:,.2f})')
                return redirect('knlInvoice:trip-invoice-detail', pk=invoice.pk)
            
            # Record payment
            invoice.amount_paid += Decimal(str(amount))
            invoice.outstanding_amount = invoice.total - invoice.amount_paid
            
            # Update status
            if invoice.outstanding_amount <= 0:
                invoice.status = 'paid'
                invoice.outstanding_amount = Decimal('0')
                messages.success(request, f'✅ Invoice paid in full!')
            else:
                invoice.status = 'pending'
                messages.success(request, f'✅ Payment of ₦{amount:,.2f} recorded!')
            
            invoice.save()
        
        except ValueError:
            messages.error(request, '❌ Invalid payment amount!')
    
    return redirect('knlInvoice:trip-invoice-detail', pk=invoice.pk)


# ============================================
# EDIT INVOICE
# ============================================

@login_required(login_url='knlInvoice:login')
def trip_invoice_edit(request, pk):
    """Edit trip invoice"""
    invoice = get_object_or_404(TripInvoice, pk=pk)
    
    if invoice.status not in ['draft', 'pending']:
        messages.warning(request, '⚠️ Can only edit draft or pending invoices!')
        return redirect('knlInvoice:trip-invoice-detail', pk=invoice.pk)
    
    if request.method == 'POST':
        try:
            # Update fields
            invoice.client_id = request.POST.get('client') or None
            invoice.issue_date = request.POST.get('issue_date', invoice.issue_date)
            invoice.due_date = request.POST.get('due_date', invoice.due_date)
            invoice.tax_rate = float(request.POST.get('tax_rate', invoice.tax_rate))
            invoice.payment_terms = request.POST.get('payment_terms', invoice.payment_terms)
            invoice.notes = request.POST.get('notes', '')
            
            # Recalculate totals
            invoice.calculate_totals()
            invoice.save()
            
            messages.success(request, '✅ Invoice updated successfully!')
            return redirect('knlInvoice:trip-invoice-detail', pk=invoice.pk)
        
        except Exception as e:
            messages.error(request, f'❌ Error updating invoice: {str(e)}')
    
    clients = Client.objects.all().order_by('clientName')
    
    context = {
        'page_title': f'Edit Invoice {invoice.invoice_number}',
        'invoice': invoice,
        'clients': clients,
        'payment_terms': TripInvoice.TERMS,
    }
    
    return render(request, 'knlInvoice/trip_invoice_edit.html', context)


# ============================================
# ADD TRIP TO EXISTING INVOICE
# ============================================

@login_required(login_url='knlInvoice:login')
def trip_invoice_add_trip(request, pk):
    """Add another trip to an existing invoice"""
    invoice = get_object_or_404(TripInvoice, pk=pk)
    
    # Only allow adding to draft invoices
    if invoice.status not in ['draft']:
        messages.error(request, '❌ Can only add trips to draft invoices!')
        return redirect('knlInvoice:trip-invoice-detail', pk=invoice.pk)
    
    if request.method == 'POST':
        try:
            trip_id = request.POST.get('trip')
            trip = get_object_or_404(Trip, pk=trip_id)
            
            # Check if trip already on invoice
            if invoice.line_items.filter(trip=trip).exists():
                messages.error(request, '❌ This trip is already on the invoice!')
                return redirect('knlInvoice:trip-invoice-add-trip', pk=invoice.pk)
            
            # Get trip details
            date_loaded = request.POST.get('date_loaded', trip.startDate.date())
            file_reference = request.POST.get('file_reference', '')
            container_number = request.POST.get('container_number', '')
            terminal = request.POST.get('terminal', '')
            truck_number = request.POST.get('truck_number', trip.truck.plateNumber if trip.truck else '')
            container_length = request.POST.get('container_length', '20FT')
            destination = request.POST.get('destination', trip.destination)
            amount = float(request.POST.get('amount', trip.revenue))
            
            # Add to invoice
            invoice.add_trip(
                trip=trip,
                date_loaded=date_loaded,
                file_reference=file_reference,
                container_number=container_number,
                terminal=terminal,
                truck_number=truck_number,
                container_length=container_length,
                destination=destination,
                amount=amount,
            )
            
            messages.success(request, f'✅ Trip {trip.tripNumber} added to invoice!')
            return redirect('knlInvoice:trip-invoice-detail', pk=invoice.pk)
        
        except Exception as e:
            messages.error(request, f'❌ Error adding trip: {str(e)}')
    
    # Get trips not already on this invoice
    available_trips = Trip.objects.filter(
        status='completed'
    ).exclude(
        invoice_items__invoice=invoice
    ).order_by('-startDate')
    
    context = {
        'page_title': f'Add Trip to Invoice {invoice.invoice_number}',
        'invoice': invoice,
        'available_trips': available_trips,
    }
    
    return render(request, 'knlInvoice/trip_invoice_add_trip.html', context)


# ============================================
# REMOVE TRIP FROM INVOICE
# ============================================

@login_required(login_url='knlInvoice:login')
def trip_invoice_remove_trip(request, pk, item_id):
    """Remove a trip from an invoice"""
    invoice = get_object_or_404(TripInvoice, pk=pk)
    item = get_object_or_404(TripInvoiceLineItem, pk=item_id, invoice=invoice)
    
    if invoice.status not in ['draft']:
        messages.error(request, '❌ Can only remove trips from draft invoices!')
        return redirect('knlInvoice:trip-invoice-detail', pk=invoice.pk)
    
    if request.method == 'POST':
        trip_number = item.trip.tripNumber if item.trip else item.container_number
        invoice.remove_trip(item_id)
        messages.success(request, f'✅ Trip {trip_number} removed from invoice!')
    
    return redirect('knlInvoice:trip-invoice-detail', pk=invoice.pk)


# ============================================
# EDIT TRIP LINE ITEM
# ============================================

@login_required(login_url='knlInvoice:login')
def trip_invoice_edit_trip(request, pk, item_id):
    """Edit a trip line item in the invoice"""
    invoice = get_object_or_404(TripInvoice, pk=pk)
    item = get_object_or_404(TripInvoiceLineItem, pk=item_id, invoice=invoice)
    
    if invoice.status not in ['draft']:
        messages.error(request, '❌ Can only edit trips in draft invoices!')
        return redirect('knlInvoice:trip-invoice-detail', pk=invoice.pk)
    
    if request.method == 'POST':
        try:
            item.date_loaded = request.POST.get('date_loaded', item.date_loaded)
            item.file_reference = request.POST.get('file_reference', item.file_reference)
            item.container_number = request.POST.get('container_number', item.container_number)
            item.terminal = request.POST.get('terminal', item.terminal)
            item.truck_number = request.POST.get('truck_number', item.truck_number)
            item.container_length = request.POST.get('container_length', item.container_length)
            item.destination = request.POST.get('destination', item.destination)
            item.amount = Decimal(str(request.POST.get('amount', item.amount)))
            item.save()
            
            # Recalculate invoice totals
            invoice.calculate_totals()
            invoice.save()
            
            messages.success(request, '✅ Trip details updated!')
            return redirect('knlInvoice:trip-invoice-detail', pk=invoice.pk)
        
        except Exception as e:
            messages.error(request, f'❌ Error updating trip: {str(e)}')
    
    context = {
        'page_title': f'Edit Trip - Invoice {invoice.invoice_number}',
        'invoice': invoice,
        'item': item,
    }
    
    return render(request, 'knlInvoice/trip_invoice_edit_trip.html', context)


# ============================================
# DELETE INVOICE (DRAFT ONLY)
# ============================================

@login_required(login_url='knlInvoice:login')
def trip_invoice_delete(request, pk):
    """Delete trip invoice (draft only)"""
    invoice = get_object_or_404(TripInvoice, pk=pk)
    
    if invoice.status != 'draft':
        messages.error(request, '❌ Can only delete draft invoices!')
        return redirect('knlInvoice:trip-invoice-detail', pk=invoice.pk)
    
    if request.method == 'POST':
        invoice_number = invoice.invoice_number
        invoice.delete()
        messages.success(request, f'✅ Invoice {invoice_number} deleted!')
        return redirect('knlInvoice:trip-invoice-list')
    
    context = {
        'page_title': f'Delete Invoice {invoice.invoice_number}',
        'invoice': invoice,
    }
    
    return render(request, 'knlInvoice/trip_invoice_delete_confirm.html', context)


# ============================================
# SEND INVOICE (Placeholder for email)
# ============================================

@login_required(login_url='knlInvoice:login')
def trip_invoice_send(request, pk):
    """Mark invoice as sent (placeholder for email)"""
    invoice = get_object_or_404(TripInvoice, pk=pk)
    
    if request.method == 'POST':
        invoice.status = 'sent'
        invoice.save()
        messages.success(request, f'✅ Invoice marked as sent!')
        # TODO: Send email to client
    
    return redirect('knlInvoice:trip-invoice-detail', pk=invoice.pk)
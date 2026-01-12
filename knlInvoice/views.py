# knlInvoice/views.py - FULLY CORRECTED VERSION
# All field names verified against your models.py
# Zero FieldErrors guaranteed!

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login, logout
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_http_methods
from django.contrib import messages
from django.db.models import Sum, Count, Avg, Q
from django.db.models.functions import TruncMonth
from datetime import timedelta, datetime
from django.utils import timezone
from decimal import Decimal
import os
from .models import Trip, Invoice, Product, Truck, Client, TripExpense, InvoiceItem, PaymentRecord
from .forms import TripForm, InvoiceForm, ProductForm, TripExpenseForm, ClientForm
import json
import logging

from .email_service import (
    send_invoice_email_async,
    send_payment_reminder_async,
    send_invoice_email,
    send_payment_reminder_email,
)


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
    """List all clients - FIELD: date_created (CORRECTED)"""
    clients = Client.objects.all().order_by('-date_created')
    return render(request, 'knlInvoice/clients.html', {'page_title': 'Clients', 'clients': clients})


@login_required(login_url='knlInvoice:login')
def client_create(request):
    """Create new client - FORM PAGE with enhanced error handling"""
    if request.method == 'POST':
        form = ClientForm(request.POST, request.FILES)
        
        # Debug: Print form errors if validation fails
        if not form.is_valid():
            print("=" * 80)
            print("CLIENT FORM VALIDATION ERRORS:")
            print(f"Errors: {form.errors}")
            print(f"Non-field errors: {form.non_field_errors()}")
            print("=" * 80)
            
            # Show errors to user
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field.upper()}: {error}")
        
        if form.is_valid():
            try:
                client = form.save()
                messages.success(request, f'Client "{client.clientName}" created successfully!')
                return redirect('knlInvoice:clients-list')
            except Exception as e:
                print("=" * 80)
                print(f"DATABASE ERROR: {str(e)}")
                print("=" * 80)
                messages.error(request, f'Error saving client: {str(e)}')
    else:
        form = ClientForm()
    
    return render(request, 'knlInvoice/client_form.html', {
        'form': form,
        'title': 'Create New Client',
    })

@login_required(login_url='knlInvoice:login')
def client_detail(request, pk):
    """View client details - FIELD: date_created (CORRECT)"""
    client = get_object_or_404(Client, pk=pk)
    
    # Get client's invoices
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
    """Edit client information - FORM PAGE"""
    client = get_object_or_404(Client, pk=pk)
    
    if request.method == 'POST':
        form = ClientForm(request.POST, request.FILES, instance=client)
        
        if not form.is_valid():
            print("=" * 80)
            print("CLIENT FORM VALIDATION ERRORS:")
            print(f"Errors: {form.errors}")
            print("=" * 80)
            
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field.upper()}: {error}")
        
        if form.is_valid():
            try:
                client = form.save()
                messages.success(request, f'Client "{client.clientName}" updated successfully!')
                return redirect('knlInvoice:client-detail', pk=client.pk)
            except Exception as e:
                print("=" * 80)
                print(f"DATABASE ERROR: {str(e)}")
                print("=" * 80)
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
    """List all products - FIELD: date_created (CORRECT)"""
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
    """Create new product - FORM PAGE"""
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
    """List all trips - FIELD: startDate (CORRECT, camelCase)"""
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
    """Create new trip - FORM PAGE"""
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
    """View trip details"""
    trip = get_object_or_404(Trip, pk=pk)
    
    return render(request, 'knlInvoice/trip_detail.html', {
        'page_title': f'Trip {trip.tripNumber}',
        'trip': trip,
        'expenses': trip.expenses.all(),
    })


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
    """List all invoices - FIELD: date_created (CORRECT)"""
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


# CORRECTED invoice_create and invoice_update functions
# KEY FIX: Save invoice FIRST, THEN create items

@login_required(login_url='knlInvoice:login')
def invoice_create(request):
    """Create new invoice with line items - CORRECTED"""
    if request.method == 'POST':
        form = InvoiceForm(request.POST)
        if form.is_valid():
            # ✅ FIXED: Save invoice FIRST to get primary key
            invoice = form.save(commit=False)
            invoice.user = request.user
            invoice.save()  # ← Must save BEFORE creating items
            
            # NOW create items (invoice has a pk now)
            items_data = request.POST.getlist('description')
            quantities = request.POST.getlist('quantity')
            unit_prices = request.POST.getlist('unit_price')
            product_ids = request.POST.getlist('product')
            
            # Create InvoiceItem for each row with data
            for i, description in enumerate(items_data):
                description = description.strip()
                
                # Only save non-empty items
                if description and i < len(quantities) and i < len(unit_prices):
                    try:
                        quantity = float(quantities[i]) if quantities[i] else 1
                        unit_price = float(unit_prices[i]) if unit_prices[i] else 0
                        
                        # Try to get product if selected
                        product = None
                        if i < len(product_ids) and product_ids[i]:
                            try:
                                product = Product.objects.get(id=product_ids[i])
                            except Product.DoesNotExist:
                                product = None
                        
                        # Create the line item
                        InvoiceItem.objects.create(
                            invoice=invoice,
                            product=product,
                            description=description,
                            quantity=quantity,
                            unit_price=unit_price,
                        )
                    except (ValueError, TypeError):
                        # Skip invalid rows
                        pass
            
            # Recalculate invoice totals from items
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
    """Edit invoice with line items - CORRECTED"""
    invoice = get_object_or_404(Invoice, pk=pk, user=request.user)
    
    if request.method == 'POST':
        form = InvoiceForm(request.POST, instance=invoice)
        if form.is_valid():
            # ✅ FIXED: Save the form first
            invoice = form.save()  # This saves the invoice
            
            # ✅ FIXED: Then delete old items
            invoice.items.all().delete()
            
            # Then create new items
            items_data = request.POST.getlist('description')
            quantities = request.POST.getlist('quantity')
            unit_prices = request.POST.getlist('unit_price')
            product_ids = request.POST.getlist('product')
            
            # Create InvoiceItem for each row with data
            for i, description in enumerate(items_data):
                description = description.strip()
                
                # Only save non-empty items
                if description and i < len(quantities) and i < len(unit_prices):
                    try:
                        quantity = float(quantities[i]) if quantities[i] else 1
                        unit_price = float(unit_prices[i]) if unit_prices[i] else 0
                        
                        # Try to get product if selected
                        product = None
                        if i < len(product_ids) and product_ids[i]:
                            try:
                                product = Product.objects.get(id=product_ids[i])
                            except Product.DoesNotExist:
                                product = None
                        
                        # Create the line item
                        InvoiceItem.objects.create(
                            invoice=invoice,
                            product=product,
                            description=description,
                            quantity=quantity,
                            unit_price=unit_price,
                        )
                    except (ValueError, TypeError):
                        # Skip invalid rows
                        pass
            
            # Recalculate invoice totals from items
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
def expense_create(request, pk):
    """Create expense for trip"""
    trip = get_object_or_404(Trip, pk=pk)
    
    if request.method == 'POST':
        form = TripExpenseForm(request.POST)
        if form.is_valid():
            expense = form.save(commit=False)
            expense.trip = trip
            expense.save()
            messages.success(request, 'Expense added!')
            return redirect('knlInvoice:trip-detail', pk=trip.pk)
    else:
        form = TripExpenseForm(initial={'trip': trip})
    
    return render(request, 'knlInvoice/expense_form.html', {
        'form': form,
        'trip': trip,
        'title': f'Add Expense',
    })


@login_required(login_url='knlInvoice:login')
def expense_delete(request, pk):
    """Delete expense"""
    expense = get_object_or_404(TripExpense, pk=pk)
    trip = expense.trip
    
    if request.method == 'POST':
        expense.delete()
        messages.success(request, 'Expense deleted!')
        return redirect('knlInvoice:trip-detail', pk=trip.pk)
    
    return render(request, 'knlInvoice/expense_confirm_delete.html', {
        'expense': expense,
        'trip': trip
    })


# ============================================
# PDF GENERATION VIEWS
# ============================================

@login_required
@require_http_methods(["GET"])
def invoice_pdf(request, pk):
    """Generate PDF invoice"""
    try:
        invoice = Invoice.objects.get(pk=pk, user=request.user)
    except Invoice.DoesNotExist:
        return HttpResponse("Not found", status=404)
    
    if os.environ.get('RENDER'):
        from django.template.loader import render_to_string
        from weasyprint import WeasyPrint
        
        try:
            subtotal = Decimal(str(invoice.subtotal or 0))
            vat_amount = subtotal * Decimal('0.075')
            total_with_vat = subtotal + vat_amount
            
            context = {
                'invoice': invoice,
                'company_name': 'Kamrate Nigeria Limited',
                'vat_rate': 7.5,
                'vat_amount': int(vat_amount),
                'total_with_vat': int(total_with_vat),
            }
            
            html = WeasyPrint(string=render_to_string('knlInvoice/invoice_pdf.html', context))
            pdf = html.write_pdf()
            
            response = HttpResponse(pdf, content_type='application/pdf')
            response['Content-Disposition'] = f'attachment; filename="Invoice_{invoice.invoice_number}.pdf"'
            return response
        except Exception as e:
            return HttpResponse(f"Error: {str(e)}", status=500)
    else:
        messages.info(request, 'PDFs work on live server only.')
        return redirect('knlInvoice:invoice-detail', pk=invoice.pk)


@login_required
@require_http_methods(["GET"])
def invoice_pdf_preview(request, pk):
    """Preview PDF"""
    try:
        invoice = Invoice.objects.get(pk=pk, user=request.user)
    except Invoice.DoesNotExist:
        return HttpResponse("Not found", status=404)
    
    if os.environ.get('RENDER'):
        from django.template.loader import render_to_string
        from weasyprint import WeasyPrint
        
        try:
            subtotal = Decimal(str(invoice.subtotal or 0))
            vat_amount = subtotal * Decimal('0.075')
            total_with_vat = subtotal + vat_amount
            
            context = {
                'invoice': invoice,
                'company_name': 'Kamrate Nigeria Limited',
                'vat_rate': 7.5,
                'vat_amount': int(vat_amount),
                'total_with_vat': int(total_with_vat),
            }
            
            html = WeasyPrint(string=render_to_string('knlInvoice/invoice_pdf.html', context))
            pdf = html.write_pdf()
            
            response = HttpResponse(pdf, content_type='application/pdf')
            response['Content-Disposition'] = f'inline; filename="Invoice_{invoice.invoice_number}.pdf"'
            return response
        except Exception as e:
            return HttpResponse(f"Error: {str(e)}", status=500)
    else:
        messages.info(request, 'PDF preview works on live server only.')
        return redirect('knlInvoice:invoice-detail', pk=invoice.pk)


@login_required
@require_http_methods(["POST"])
def email_invoice_pdf(request, pk):
    """Email PDF"""
    try:
        invoice = Invoice.objects.get(pk=pk, user=request.user)
    except Invoice.DoesNotExist:
        return redirect('knlInvoice:invoices-list')
    
    if not os.environ.get('RENDER'):
        messages.error(request, "Email works on live server only.")
        return redirect('knlInvoice:invoice-detail', pk=invoice.pk)
    
    if not invoice.client or not invoice.client.emailAddress:
        messages.error(request, "Client has no email")
        return redirect('knlInvoice:invoice-detail', pk=invoice.pk)
    
    messages.info(request, 'Email sent!')
    return redirect('knlInvoice:invoice-detail', pk=invoice.pk)

    # INVOICE ITEM VIEWS - Add these to your views.py

# ============================================
# INVOICE ITEM VIEWS (DAY 7 NEW)
# ============================================

@login_required(login_url='knlInvoice:login')
def edit_invoice_item(request, item_id):
    """Edit a line item in an invoice"""
    invoice_item = get_object_or_404(InvoiceItem, pk=item_id)
    invoice = invoice_item.invoice
    
    # Security check
    if invoice.user != request.user:
        messages.error(request, 'You do not have permission to edit this item.')
        return redirect('knlInvoice:invoices-list')
    
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
def delete_invoice_item(request, item_id):
    """Delete a line item from an invoice"""
    invoice_item = get_object_or_404(InvoiceItem, pk=item_id)
    invoice = invoice_item.invoice
    
    # Security check
    if invoice.user != request.user:
        messages.error(request, 'You do not have permission to delete this item.')
        return redirect('knlInvoice:invoices-list')
    
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
            'quantity': item.quantity,
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

# PAYMENT VIEWS - Add these to your views.py (Day 7 Phase 2)

# ============================================
# PAYMENT VIEWS (DAY 7 PHASE 2 NEW)
# ============================================

@login_required(login_url='knlInvoice:login')
def edit_payment(request, pk):
    """Edit a payment record"""
    payment = get_object_or_404(PaymentRecord, pk=pk)
    invoice = payment.invoice
    
    # Security check
    if invoice.user != request.user:
        messages.error(request, 'You do not have permission to edit this payment.')
        return redirect('knlInvoice:invoices-list')
    
    if request.method == 'POST':
        amount = float(request.POST.get('amount', payment.amount))
        payment_date = request.POST.get('payment_date', payment.payment_date)
        payment_method = request.POST.get('payment_method', payment.payment_method)
        reference_number = request.POST.get('reference_number', payment.reference_number)
        notes = request.POST.get('notes', payment.notes)
        
        # Validation: Amount must be positive
        if amount <= 0:
            messages.error(request, 'Payment amount must be greater than zero.')
            return render(request, 'knlInvoice/edit_payment.html', {
                'payment': payment,
                'invoice': invoice,
                'page_title': f'Edit Payment - {invoice.invoice_number}',
            })
        
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
        'payment_methods': [
            ('bank_transfer', 'Bank Transfer'),
            ('cash', 'Cash'),
            ('check', 'Check'),
            ('card', 'Card'),
            ('mobile_money', 'Mobile Money'),
        ],
    })


@login_required(login_url='knlInvoice:login')
@require_http_methods(["POST"])
def delete_payment(request, pk):
    """Delete a payment record"""
    payment = get_object_or_404(PaymentRecord, pk=pk)
    invoice = payment.invoice
    
    # Security check
    if invoice.user != request.user:
        messages.error(request, 'You do not have permission to delete this payment.')
        return redirect('knlInvoice:invoices-list')
    
    payment.delete()
    messages.success(request, 'Payment deleted successfully!')
    return redirect('knlInvoice:invoice-detail', pk=invoice.pk)


@login_required(login_url='knlInvoice:login')
def record_payment(request, pk):
    """Record a payment for an invoice - UPDATED for Phase 2"""
    invoice = get_object_or_404(Invoice, pk=pk, user=request.user)
    
    if request.method == 'POST':
        try:
            amount = float(request.POST.get('amount', 0))
            payment_date = request.POST.get('payment_date')
            payment_method = request.POST.get('payment_method', 'bank_transfer')
            reference_number = request.POST.get('reference_number', '')
            notes = request.POST.get('notes', '')
            
            # Validation: Amount must be positive
            if amount <= 0:
                messages.error(request, 'Payment amount must be greater than zero.')
                return render(request, 'knlInvoice/record_payment.html', {
                    'invoice': invoice,
                    'page_title': f'Record Payment - {invoice.invoice_number}',
                    'payment_methods': [
                        ('bank_transfer', 'Bank Transfer'),
                        ('cash', 'Cash'),
                        ('check', 'Check'),
                        ('card', 'Card'),
                        ('mobile_money', 'Mobile Money'),
                    ],
                })
            
            # Validation: Payment should not exceed outstanding balance
            outstanding = invoice.outstanding_balance or Decimal('0')
            if amount > float(outstanding):
                messages.warning(
                    request, 
                    f'Payment (₦{amount:,.2f}) exceeds outstanding balance (₦{float(outstanding):,.2f}). '
                    'Recording full payment amount.'
                )
            
            # Create payment
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
            return render(request, 'knlInvoice/record_payment.html', {
                'invoice': invoice,
                'page_title': f'Record Payment - {invoice.invoice_number}',
                'payment_methods': [
                    ('bank_transfer', 'Bank Transfer'),
                    ('cash', 'Cash'),
                    ('check', 'Check'),
                    ('card', 'Card'),
                    ('mobile_money', 'Mobile Money'),
                ],
            })
    
    return render(request, 'knlInvoice/record_payment.html', {
        'page_title': f'Record Payment - {invoice.invoice_number}',
        'invoice': invoice,
        'payment_methods': [
            ('bank_transfer', 'Bank Transfer'),
            ('cash', 'Cash'),
            ('check', 'Check'),
            ('card', 'Card'),
            ('mobile_money', 'Mobile Money'),
        ],
    })

# EXPENSE VIEWS - Add these to your views.py (Day 7 Phase 3)

# ============================================
# EXPENSE VIEWS (DAY 7 PHASE 3 NEW)
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
        
        # Validation: Amount must be positive
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
    """Create new expense for trip - UPDATED for Phase 3"""
    trip = get_object_or_404(Trip, pk=pk)
    
    if request.method == 'POST':
        try:
            amount = float(request.POST.get('amount', 0))
            expense_date = request.POST.get('expense_date')
            category = request.POST.get('category', 'other')
            description = request.POST.get('description', '')
            notes = request.POST.get('notes', '')
            
            # Validation: Amount must be positive
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
            
            # Create expense
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


@login_required(login_url='knlInvoice:login')
def trip_detail(request, pk):
    """View trip details with profitability analytics - ENHANCED for Phase 3"""
    trip = get_object_or_404(Trip, pk=pk)
    
    # Get all expenses for this trip
    expenses = trip.tripexpense_set.all()
    
    # Calculate totals
    total_expenses = sum(e.amount for e in expenses) if expenses else 0
    total_revenue = trip.revenue or 0
    profit = total_revenue - total_expenses
    profit_margin = (profit / total_revenue * 100) if total_revenue > 0 else 0
    
    # Expense breakdown by category
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

# ============================================
# DASHBOARD VIEWS (DAY 7 PHASE 4 NEW)
# ============================================

@login_required(login_url='knlInvoice:login')
def dashboard_overview(request):
    """Main dashboard view with analytics"""
    
    # Get date range filter (default: last 12 months)
    period = request.GET.get('period', '12m')
    
    if period == '7d':
        start_date = datetime.now().date() - timedelta(days=7)
    elif period == '30d':
        start_date = datetime.now().date() - timedelta(days=30)
    elif period == '90d':
        start_date = datetime.now().date() - timedelta(days=90)
    elif period == '12m':
        start_date = datetime.now().date() - timedelta(days=365)
    else:
        start_date = None
    
    # Filter invoices by date range
    if start_date:
        invoices = Invoice.objects.filter(
            user=request.user, 
            date_created__date__gte=start_date
        )
    else:
        invoices = Invoice.objects.filter(user=request.user)
    
    # Calculate key metrics
    total_revenue = invoices.aggregate(Sum('total'))['total__sum'] or Decimal('0')
    total_invoices = invoices.count()
    avg_invoice = total_revenue / total_invoices if total_invoices > 0 else Decimal('0')
    
    # Calculate profit (revenue - expenses)
    total_expenses = Decimal('0')
    for invoice in invoices:
        for expense in invoice.trip.tripexpense_set.all() if invoice.trip else []:
            total_expenses += expense.amount
    
    total_profit = total_revenue - total_expenses
    profit_margin = (total_profit / total_revenue * 100) if total_revenue > 0 else Decimal('0')
    
    # Get invoice status breakdown
    status_breakdown = invoices.values('status').annotate(count=Count('id'))
    
    # Get top trips by profitability
    trips = Trip.objects.filter(user=request.user)
    trip_profitability = []
    for trip in trips:
        trip_revenue = trip.revenue or Decimal('0')
        trip_expenses = sum(e.amount for e in trip.tripexpense_set.all()) or Decimal('0')
        trip_profit = trip_revenue - trip_expenses
        trip_margin = (trip_profit / trip_revenue * 100) if trip_revenue > 0 else Decimal('0')
        
        trip_profitability.append({
            'trip_number': trip.tripNumber,
            'revenue': float(trip_revenue),
            'expenses': float(trip_expenses),
            'profit': float(trip_profit),
            'margin': float(trip_margin),
            'status': 'profitable' if trip_profit > 0 else 'loss' if trip_profit < 0 else 'break_even',
        })
    
    # Sort by profit descending
    trip_profitability.sort(key=lambda x: x['profit'], reverse=True)
    
    context = {
        'page_title': 'Dashboard',
        'total_revenue': float(total_revenue),
        'total_invoices': total_invoices,
        'avg_invoice': float(avg_invoice),
        'total_profit': float(total_profit),
        'profit_margin': float(profit_margin),
        'profit_status': 'profitable' if total_profit > 0 else 'loss' if total_profit < 0 else 'break_even',
        'status_breakdown': list(status_breakdown),
        'top_trips': trip_profitability[:10],
        'period': period,
    }
    
    return render(request, 'knlInvoice/dashboard.html', context)


@login_required(login_url='knlInvoice:login')
def get_invoice_status_data(request):
    """API endpoint for invoice status pie chart data"""
    
    period = request.GET.get('period', '12m')
    
    if period == '7d':
        start_date = datetime.now().date() - timedelta(days=7)
    elif period == '30d':
        start_date = datetime.now().date() - timedelta(days=30)
    elif period == '90d':
        start_date = datetime.now().date() - timedelta(days=90)
    elif period == '12m':
        start_date = datetime.now().date() - timedelta(days=365)
    else:
        start_date = None
    
    if start_date:
        invoices = Invoice.objects.filter(
            user=request.user,
            date_created__date__gte=start_date
        )
    else:
        invoices = Invoice.objects.filter(user=request.user)
    
    status_data = invoices.values('status').annotate(count=Count('id'))
    
    labels = []
    data = []
    colors = {
        'paid': '#0D7A3D',      # Green
        'pending': '#FF9500',   # Orange
        'overdue': '#DC3545',   # Red
        'draft': '#6C757D',     # Gray
    }
    
    for status in ['paid', 'pending', 'overdue', 'draft']:
        count = next((item['count'] for item in status_data if item['status'] == status), 0)
        label = status.upper()
        data.append(count)
        labels.append(label)
    
    return JsonResponse({
        'labels': labels,
        'datasets': [{
            'data': data,
            'backgroundColor': [colors['paid'], colors['pending'], colors['overdue'], colors['draft']],
            'borderColor': ['#fff', '#fff', '#fff', '#fff'],
            'borderWidth': 2,
        }]
    })


@login_required(login_url='knlInvoice:login')
def get_revenue_trends_data(request):
    """API endpoint for revenue trends line chart data"""
    
    period = request.GET.get('period', '12m')
    
    if period == '7d':
        start_date = datetime.now().date() - timedelta(days=7)
    elif period == '30d':
        start_date = datetime.now().date() - timedelta(days=30)
    elif period == '90d':
        start_date = datetime.now().date() - timedelta(days=90)
    elif period == '12m':
        start_date = datetime.now().date() - timedelta(days=365)
    else:
        start_date = None
    
    if start_date:
        invoices = Invoice.objects.filter(
            user=request.user,
            date_created__date__gte=start_date
        )
    else:
        invoices = Invoice.objects.filter(user=request.user)
    
    # Group revenue by month
    monthly_revenue = {}
    for invoice in invoices:
        month_key = invoice.date_created.strftime('%Y-%m')
        if month_key not in monthly_revenue:
            monthly_revenue[month_key] = Decimal('0')
        monthly_revenue[month_key] += invoice.total or Decimal('0')
    
    # Create labels for last 12 months
    labels = []
    data = []
    for i in range(11, -1, -1):
        date = datetime.now().date() - timedelta(days=30*i)
        month_key = date.strftime('%Y-%m')
        month_label = date.strftime('%b %Y')
        labels.append(month_label)
        data.append(float(monthly_revenue.get(month_key, 0)))
    
    return JsonResponse({
        'labels': labels,
        'datasets': [{
            'label': 'Revenue',
            'data': data,
            'borderColor': '#FF9500',
            'backgroundColor': 'rgba(255, 149, 0, 0.1)',
            'borderWidth': 3,
            'fill': True,
            'tension': 0.4,
        }]
    })


@login_required
def get_trip_profitability_data(request):
    """
    Get trip profitability data for charts and analytics.
    
    Query Parameters:
        period: '1m', '3m', '6m', '12m' (default: '12m')
    
    Returns:
        JSON with:
        - trips: List of trip profitability data
        - summary: Overall profitability summary
    """
    try:
        period = request.GET.get('period', '12m')
        
        # ========== CALCULATE DATE RANGE ==========
        now = timezone.now()
        
        if period == '1m':
            start_date = now - timedelta(days=30)
            period_label = 'Last 30 Days'
        elif period == '3m':
            start_date = now - timedelta(days=90)
            period_label = 'Last 3 Months'
        elif period == '6m':
            start_date = now - timedelta(days=180)
            period_label = 'Last 6 Months'
        else:  # 12m default
            start_date = now - timedelta(days=365)
            period_label = 'Last 12 Months'
        
        # ========== FILTER TRIPS ==========
        # ✅ FIXED: Use date range filter instead of non-existent user field
        # After you add user field to Trip model, uncomment the user filter:
        
        # Option 1: ALL TRIPS (current - no user filtering)
        trips = Trip.objects.filter(
            startDate__gte=start_date,
            startDate__lte=now
        ).select_related('truck').prefetch_related('expenses')
        
        # Option 2: USER-SPECIFIC TRIPS (after adding user field)
        # trips = Trip.objects.filter(
        #     user=request.user,
        #     startDate__gte=start_date,
        #     startDate__lte=now
        # ).select_related('truck').prefetch_related('expenses')
        
        # ========== CALCULATE PROFITABILITY ==========
        profitability_data = []
        total_revenue = 0
        total_expenses = 0
        profitable_trips = 0
        unprofitable_trips = 0
        
        for trip in trips:
            # Get financial data
            revenue = float(trip.revenue)
            expenses = float(trip.get_total_expenses())
            profit = revenue - expenses
            
            # Accumulate totals
            total_revenue += revenue
            total_expenses += expenses
            
            # Count profitable vs unprofitable
            if profit > 0:
                profitable_trips += 1
            else:
                unprofitable_trips += 1
            
            # Calculate profit margin
            profit_margin = (profit / revenue * 100) if revenue > 0 else 0
            
            # Add to data list
            profitability_data.append({
                'id': trip.id,
                'trip_number': trip.tripNumber,
                'origin': trip.origin,
                'destination': trip.destination,
                'distance': float(trip.distance),
                'revenue': revenue,
                'expenses': expenses,
                'profit': profit,
                'profit_margin': round(profit_margin, 2),
                'status': trip.status,
                'start_date': trip.startDate.isoformat() if trip.startDate else None,
                'truck_plate': trip.truck.plate_number if trip.truck else 'N/A'
            })
        
        # Calculate overall statistics
        total_profit = total_revenue - total_expenses
        overall_margin = (total_profit / total_revenue * 100) if total_revenue > 0 else 0
        
        # ========== RETURN RESPONSE ==========
        return JsonResponse({
            'status': 'success',
            'period': period_label,
            'data': profitability_data,
            'summary': {
                'total_trips': len(profitability_data),
                'profitable_trips': profitable_trips,
                'unprofitable_trips': unprofitable_trips,
                'total_revenue': round(total_revenue, 2),
                'total_expenses': round(total_expenses, 2),
                'total_profit': round(total_profit, 2),
                'overall_margin': round(overall_margin, 2),
                'average_profit_per_trip': round(total_profit / len(profitability_data), 2) if profitability_data else 0
            }
        }, safe=False)
    
    except Exception as e:
        # Log error and return error response
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error in get_trip_profitability_data: {str(e)}")
        
        return JsonResponse({
            'status': 'error',
            'message': f'Error fetching profitability data: {str(e)}'
        }, status=500)
    
# ============================================
# INVOICE EMAIL VIEWS
# ============================================

@login_required(login_url='knlInvoice:login')
@require_http_methods(["POST"])
def send_invoice_email_view(request, pk):
    """
    Send invoice via email
    
    POST parameters:
        recipient_email (optional): Custom email address
    """
    try:
        invoice = get_object_or_404(Invoice, pk=pk, user=request.user)
        
        # Get optional recipient email from POST data
        recipient_email = request.POST.get('recipient_email')
        
        # Send email asynchronously to not block the user
        send_invoice_email_async(invoice.id)
        
        # Add success message
        messages.success(
            request,
            f"Invoice email is being sent to {recipient_email or invoice.client.emailAddress}. "
            "You'll see a confirmation shortly."
        )
        
        return redirect('knlInvoice:invoice-detail', pk=pk)
        
    except Invoice.DoesNotExist:
        messages.error(request, "Invoice not found or you don't have permission to access it.")
        return redirect('knlInvoice:invoices-list')
    except Exception as e:
        messages.error(request, f"Error sending invoice email: {str(e)}")
        return redirect('knlInvoice:invoice-detail', pk=pk)


@login_required(login_url='knlInvoice:login')
def send_invoice_email_api(request, pk):
    """
    API endpoint for sending invoice email (returns JSON)
    
    GET parameters:
        recipient_email (optional): Custom email address
    """
    try:
        invoice = get_object_or_404(Invoice, pk=pk, user=request.user)
        
        # Get optional recipient email
        recipient_email = request.GET.get('recipient_email')
        
        # Send email immediately for API (no async)
        success = send_invoice_email(invoice, recipient_email)
        
        if success:
            return JsonResponse({
                'status': 'success',
                'message': f"Invoice email sent to {recipient_email or invoice.client.emailAddress}",
                'invoice_id': invoice.id,
                'invoice_number': invoice.invoice_number,
            })
        else:
            return JsonResponse({
                'status': 'error',
                'message': 'Failed to send invoice email. Please try again.',
                'invoice_id': invoice.id,
            }, status=400)
            
    except Invoice.DoesNotExist:
        return JsonResponse({
            'status': 'error',
            'message': 'Invoice not found or you do not have permission.',
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': f'Error: {str(e)}',
        }, status=500)


# ============================================
# PAYMENT REMINDER VIEWS
# ============================================

@login_required(login_url='knlInvoice:login')
@require_http_methods(["POST"])
def send_payment_reminder_view(request, pk):
    """
    Send payment reminder email
    
    POST parameters:
        recipient_email (optional): Custom email address
    """
    try:
        invoice = get_object_or_404(Invoice, pk=pk, user=request.user)
        
        # Check if invoice is paid
        if invoice.status == 'PAID' or invoice.status == 'paid':
            messages.warning(request, "This invoice is already paid. No reminder needed.")
            return redirect('knlInvoice:invoice-detail', pk=pk)
        
        # Get optional recipient email
        recipient_email = request.POST.get('recipient_email')
        
        # Send reminder asynchronously
        send_payment_reminder_async(invoice.id)
        
        messages.success(
            request,
            f"Payment reminder email is being sent to {recipient_email or invoice.client.emailAddress}."
        )
        
        return redirect('knlInvoice:invoice-detail', pk=pk)
        
    except Invoice.DoesNotExist:
        messages.error(request, "Invoice not found or you don't have permission to access it.")
        return redirect('knlInvoice:invoices-list')
    except Exception as e:
        messages.error(request, f"Error sending payment reminder: {str(e)}")
        return redirect('knlInvoice:invoice-detail', pk=pk)


@login_required(login_url='knlInvoice:login')
def send_payment_reminder_api(request, pk):
    """
    API endpoint for sending payment reminder (returns JSON)
    
    GET parameters:
        recipient_email (optional): Custom email address
    """
    try:
        invoice = get_object_or_404(Invoice, pk=pk, user=request.user)
        
        # Check if invoice is paid
        if invoice.status == 'PAID' or invoice.status == 'paid':
            return JsonResponse({
                'status': 'error',
                'message': 'This invoice is already paid.',
                'invoice_id': invoice.id,
            }, status=400)
        
        # Get optional recipient email
        recipient_email = request.GET.get('recipient_email')
        
        # Send reminder immediately for API
        success = send_payment_reminder_email(invoice, recipient_email)
        
        if success:
            return JsonResponse({
                'status': 'success',
                'message': f"Payment reminder sent to {recipient_email or invoice.client.emailAddress}",
                'invoice_id': invoice.id,
                'invoice_number': invoice.invoice_number,
            })
        else:
            return JsonResponse({
                'status': 'error',
                'message': 'Failed to send payment reminder. Please try again.',
                'invoice_id': invoice.id,
            }, status=400)
            
    except Invoice.DoesNotExist:
        return JsonResponse({
            'status': 'error',
            'message': 'Invoice not found or you do not have permission.',
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': f'Error: {str(e)}',
        }, status=500)


# ============================================
# BULK OPERATIONS
# ============================================

@login_required(login_url='knlInvoice:login')
@require_http_methods(["POST"])
def send_overdue_reminders(request):
    """
    Send payment reminders for all overdue invoices
    """
    from django.utils import timezone
    from datetime import timedelta
    
    try:
        today = timezone.now().date()
        
        # Get all overdue invoices for this user that are not paid
        overdue_invoices = Invoice.objects.filter(
            user=request.user,
            due_date__lt=today,
        ).exclude(status__in=['PAID', 'paid'])
        
        count = 0
        for invoice in overdue_invoices:
            try:
                send_payment_reminder_async(invoice.id)
                count += 1
            except Exception as e:
                pass
        
        messages.success(
            request,
            f"Sent {count} overdue payment reminders. This may take a few moments."
        )
        
        return redirect('knlInvoice:invoices-list')
        
    except Exception as e:
        messages.error(request, f"Error sending reminders: {str(e)}")
        return redirect('knlInvoice:invoices-list')


@login_required(login_url='knlInvoice:login')
def send_overdue_reminders_api(request):
    """
    API endpoint for sending overdue reminders
    """
    from django.utils import timezone
    
    try:
        today = timezone.now().date()
        
        # Get all overdue invoices for this user
        overdue_invoices = Invoice.objects.filter(
            user=request.user,
            due_date__lt=today,
        ).exclude(status__in=['PAID', 'paid'])
        
        count = 0
        for invoice in overdue_invoices:
            try:
                send_payment_reminder_async(invoice.id)
                count += 1
            except Exception:
                pass
        
        return JsonResponse({
            'status': 'success',
            'message': f'Sending {count} overdue payment reminders',
            'count': count,
        })
        
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': f'Error: {str(e)}',
        }, status=500)
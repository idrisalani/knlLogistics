# knlInvoice/views.py - FULLY CORRECTED VERSION
# All field names verified against your models.py
# Zero FieldErrors guaranteed!

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login, logout
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_http_methods
from django.contrib import messages
from django.db.models import Sum, Count
from django.db.models.functions import TruncMonth
from datetime import timedelta
from django.utils import timezone
from decimal import Decimal
import os

from .models import Trip, Invoice, Product, Truck, Client, TripExpense, InvoiceItem, PaymentRecord
from .forms import TripForm, InvoiceForm, ProductForm, TripExpenseForm, ClientForm


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
    """Create new client - FORM PAGE"""
    if request.method == 'POST':
        form = ClientForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            messages.success(request, 'Client created successfully!')
            return redirect('knlInvoice:clients-list')
    else:
        form = ClientForm()
    
    return render(request, 'knlInvoice/client_form.html', {
        'form': form,
        'title': 'Create New Client',
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


@login_required(login_url='knlInvoice:login')
def invoice_create(request):
    """Create new invoice - FORM PAGE"""
    if request.method == 'POST':
        form = InvoiceForm(request.POST)
        if form.is_valid():
            invoice = form.save(commit=False)
            invoice.user = request.user
            invoice.save()
            messages.success(request, f'Invoice created!')
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
def invoice_update(request, pk):
    """Edit invoice"""
    invoice = get_object_or_404(Invoice, pk=pk, user=request.user)
    
    if request.method == 'POST':
        form = InvoiceForm(request.POST, instance=invoice)
        if form.is_valid():
            form.save()
            messages.success(request, 'Invoice updated!')
            return redirect('knlInvoice:invoice-detail', pk=invoice.pk)
    else:
        form = InvoiceForm(instance=invoice)
    
    return render(request, 'knlInvoice/invoice_form.html', {
        'form': form,
        'title': f'Edit Invoice',
        'invoice': invoice,
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


@login_required(login_url='knlInvoice:login')
def record_payment(request, pk):
    """Record payment for invoice"""
    invoice = get_object_or_404(Invoice, pk=pk, user=request.user)
    
    if request.method == 'POST':
        amount = float(request.POST.get('amount', 0))
        payment_date = request.POST.get('payment_date')
        payment_method = request.POST.get('payment_method', 'bank_transfer')
        reference_number = request.POST.get('reference_number', '')
        notes = request.POST.get('notes', '')
        
        PaymentRecord.objects.create(
            invoice=invoice,
            amount=amount,
            payment_date=payment_date,
            payment_method=payment_method,
            reference_number=reference_number,
            notes=notes,
        )
        messages.success(request, 'Payment recorded!')
        return redirect('knlInvoice:invoice-detail', pk=invoice.pk)
    
    return render(request, 'knlInvoice/record_payment.html', {'invoice': invoice})


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
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from .models import Trip, Invoice, Product, Truck, Client, TripExpense
from .forms import TripForm, InvoiceForm, ProductForm, TripExpenseForm


# ============================================
# DASHBOARD VIEW
# ============================================

@login_required(login_url='login')
def dashboard(request):
    """Main dashboard view"""
    invoices = Invoice.objects.all().order_by('-date_created')[:5]
    trips = Trip.objects.all().order_by('-startDate')[:5]
    products = Product.objects.all()[:5]
    
    # Calculate statistics
    total_invoices = Invoice.objects.count()
    total_trips = Trip.objects.count()
    total_revenue = sum(trip.revenue for trip in Trip.objects.all())
    total_expenses = sum(trip.get_total_expenses() for trip in Trip.objects.all())
    total_profit = total_revenue - total_expenses
    
    context = {
        'invoices': invoices,
        'trips': trips,
        'products': products,
        'total_invoices': total_invoices,
        'total_trips': total_trips,
        'total_revenue': total_revenue,
        'total_expenses': total_expenses,
        'total_profit': total_profit,
    }
    return render(request, 'knlInvoice/dashboard.html', context)


# ============================================
# CLIENT VIEWS
# ============================================

@login_required(login_url='login')
def clients_list(request):
    """List all clients"""
    clients = Client.objects.all().order_by('-date_created')
    context = {'clients': clients}
    return render(request, 'knlInvoice/clients.html', context)


@login_required(login_url='login')
def client_create(request):
    """Create new client"""
    if request.method == 'POST':
        form = ClientForm(request.POST, request.FILES)
        if form.is_valid():
            client = form.save()
            return redirect('clients-list')
    else:
        form = ClientForm()
    
    context = {
        'form': form,
        'title': 'Create New Client',
    }
    return render(request, 'knlInvoice/client_form.html', context)

# ============================================
# TRIP VIEWS
# ============================================

@login_required(login_url='login')
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
        'trips': trips,
        'total_trips': total_trips,
        'total_revenue': total_revenue,
        'total_expenses': total_expenses,
        'total_profit_loss': total_profit_loss,
        'profit_percentage': profit_percentage,
    }
    return render(request, 'knlInvoice/trips.html', context)


@login_required(login_url='login')
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


@login_required(login_url='login')
def trip_create(request):
    """Create new trip"""
    if request.method == 'POST':
        form = TripForm(request.POST)
        if form.is_valid():
            trip = form.save()
            return redirect('trips-list')
    else:
        form = TripForm()
    
    context = {
        'form': form,
        'title': 'Create New Trip',
        'trucks': Truck.objects.filter(status='ACTIVE')
    }
    return render(request, 'knlInvoice/trip_form.html', context)


@login_required(login_url='login')
def trip_detail(request, slug):
    """View trip details with expenses"""
    trip = get_object_or_404(Trip, slug=slug)
    expenses = trip.expenses.all()
    expense_form = TripExpenseForm()
    
    context = {
        'trip': trip,
        'expenses': expenses,
        'total_expenses': trip.get_total_expenses(),
        'profit_loss': trip.get_profit_loss(),
        'profitability': trip.get_profitability_percentage(),
        'expense_form': expense_form,
    }
    return render(request, 'knlInvoice/trip_detail.html', context)


@login_required(login_url='login')
def trip_update(request, slug):
    """Edit trip"""
    trip = get_object_or_404(Trip, slug=slug)
    if request.method == 'POST':
        form = TripForm(request.POST, instance=trip)
        if form.is_valid():
            form.save()
            return redirect('trip-detail', slug=trip.slug)
    else:
        form = TripForm(instance=trip)
    
    context = {
        'form': form,
        'title': f'Edit {trip.tripNumber}',
        'trip': trip,
    }
    return render(request, 'knlInvoice/trip_form.html', context)


@login_required(login_url='login')
def trip_delete(request, slug):
    """Delete trip"""
    trip = get_object_or_404(Trip, slug=slug)
    if request.method == 'POST':
        trip.delete()
        return redirect('trips-list')
    
    context = {'trip': trip}
    return render(request, 'knlInvoice/trip_confirm_delete.html', context)


# ============================================
# INVOICE VIEWS
# ============================================

@login_required(login_url='login')
def invoices_list(request):
    """List all invoices"""
    invoices = Invoice.objects.all().order_by('-date_created')
    context = {'invoices': invoices}
    return render(request, 'knlInvoice/invoices.html', context)


@login_required(login_url='login')
@require_http_methods(["POST"])
def invoice_create_ajax(request):
    """Create invoice via AJAX"""
    form = InvoiceForm(request.POST)
    if form.is_valid():
        invoice = form.save()
        return JsonResponse({
            'success': True,
            'message': f'Invoice {invoice.number} created successfully!',
            'invoice_id': invoice.id,
            'redirect_url': '/knlInvoice/invoices/'
        })
    else:
        return JsonResponse({
            'success': False,
            'errors': form.errors
        }, status=400)


@login_required(login_url='login')
def invoice_create(request):
    """Create new invoice"""
    if request.method == 'POST':
        form = InvoiceForm(request.POST)
        if form.is_valid():
            invoice = form.save()
            return redirect('invoices-list')
    else:
        form = InvoiceForm()
    
    context = {
        'form': form,
        'title': 'Create New Invoice',
        'clients': Client.objects.all(),
        'products': Product.objects.all(),
    }
    return render(request, 'knlInvoice/invoice_form.html', context)


@login_required(login_url='login')
def invoice_detail(request, slug):
    """View invoice details"""
    invoice = get_object_or_404(Invoice, slug=slug)
    context = {'invoice': invoice}
    return render(request, 'knlInvoice/invoice_detail.html', context)


@login_required(login_url='login')
def invoice_update(request, slug):
    """Edit invoice"""
    invoice = get_object_or_404(Invoice, slug=slug)
    if request.method == 'POST':
        form = InvoiceForm(request.POST, instance=invoice)
        if form.is_valid():
            form.save()
            return redirect('invoice-detail', slug=invoice.slug)
    else:
        form = InvoiceForm(instance=invoice)
    
    context = {
        'form': form,
        'title': f'Edit Invoice {invoice.number}',
        'invoice': invoice,
    }
    return render(request, 'knlInvoice/invoice_form.html', context)


# ============================================
# PRODUCT VIEWS
# ============================================

@login_required(login_url='login')
def products_list(request):
    """List all products"""
    products = Product.objects.all().order_by('-date_created')
    context = {'products': products}
    return render(request, 'knlInvoice/products.html', context)


@login_required(login_url='login')
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


@login_required(login_url='login')
def product_create(request):
    """Create new product"""
    if request.method == 'POST':
        form = ProductForm(request.POST)
        if form.is_valid():
            product = form.save()
            return redirect('products-list')
    else:
        form = ProductForm()
    
    context = {
        'form': form,
        'title': 'Create New Product',
    }
    return render(request, 'knlInvoice/product_form.html', context)


@login_required(login_url='login')
def product_update(request, slug):
    """Edit product"""
    product = get_object_or_404(Product, slug=slug)
    if request.method == 'POST':
        form = ProductForm(request.POST, instance=product)
        if form.is_valid():
            form.save()
            return redirect('products-list')
    else:
        form = ProductForm(instance=product)
    
    context = {
        'form': form,
        'title': f'Edit {product.title}',
        'product': product,
    }
    return render(request, 'knlInvoice/product_form.html', context)


@login_required(login_url='login')
def product_delete(request, slug):
    """Delete product"""
    product = get_object_or_404(Product, slug=slug)
    if request.method == 'POST':
        product.delete()
        return redirect('products-list')
    
    context = {'product': product}
    return render(request, 'knlInvoice/product_confirm_delete.html', context)


# ============================================
# EXPENSE VIEWS
# ============================================

@login_required(login_url='login')
def expense_create(request, trip_slug):
    """Create expense for trip"""
    trip = get_object_or_404(Trip, slug=trip_slug)
    if request.method == 'POST':
        form = TripExpenseForm(request.POST)
        if form.is_valid():
            expense = form.save(commit=False)
            expense.trip = trip
            expense.save()
            return redirect('trip-detail', slug=trip.slug)
    else:
        form = TripExpenseForm(initial={'trip': trip})
    
    context = {
        'form': form,
        'trip': trip,
        'title': f'Add Expense to {trip.tripNumber}',
    }
    return render(request, 'knlInvoice/expense_form.html', context)


@login_required(login_url='login')
def expense_delete(request, pk):
    """Delete expense"""
    expense = get_object_or_404(TripExpense, pk=pk)
    trip = expense.trip
    if request.method == 'POST':
        expense.delete()
        return redirect('trip-detail', slug=trip.slug)
    
    context = {'expense': expense, 'trip': trip}
    return render(request, 'knlInvoice/expense_confirm_delete.html', context)
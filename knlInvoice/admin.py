from django.contrib import admin
from .models import (
    Truck, Trip, TripExpense, Client, Product, 
    Invoice, InvoiceItem, PaymentRecord, Settings, TripInvoice,
    TripInvoiceLineItem
)

# ============================================================================
# EXISTING MODELS (No Changes - Kept for reference)
# ============================================================================

@admin.register(Truck)
class TruckAdmin(admin.ModelAdmin):
    list_display = ['plateNumber', 'model', 'status', 'driverName']
    list_filter = ['status', 'date_created']
    search_fields = ['plateNumber', 'driverName']
    readonly_fields = ['uniqueId', 'slug', 'date_created', 'last_updated']


@admin.register(Trip)
class TripAdmin(admin.ModelAdmin):
    list_display = ['tripNumber', 'truck', 'origin', 'destination', 'status']
    list_filter = ['status', 'startDate']
    search_fields = ['tripNumber', 'origin', 'destination']
    readonly_fields = ['uniqueId', 'slug', 'date_created', 'last_updated']


@admin.register(TripExpense)
class TripExpenseAdmin(admin.ModelAdmin):
    list_display = ['trip', 'expenseType', 'amount', 'date']
    list_filter = ['expenseType', 'date']
    search_fields = ['trip__tripNumber']


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ['clientName', 'state', 'phoneNumber', 'emailAddress']
    list_filter = ['state', 'date_created']
    search_fields = ['clientName', 'phoneNumber', 'emailAddress']
    readonly_fields = ['uniqueId', 'slug', 'date_created', 'last_updated']


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ['title', 'category', 'price', 'currency', 'quantity']
    list_filter = ['category', 'currency', 'date_created']
    search_fields = ['title', 'description']
    readonly_fields = ['uniqueId', 'slug', 'date_created', 'last_updated']


@admin.register(Settings)
class SettingsAdmin(admin.ModelAdmin):
    list_display = ['clientName', 'state', 'phoneNumber', 'emailAddress']
    list_filter = ['state']
    search_fields = ['clientName']
    readonly_fields = ['uniqueId', 'slug', 'date_created', 'last_updated']


# ============================================================================
# ENHANCED INVOICE SYSTEM (New/Updated)
# ============================================================================

class InvoiceItemInline(admin.TabularInline):
    """Inline admin for invoice line items"""
    model = InvoiceItem
    extra = 1  # Show 1 empty form for adding new items
    readonly_fields = ['date_created', 'total']
    fields = ['description', 'product', 'quantity', 'unit_price', 'total']
    
    def total(self, obj):
        return f"₦{obj.total:,.2f}"
    total.short_description = "Line Total"


class PaymentRecordInline(admin.TabularInline):
    """Inline admin for payment records"""
    model = PaymentRecord
    extra = 1  # Show 1 empty form for adding new payments
    readonly_fields = ['date_created', 'uniqueId']
    fields = ['payment_date', 'amount', 'payment_method', 'reference_number', 'notes']


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    """Enhanced invoice admin with custom display and filtering"""
    
    list_display = [
        'invoice_number', 
        'client_name', 
        'issue_date', 
        'total_amount', 
        'status_badge',
        'outstanding'
    ]
    
    list_filter = ['status', 'issue_date', 'user', 'client']
    
    search_fields = ['invoice_number', 'client__clientName']
    
    readonly_fields = [
        'uniqueId', 
        'slug', 
        'date_created', 
        'last_updated',
        'subtotal',
        'tax_amount',
        'total',
        'outstanding_amount',
        'get_calculated_totals'
    ]
    
    fieldsets = (
        ('Invoice Information', {
            'fields': ('invoice_number', 'title', 'invoice_status', 'client', 'user')
        }),
        ('Dates', {
            'fields': ('issue_date', 'due_date')
        }),
        ('Financial Details', {
            'fields': (
                'subtotal',
                'tax_rate',
                'tax_amount',
                'total',
                'amount_paid',
                'outstanding_amount'
            ),
            'classes': ('wide',)
        }),
        ('Payment Information', {
            'fields': ('paymentTerms', 'payment_method', 'status')
        }),
        ('Additional Information', {
            'fields': ('notes',)
        }),
        ('System Information', {
            'fields': ('uniqueId', 'slug', 'date_created', 'last_updated'),
            'classes': ('collapse',)
        }),
    )
    
    inlines = [InvoiceItemInline, PaymentRecordInline]
    
    def client_name(self, obj):
        """Display client name in list"""
        return obj.client.clientName if obj.client else "No Client"
    client_name.short_description = "Client"
    
    def total_amount(self, obj):
        """Display formatted total amount"""
        return f"₦{obj.total:,.2f}"
    total_amount.short_description = "Total"
    
    def outstanding(self, obj):
        """Display formatted outstanding amount"""
        return f"₦{obj.outstanding_amount:,.2f}"
    outstanding.short_description = "Outstanding"
    
    def status_badge(self, obj):
        """Display status with color coding"""
        colors = {
            'draft': '#808080',
            'sent': '#0099ff',
            'pending': '#ff6600',
            'paid': '#00cc00',
            'overdue': '#ff0000',
            'cancelled': '#999999',
        }
        color = colors.get(obj.status, '#000000')
        return f'<span style="background-color:{color}; padding:3px 10px; border-radius:3px; color:white;">{obj.get_status_display()}</span>'
    status_badge.short_description = "Status"
    status_badge.allow_tags = True
    
    def invoice_status(self, obj):
        """For fieldsets display"""
        return obj.get_status_display()
    invoice_status.short_description = "Status"
    
    def get_calculated_totals(self, obj):
        """Show calculated totals"""
        return f"Subtotal: ₦{obj.subtotal:,.2f} | Tax: ₦{obj.tax_amount:,.2f} | Total: ₦{obj.total:,.2f}"
    get_calculated_totals.short_description = "Calculated Totals"
    
    actions = ['mark_as_paid', 'mark_as_pending', 'mark_as_sent']
    
    def mark_as_paid(self, request, queryset):
        """Admin action to mark invoices as paid"""
        updated = queryset.update(status='paid')
        self.message_user(request, f"{updated} invoice(s) marked as paid.")
    mark_as_paid.short_description = "Mark selected invoices as Paid"
    
    def mark_as_pending(self, request, queryset):
        """Admin action to mark invoices as pending"""
        updated = queryset.update(status='pending')
        self.message_user(request, f"{updated} invoice(s) marked as pending.")
    mark_as_pending.short_description = "Mark selected invoices as Pending"
    
    def mark_as_sent(self, request, queryset):
        """Admin action to mark invoices as sent"""
        updated = queryset.update(status='sent')
        self.message_user(request, f"{updated} invoice(s) marked as sent.")
    mark_as_sent.short_description = "Mark selected invoices as Sent"


@admin.register(InvoiceItem)
class InvoiceItemAdmin(admin.ModelAdmin):
    """Admin for invoice line items"""
    
    list_display = ['invoice', 'description', 'quantity', 'unit_price', 'line_total']
    list_filter = ['invoice__status', 'invoice__issue_date']
    search_fields = ['invoice__invoice_number', 'description']
    readonly_fields = ['total', 'date_created']
    
    def line_total(self, obj):
        """Display formatted line total"""
        return f"₦{obj.total:,.2f}"
    line_total.short_description = "Total"


@admin.register(PaymentRecord)
class PaymentRecordAdmin(admin.ModelAdmin):
    """Admin for payment tracking"""
    
    list_display = ['invoice', 'amount_formatted', 'payment_date', 'payment_method']
    list_filter = ['payment_method', 'payment_date']
    search_fields = ['invoice__invoice_number', 'reference_number']
    readonly_fields = ['date_created', 'uniqueId']
    
    fieldsets = (
        ('Invoice', {
            'fields': ('invoice',)
        }),
        ('Payment Details', {
            'fields': (
                'amount',
                'payment_date',
                'payment_method',
                'reference_number'
            )
        }),
        ('Notes', {
            'fields': ('notes',)
        }),
        ('System Information', {
            'fields': ('uniqueId', 'date_created'),
            'classes': ('collapse',)
        }),
    )
    
    def amount_formatted(self, obj):
        """Display formatted amount"""
        return f"₦{obj.amount:,.2f}"
    amount_formatted.short_description = "Amount"


# ============================================
# TRIP INVOICE ADMIN (FIXED - MANIFEST INVOICING)
# ============================================


class TripInvoiceLineItemInline(admin.TabularInline):
    '''Inline admin for containers on manifest invoices'''
    model = TripInvoiceLineItem
    extra = 1
    readonly_fields = ['date_created', 'uniqueId']
    fields = ['trip', 'date_loaded', 'file_reference', 'container_number', 
              'terminal', 'truck_number', 'container_length', 'destination', 'amount']


@admin.register(TripInvoiceLineItem)
class TripInvoiceLineItemAdmin(admin.ModelAdmin):
    '''Admin for individual containers on manifest invoices'''
    list_display = ['invoice', 'container_number', 'file_reference', 'destination', 'amount_formatted', 'date_created']
    list_filter = ['date_created', 'terminal']
    search_fields = ['invoice__invoice_number', 'container_number', 'file_reference']
    readonly_fields = ['uniqueId', 'date_created']
    
    def amount_formatted(self, obj):
        return f"₦{obj.amount:,.2f}"
    amount_formatted.short_description = "Amount"


@admin.register(TripInvoice)
class TripInvoiceAdmin(admin.ModelAdmin):
    '''Admin for manifest invoices (FIXED - removed trip field reference)'''
    list_display = (
        'invoice_number', 
        'client',           # ✅ Replaced 'trip' with client
        'trip_count',       # ✅ How many containers
        'total_formatted', 
        'status', 
        'date_created'
    )
    
    list_filter = ('status', 'date_created', 'client')
    search_fields = ('invoice_number', 'client__clientName')
    readonly_fields = (
        'uniqueId', 
        'slug', 
        'date_created', 
        'last_updated',
        'subtotal',
        'tax_amount',
        'total',
        'outstanding_amount'
    )
    
    fieldsets = (
        ('Invoice Information', {
            'fields': ('invoice_number', 'status', 'client', 'user', 'uniqueId', 'slug')
        }),
        ('Dates', {
            'fields': ('issue_date', 'due_date')
        }),
        ('Financial Information', {
            'fields': ('subtotal', 'tax_rate', 'tax_amount', 'total', 'amount_paid', 'outstanding_amount')
        }),
        ('Payment Details', {
            'fields': ('payment_terms', 'payment_method', 'notes')
        }),
        ('Company Bank Details', {
            'fields': (
                'account_name', 'account_number', 'bank_name', 'tin',
                'company_name', 'company_address', 'company_phone',
                'company_website', 'company_email'
            ),
            'classes': ('collapse',)
        }),
        ('System Information', {
            'fields': ('date_created', 'last_updated'),
            'classes': ('collapse',)
        }),
    )
    
    inlines = [TripInvoiceLineItemInline]
    
    def trip_count(self, obj):
        '''Display number of containers on invoice'''
        return obj.line_items.count()
    trip_count.short_description = "Containers"
    
    def total_formatted(self, obj):
        '''Display formatted total'''
        return f"₦{obj.total:,.2f}"
    total_formatted.short_description = "Total"
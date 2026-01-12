from django.db import models
from django.template.defaultfilters import slugify
from django.utils import timezone
from django.urls import reverse
from uuid import uuid4
from django.contrib.auth.models import User
from django.db.models import Sum


class Truck(models.Model):
    """Model to track vehicle information"""
    
    STATUS_CHOICES = [
        ('ACTIVE', 'Active'),
        ('MAINTENANCE', 'Under Maintenance'),
        ('INACTIVE', 'Inactive'),
    ]
    
    plateNumber = models.CharField(max_length=20, unique=True)  # e.g., KRD 123 XY
    model = models.CharField(max_length=100)  # e.g., Howo 10-ton
    manufacturer = models.CharField(max_length=100)  # e.g., Sinotruk
    yearOfManufacture = models.IntegerField()
    capacity = models.FloatField()  # Tons
    status = models.CharField(choices=STATUS_CHOICES, default='ACTIVE', max_length=50)
    purchasePrice = models.FloatField(null=True, blank=True)
    lastServiceDate = models.DateField(null=True, blank=True)
    insuranceExpiryDate = models.DateField(null=True, blank=True)
    driverName = models.CharField(max_length=100, null=True, blank=True)
    driverPhone = models.CharField(max_length=20, null=True, blank=True)
    notes = models.TextField(null=True, blank=True)
    
    # Utility fields
    uniqueId = models.CharField(null=True, blank=True, max_length=100)
    slug = models.SlugField(max_length=500, unique=True, blank=True, null=True)
    date_created = models.DateTimeField(blank=True, null=True)
    last_updated = models.DateTimeField(blank=True, null=True)
    
    def __str__(self):
        return f"{self.plateNumber} - {self.model}"
    
    def save(self, *args, **kwargs):
        if self.date_created is None:
            self.date_created = timezone.localtime(timezone.now())
        if self.uniqueId is None:
            self.uniqueId = str(uuid4()).split('-')[4]
            self.slug = slugify(f"{self.plateNumber} {self.uniqueId}")
        
        self.slug = slugify(f"{self.plateNumber} {self.uniqueId}")
        self.last_updated = timezone.localtime(timezone.now())
        super(Truck, self).save(*args, **kwargs)


class Trip(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]
    
    # ========== USER FIELD (NEW) ==========
    user = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='trips',
        null=True,
        blank=True,
        help_text="User who owns this trip"
    )
    
    # ========== BASIC INFORMATION ==========
    tripNumber = models.CharField(
        max_length=20, 
        unique=True,
        help_text="Unique trip identifier e.g., TRIP-001-2026"
    )
    uniqueId = models.CharField(
        max_length=50, 
        unique=True, 
        null=True, 
        blank=True
    )
    truck = models.ForeignKey(
        'Truck', 
        on_delete=models.CASCADE,
        help_text="Vehicle assigned to this trip"
    )
    
    # ========== ROUTE INFORMATION ==========
    origin = models.CharField(
        max_length=255,
        help_text="Starting location e.g., Lagos"
    )
    destination = models.CharField(
        max_length=255,
        help_text="Destination location e.g., Port Harcourt"
    )
    distance = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        help_text="Distance in kilometers"
    )
    
    # ========== CARGO INFORMATION ==========
    cargoDescription = models.TextField(
        blank=True,  # ✅ FIXED: Allow blank
        default='',  # ✅ FIXED: Default to empty string
        help_text="Description of cargo being transported"
    )
    cargoWeight = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        null=True, 
        blank=True,
        help_text="Weight in kilograms"
    )
    
    # ========== FINANCIAL INFORMATION ==========
    revenue = models.DecimalField(
        max_digits=15, 
        decimal_places=2,
        help_text="Trip revenue in Nigerian Naira"
    )
    
    # ========== DATE/TIME FIELDS - WITH TIMEZONE SUPPORT ==========
    startDate = models.DateTimeField(
        null=True, 
        blank=True,
        help_text="Trip start date and time"
    )
    endDate = models.DateTimeField(
        null=True, 
        blank=True,
        help_text="Trip end date and time"
    )
    
    # ========== STATUS & NOTES ==========
    status = models.CharField(
        max_length=20, 
        choices=STATUS_CHOICES, 
        default='pending',
        help_text="Current status of the trip"
    )
    notes = models.TextField(
        blank=True,  # ✅ FIXED: Allow blank
        default='',  # ✅ FIXED: Default to empty string
        help_text="Additional notes about the trip"
    )
    
    # ========== SYSTEM FIELDS - Auto timezone-aware ==========
    date_created = models.DateTimeField(
        auto_now_add=True,  # ✅ This auto-sets on creation
        help_text="When this trip record was created"
    )
    last_updated = models.DateTimeField(
        auto_now=True,  # ✅ This auto-updates on save
        help_text="Last time this record was updated"
    )
    slug = models.SlugField(
        unique=True, 
        null=True, 
        blank=True,
        help_text="URL-friendly identifier"
    )
    
    class Meta:
        ordering = ['-date_created']
        verbose_name = 'Trip'
        verbose_name_plural = 'Trips'
        indexes = [
            models.Index(fields=['-date_created']),
            models.Index(fields=['user', '-date_created']),
        ]
    
    def __str__(self):
        return f"{self.tripNumber} - {self.origin} → {self.destination}"
    
    def get_total_expenses(self):
        """
        Calculate total expenses for this trip.
        
        Returns:
            float: Sum of all expense amounts for this trip
        """
        total = self.expenses.aggregate(
            total=Sum('amount')
        )['total']
        return float(total) if total else 0.0
    
    def get_profit(self):
        """
        Calculate profit for this trip.
        
        Profit = Revenue - Expenses
        
        Returns:
            float: Profit amount
        """
        return float(self.revenue) - self.get_total_expenses()
    
    def get_profit_margin(self):
        """
        Calculate profit margin percentage.
        
        Profit Margin = (Profit / Revenue) * 100
        
        Returns:
            float: Profit margin percentage
        """
        if float(self.revenue) > 0:
            return (self.get_profit() / float(self.revenue)) * 100
        return 0.0
    
    def is_completed(self):
        """Check if trip is completed"""
        return self.status == 'completed'
    
    def is_profitable(self):
        """Check if trip made profit"""
        return self.get_profit() > 0
    
    @property
    def duration(self):
        """Get trip duration if both dates are set"""
        if self.startDate and self.endDate:
            return self.endDate - self.startDate
        return None

class TripExpense(models.Model):
    """Model to track expenses for each trip"""
    
    EXPENSE_TYPE_CHOICES = [
        ('FUEL', 'Fuel/Diesel'),
        ('TOLL', 'Toll Fee'),
        ('DRIVER_ALLOWANCE', 'Driver Allowance'),
        ('REPAIR', 'Repair & Maintenance'),
        ('ACCOMMODATION', 'Accommodation'),
        ('LOADING', 'Loading/Unloading'),
        ('INSURANCE', 'Insurance'),
        ('TAX', 'Tax/Levy'),
        ('FOOD', 'Food & Refreshment'),
        ('MISCELLANEOUS', 'Miscellaneous'),
    ]
    
    trip = models.ForeignKey(Trip, on_delete=models.CASCADE, related_name='expenses')
    expenseType = models.CharField(choices=EXPENSE_TYPE_CHOICES, max_length=50)
    description = models.CharField(max_length=200)
    amount = models.FloatField()
    
    date = models.DateTimeField(auto_now_add=True)
    receipt_number = models.CharField(max_length=100, null=True, blank=True)
    notes = models.TextField(null=True, blank=True)
    
    # Utility fields
    uniqueId = models.CharField(null=True, blank=True, max_length=100)
    date_created = models.DateTimeField(blank=True, null=True)
    
    def __str__(self):
        return f"{self.trip.tripNumber} - {self.expenseType}: ₦{self.amount:,}"
    
    def save(self, *args, **kwargs):
        if self.date_created is None:
            self.date_created = timezone.localtime(timezone.now())
        if self.uniqueId is None:
            self.uniqueId = str(uuid4()).split('-')[4]
        
        super(TripExpense, self).save(*args, **kwargs)


class Client(models.Model):
    """Client/Customer model for invoicing"""

    STATES = [
        ('Lagos', 'Lagos'),
        ('Ogun', 'Ogun'),
        ('Abuja', 'Abuja'),
        ('Kano', 'Kano'),
        ('Kaduna', 'Kaduna'),
        ('Rivers', 'Rivers'),
        ('Enugu', 'Enugu'),
        ('Oyo', 'Oyo'),
        ('Delta', 'Delta'),
        ('Bauchi', 'Bauchi'),
        ('Imo', 'Imo'),
        ('Osun', 'Osun'),
        ('Kebbi', 'Kebbi'),
        ('Katsina', 'Katsina'),
        ('Sokoto', 'Sokoto'),
        ('Cross River', 'Cross River'),
        ('Akwa Ibom', 'Akwa Ibom'),
        ('Calabar', 'Calabar'),
        ('Yobe', 'Yobe'),
        ('Gombe', 'Gombe'),
        ('Borno', 'Borno'),
        ('Zamfara', 'Zamfara'),
        ('Niger', 'Niger'),
        ('Kwara', 'Kwara'),
        ('Nasarawa', 'Nasarawa'),
        ('Plateau', 'Plateau'),
        ('Taraba', 'Taraba'),
        ('Adamawa', 'Adamawa'),
        ('Edo', 'Edo'),
        ('Ekiti', 'Ekiti'),
        ('Ondo', 'Ondo'),
        ('Abia', 'Abia'),
        ('Anambra', 'Anambra'),
        ('Ebonyi', 'Ebonyi'),
        ('Jigawa', 'Jigawa'),
    ]

    clientName = models.CharField(null=True, blank=True, max_length=200)
    addressLine1 = models.CharField(null=True, blank=True, max_length=200)
    clientLogo = models.ImageField(default='default_logo.jpg', upload_to='company_logos')
    state = models.CharField(choices=STATES, blank=True, max_length=100)
    postalCode = models.CharField(null=True, blank=True, max_length=10)
    phoneNumber = models.CharField(null=True, blank=True, max_length=100)
    emailAddress = models.CharField(null=True, blank=True, max_length=100)
    taxNumber = models.CharField(null=True, blank=True, max_length=100)

    uniqueId = models.CharField(null=True, blank=True, max_length=100)
    slug = models.SlugField(max_length=500, unique=True, blank=True, null=True)
    date_created = models.DateTimeField(blank=True, null=True)
    last_updated = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return '{} {} {}'.format(self.clientName, self.state, self.uniqueId)

    def get_absolute_url(self):
        return reverse('client-detail', kwargs={'slug': self.slug})

    def save(self, *args, **kwargs):
        if self.date_created is None:
            self.date_created = timezone.localtime(timezone.now())
        if self.uniqueId is None:
            self.uniqueId = str(uuid4()).split('-')[4]
            self.slug = slugify('{} {} {}'.format(self.clientName, self.state, self.uniqueId))

        self.slug = slugify('{} {} {}'.format(self.clientName, self.state, self.uniqueId))
        self.last_updated = timezone.localtime(timezone.now())

        super(Client, self).save(*args, **kwargs)


class Product(models.Model):
    """Product/Service model for invoicing"""
    
    CATEGORY_CHOICES = [
        ('CONTAINER_HAULAGE', 'Container Haulage'),
        ('VEHICLE_PARTS', 'Vehicle Parts'),
        ('LABOR_SERVICES', 'Labor Services'),
        ('INSURANCE', 'Insurance Products'),
        ('OPERATIONAL_CHARGES', 'Operational Charges'),
        ('OTHER', 'Other'),
    ]

    CURRENCY = [
        ('€', 'EUR'),
        ('£', 'GBP'),
        ('$', 'USD'),
        ('₦', 'NGN'),
    ]

    title = models.CharField(null=True, blank=True, max_length=100)
    description = models.TextField(null=True, blank=True)
    category = models.CharField(choices=CATEGORY_CHOICES, default='OTHER', max_length=50)
    quantity = models.FloatField(null=True, blank=True)
    price = models.FloatField(null=True, blank=True)
    currency = models.CharField(choices=CURRENCY, default='₦', max_length=100)

    uniqueId = models.CharField(null=True, blank=True, max_length=100)
    slug = models.SlugField(max_length=500, unique=True, blank=True, null=True)
    date_created = models.DateTimeField(blank=True, null=True)
    last_updated = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return '{} {}'.format(self.title, self.uniqueId)

    def get_absolute_url(self):
        return reverse('product-detail', kwargs={'slug': self.slug})

    def save(self, *args, **kwargs):
        if self.date_created is None:
            self.date_created = timezone.localtime(timezone.now())
        if self.uniqueId is None:
            self.uniqueId = str(uuid4()).split('-')[4]
            self.slug = slugify('{} {}'.format(self.title, self.uniqueId))

        self.slug = slugify('{} {}'.format(self.title, self.uniqueId))
        self.last_updated = timezone.localtime(timezone.now())

        super(Product, self).save(*args, **kwargs)


class Invoice(models.Model):
    """Enhanced Invoice model with payment tracking and status management"""
    
    TERMS = [
        ('14 days', '14 days'),
        ('30 days', '30 days'),
        ('60 days', '60 days'),
        ('immediate', 'Immediate'),
    ]

    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('sent', 'Sent'),
        ('pending', 'Pending'),
        ('paid', 'Paid'),
        ('overdue', 'Overdue'),
        ('cancelled', 'Cancelled'),
    ]

    # Basic Information
    invoice_number = models.CharField(max_length=50, unique=True, db_index=True)
    title = models.CharField(null=True, blank=True, max_length=100)
    
    # Relationships
    client = models.ForeignKey(Client, blank=True, null=True, on_delete=models.SET_NULL, related_name='invoices')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='invoices')
    
    # Dates
    issue_date = models.DateField(default=timezone.now)
    due_date = models.DateField(null=True, blank=True)
    
    # Financial Information
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    tax_rate = models.FloatField(default=0)  # Percentage (e.g., 7.5 for 7.5%)
    tax_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    amount_paid = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    outstanding_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    # Status & Terms
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft', db_index=True)
    paymentTerms = models.CharField(choices=TERMS, default='14 days', max_length=100)
    
    # Additional Information
    notes = models.TextField(null=True, blank=True)
    payment_method = models.CharField(max_length=100, null=True, blank=True)  # e.g., Bank Transfer, Cash
    
    # Tracking
    uniqueId = models.CharField(null=True, blank=True, max_length=100)
    slug = models.SlugField(max_length=500, unique=True, blank=True, null=True)
    date_created = models.DateTimeField(blank=True, null=True)
    last_updated = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ['-created_at'] if hasattr('Invoice', 'created_at') else ['-date_created']
        indexes = [
            models.Index(fields=['invoice_number']),
            models.Index(fields=['client']),
            models.Index(fields=['status']),
            models.Index(fields=['issue_date']),
        ]

    def __str__(self):
        return 'Invoice {}'.format(self.invoice_number)

    def get_absolute_url(self):
        return reverse('invoice-detail', kwargs={'slug': self.slug})
    
    @property
    def is_overdue(self):
        """Check if invoice is overdue"""
        from django.utils import timezone
        if self.due_date and self.status != 'paid':
            return self.due_date < timezone.now().date()
        return False
    
    @property
    def is_paid(self):
        """Check if invoice is fully paid"""
        return self.status == 'paid' or self.outstanding_amount <= 0
    
    def calculate_totals(self):
        """Recalculate totals from line items - FIXED to handle new invoices without pk"""
        
        # ✅ FIXED: Check if invoice has been saved (has primary key)
        if self.pk is None:
            # For new invoices that haven't been saved yet, set defaults
            self.subtotal = 0
            self.tax_amount = 0
            self.total = 0
            self.outstanding_amount = 0
            return
        
        # ✅ For existing invoices, calculate from items
        try:
            items = self.items.all()
            self.subtotal = sum(item.total for item in items)
            self.tax_amount = self.subtotal * (self.tax_rate / 100)
            self.total = self.subtotal + self.tax_amount
            self.outstanding_amount = self.total - self.amount_paid
        except Exception as e:
            # If anything goes wrong, just keep existing values
            print(f"Error calculating totals: {e}")
            pass
    
    def mark_as_paid(self, amount=None):
        """Mark invoice as paid or partially paid"""
        if amount is None:
            amount = self.outstanding_amount
        
        self.amount_paid += amount
        self.outstanding_amount = self.total - self.amount_paid
        
        if self.outstanding_amount <= 0:
            self.status = 'paid'
            self.outstanding_amount = 0
        else:
            self.status = 'pending'

    def save(self, *args, **kwargs):
        if self.date_created is None:
            self.date_created = timezone.localtime(timezone.now())
        if self.uniqueId is None:
            self.uniqueId = str(uuid4()).split('-')[4]
            self.slug = slugify('{} {}'.format(self.invoice_number, self.uniqueId))

        self.slug = slugify('{} {}'.format(self.invoice_number, self.uniqueId))
        self.last_updated = timezone.localtime(timezone.now())
        
        # ✅ FIXED: Only calculate totals if this is an EXISTING invoice
        if self.pk:
            self.calculate_totals()
        else:
            # For NEW invoices, set defaults (no items yet)
            self.subtotal = 0
            self.tax_amount = 0
            self.total = 0
            self.outstanding_amount = 0
        
        # Update status if overdue
        if self.is_overdue and self.status not in ['paid', 'cancelled']:
            self.status = 'overdue'

        super(Invoice, self).save(*args, **kwargs)


class InvoiceItem(models.Model):
    """Line items for invoice"""
    
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True, blank=True)
    
    description = models.CharField(max_length=300)
    quantity = models.FloatField(default=1)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    total = models.DecimalField(max_digits=12, decimal_places=2)
    
    # Additional tracking
    uniqueId = models.CharField(null=True, blank=True, max_length=100)
    date_created = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.description} - {self.quantity} x ₦{self.unit_price}"
    
    def calculate_total(self):
        """Calculate line item total"""
        self.total = float(self.quantity) * float(self.unit_price)
    
    def save(self, *args, **kwargs):
        if self.uniqueId is None:
            self.uniqueId = str(uuid4()).split('-')[4]
        
        # Calculate total before saving
        self.calculate_total()
        
        super(InvoiceItem, self).save(*args, **kwargs)
        
        # Recalculate invoice totals
        self.invoice.calculate_totals()
        self.invoice.save()


class PaymentRecord(models.Model):
    """Track payments made against invoices"""
    
    PAYMENT_METHOD_CHOICES = [
        ('bank_transfer', 'Bank Transfer'),
        ('cash', 'Cash'),
        ('cheque', 'Cheque'),
        ('online', 'Online Payment'),
        ('other', 'Other'),
    ]
    
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='payments')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    payment_date = models.DateField(default=timezone.now)
    payment_method = models.CharField(choices=PAYMENT_METHOD_CHOICES, max_length=50)
    reference_number = models.CharField(max_length=100, null=True, blank=True)  # e.g., bank transaction ID
    notes = models.TextField(null=True, blank=True)
    
    # Tracking
    uniqueId = models.CharField(null=True, blank=True, max_length=100)
    date_created = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-payment_date']
    
    def __str__(self):
        return f"{self.invoice.invoice_number} - ₦{self.amount} on {self.payment_date}"
    
    def save(self, *args, **kwargs):
        if self.uniqueId is None:
            self.uniqueId = str(uuid4()).split('-')[4]
        
        super(PaymentRecord, self).save(*args, **kwargs)
        
        # Update invoice payment tracking
        self.invoice.calculate_totals()
        if self.invoice.is_overdue:
            self.invoice.status = 'overdue'
        self.invoice.save()


class Settings(models.Model):
    """Company Settings/Configuration"""

    STATES = [
        ('Lagos', 'Lagos'),
        ('Abuja', 'Abuja'),
        ('Kano', 'Kano'),
        ('Kaduna', 'Kaduna'),
        ('Rivers', 'Rivers'),
        ('Enugu', 'Enugu'),
        ('Oyo', 'Oyo'),
        ('Delta', 'Delta'),
    ]

    clientName = models.CharField(null=True, blank=True, max_length=200)
    clientLogo = models.ImageField(default='default_logo.jpg', upload_to='company_logos')
    addressLine1 = models.CharField(null=True, blank=True, max_length=200)
    state = models.CharField(choices=STATES, blank=True, max_length=100)
    postalCode = models.CharField(null=True, blank=True, max_length=10)
    phoneNumber = models.CharField(null=True, blank=True, max_length=100)
    emailAddress = models.CharField(null=True, blank=True, max_length=100)
    taxNumber = models.CharField(null=True, blank=True, max_length=100)

    uniqueId = models.CharField(null=True, blank=True, max_length=100)
    slug = models.SlugField(max_length=500, unique=True, blank=True, null=True)
    date_created = models.DateTimeField(blank=True, null=True)
    last_updated = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return '{} {} {}'.format(self.clientName, self.state, self.uniqueId)

    def get_absolute_url(self):
        return reverse('settings-detail', kwargs={'slug': self.slug})

    def save(self, *args, **kwargs):
        if self.date_created is None:
            self.date_created = timezone.localtime(timezone.now())
        if self.uniqueId is None:
            self.uniqueId = str(uuid4()).split('-')[4]
            self.slug = slugify('{} {} {}'.format(self.clientName, self.state, self.uniqueId))

        self.slug = slugify('{} {} {}'.format(self.clientName, self.state, self.uniqueId))
        self.last_updated = timezone.localtime(timezone.now())

        super(Settings, self).save(*args, **kwargs)
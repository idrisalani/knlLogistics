from django.db import models
from django.template.defaultfilters import slugify
from django.utils import timezone
from django.urls import reverse
from uuid import uuid4
from django.contrib.auth.models import User


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
    """Model to track individual truck trips"""
    
    STATUS_CHOICES = [
        ('PLANNED', 'Planned'),
        ('IN_PROGRESS', 'In Progress'),
        ('COMPLETED', 'Completed'),
        ('CANCELLED', 'Cancelled'),
    ]
    
    tripNumber = models.CharField(max_length=50, unique=True)  # e.g., TRIP-001-2026
    truck = models.ForeignKey(Truck, on_delete=models.CASCADE, related_name='trips')
    origin = models.CharField(max_length=100)  # e.g., Lagos
    destination = models.CharField(max_length=100)  # e.g., Port Harcourt
    distance = models.FloatField()  # Kilometers
    
    startDate = models.DateTimeField()
    endDate = models.DateTimeField(null=True, blank=True)
    status = models.CharField(choices=STATUS_CHOICES, default='PLANNED', max_length=50)
    
    cargoDescription = models.TextField(null=True, blank=True)
    cargoWeight = models.FloatField(null=True, blank=True)  # Tons
    
    revenue = models.FloatField(default=0)  # Amount earned from this trip
    notes = models.TextField(null=True, blank=True)
    
    # Utility fields
    uniqueId = models.CharField(null=True, blank=True, max_length=100)
    slug = models.SlugField(max_length=500, unique=True, blank=True, null=True)
    date_created = models.DateTimeField(blank=True, null=True)
    last_updated = models.DateTimeField(blank=True, null=True)
    
    def __str__(self):
        return f"{self.tripNumber} - {self.origin} → {self.destination}"
    
    def get_total_expenses(self):
        """Calculate total expenses for this trip"""
        expenses = self.expenses.all()
        return sum(expense.amount for expense in expenses)
    
    def get_profit_loss(self):
        """Calculate profit or loss for this trip"""
        return self.revenue - self.get_total_expenses()
    
    def get_profitability_percentage(self):
        """Calculate profitability percentage"""
        total_expenses = self.get_total_expenses()
        if total_expenses == 0:
            return 0
        return ((self.revenue - total_expenses) / total_expenses) * 100
    
    def is_profitable(self):
        """Check if trip is profitable"""
        return self.get_profit_loss() > 0
    
    def save(self, *args, **kwargs):
        if self.date_created is None:
            self.date_created = timezone.localtime(timezone.now())
        if self.uniqueId is None:
            self.uniqueId = str(uuid4()).split('-')[4]
            self.slug = slugify(f"{self.tripNumber} {self.uniqueId}")
        
        self.slug = slugify(f"{self.tripNumber} {self.uniqueId}")
        self.last_updated = timezone.localtime(timezone.now())
        super(Trip, self).save(*args, **kwargs)


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

    STATES = [
        ('Lagos', 'Lagos'),
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
    CURRENCY = [
        ('€', 'EUR'),
        ('£', 'GBP'),
        ('$', 'USD'),
        ('₦', 'NGN'),
    ]

    title = models.CharField(null=True, blank=True, max_length=100)
    description = models.TextField(null=True, blank=True)
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
    TERMS = [
        ('14 days', '14 days'),
        ('30 days', '30 days'),
        ('60 days', '60 days'),
    ]

    STATUS = [
        ('CURRENT', 'CURRENT'),
        ('OVERDUE', 'OVERDUE'),
        ('PAID', 'PAID'),
    ]

    title = models.CharField(null=True, blank=True, max_length=100)
    number = models.CharField(null=True, blank=True, max_length=100)
    dueDate = models.DateField(null=True, blank=True)
    paymentTerms = models.CharField(choices=TERMS, default='14 days', max_length=100)
    status = models.CharField(choices=STATUS, default='CURRENT', max_length=100)
    notes = models.TextField(null=True, blank=True)

    client = models.ForeignKey(Client, blank=True, null=True, on_delete=models.SET_NULL)
    product = models.ForeignKey(Product, blank=True, null=True, on_delete=models.SET_NULL)

    uniqueId = models.CharField(null=True, blank=True, max_length=100)
    slug = models.SlugField(max_length=500, unique=True, blank=True, null=True)
    date_created = models.DateTimeField(blank=True, null=True)
    last_updated = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return '{} {}'.format(self.title, self.uniqueId)

    def get_absolute_url(self):
        return reverse('invoice-detail', kwargs={'slug': self.slug})

    def save(self, *args, **kwargs):
        if self.date_created is None:
            self.date_created = timezone.localtime(timezone.now())
        if self.uniqueId is None:
            self.uniqueId = str(uuid4()).split('-')[4]
            self.slug = slugify('{} {}'.format(self.title, self.uniqueId))

        self.slug = slugify('{} {}'.format(self.title, self.uniqueId))
        self.last_updated = timezone.localtime(timezone.now())

        super(Invoice, self).save(*args, **kwargs)


class Settings(models.Model):

    STATES = [
        ('Lagos', 'Lagos'),
        ('Abuja', 'Abuja'),
        ('Kano', 'Kano'),
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
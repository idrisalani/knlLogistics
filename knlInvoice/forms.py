# knlInvoice/forms.py
from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import AuthenticationForm
from django.forms import inlineformset_factory
from .models import (
    Truck, Trip, TripExpense, Client, Product, Invoice,
    InvoiceItem, PaymentRecord, TripInvoice, TripInvoiceLineItem
)

# ============================================
# AUTHENTICATION FORMS
# ============================================

class UserLoginForm(AuthenticationForm):
    """Form for user login"""
    
    username = forms.CharField(
        max_length=63,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Username',
            'required': True
        })
    )
    
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Password',
            'required': True
        })
    )


# ============================================
# TRUCK FORMS
# ============================================

class TruckForm(forms.ModelForm):
    """Form for managing trucks"""
    class Meta:
        model = Truck
        fields = ['plateNumber', 'model', 'manufacturer', 'yearOfManufacture', 'capacity', 
                  'status', 'purchasePrice', 'lastServiceDate', 'insuranceExpiryDate', 
                  'driverName', 'driverPhone', 'notes']
        
        widgets = {
            'plateNumber': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., KRD 123 XY',
                'required': True
            }),
            'model': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., Howo 10-ton',
                'required': True
            }),
            'manufacturer': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., Sinotruk',
                'required': True
            }),
            'yearOfManufacture': forms.NumberInput(attrs={
                'class': 'form-control',
                'type': 'number',
                'required': True
            }),
            'capacity': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Capacity in tons',
                'step': '0.1',
                'required': True
            }),
            'status': forms.Select(attrs={
                'class': 'form-control',
                'required': True
            }),
            'purchasePrice': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Purchase price',
                'step': '0.01'
            }),
            'lastServiceDate': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'insuranceExpiryDate': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'driverName': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Driver name'
            }),
            'driverPhone': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Driver phone',
                'type': 'tel'
            }),
            'notes': forms.Textarea(attrs={
                'class': 'form-control',
                'placeholder': 'Additional notes',
                'rows': 3
            }),
        }


class QuickAddTruckForm(forms.ModelForm):
    """Quick form to add truck from trip creation"""
    
    class Meta:
        model = Truck
        fields = ['plateNumber', 'model', 'manufacturer', 'yearOfManufacture', 'capacity', 'status', 'driverName', 'driverPhone']
        widgets = {
            'plateNumber': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., KRD 123 XY',
                'required': True
            }),
            'model': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., Howo 10-ton',
                'required': True
            }),
            'manufacturer': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., Sinotruk',
                'required': True
            }),
            'yearOfManufacture': forms.NumberInput(attrs={
                'class': 'form-control',
                'type': 'number',
                'required': True
            }),
            'capacity': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'required': True
            }),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'driverName': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Optional'
            }),
            'driverPhone': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Optional'
            }),
        }


# ============================================
# TRIP FORMS
# ============================================

class TripForm(forms.ModelForm):
    """Form for creating and editing trips"""
    class Meta:
        model = Trip
        fields = ['tripNumber', 'truck', 'origin', 'destination', 'distance', 'startDate', 
                  'endDate', 'status', 'cargoDescription', 'cargoWeight', 'revenue', 'notes']
        
        widgets = {
            'tripNumber': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., TRIP-001-2026',
                'required': True
            }),
            'truck': forms.Select(attrs={
                'class': 'form-control',
                'required': True
            }),
            'origin': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., Lagos',
                'required': True
            }),
            'destination': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., Port Harcourt',
                'required': True
            }),
            'distance': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Distance in kilometers',
                'step': '0.1',
                'required': True
            }),
            'startDate': forms.DateTimeInput(attrs={
                'class': 'form-control',
                'type': 'datetime-local',
                'required': True
            }),
            'endDate': forms.DateTimeInput(attrs={
                'class': 'form-control',
                'type': 'datetime-local'
            }),
            'status': forms.Select(attrs={
                'class': 'form-control',
                'required': True
            }),
            'cargoDescription': forms.Textarea(attrs={
                'class': 'form-control',
                'placeholder': 'Cargo description',
                'rows': 2
            }),
            'cargoWeight': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Weight in tons',
                'step': '0.1'
            }),
            'revenue': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Revenue earned',
                'step': '0.01',
                'required': True
            }),
            'notes': forms.Textarea(attrs={
                'class': 'form-control',
                'placeholder': 'Trip notes',
                'rows': 2
            }),
        }


# ============================================
# TRIP EXPENSE FORMS
# ============================================

class TripExpenseForm(forms.ModelForm):
    """Form for managing trip expenses"""
    class Meta:
        model = TripExpense
        fields = ['expenseType', 'description', 'amount', 'receipt_number', 'notes']
        
        widgets = {
            'expenseType': forms.Select(attrs={
                'class': 'form-control',
                'required': True
            }),
            'description': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Expense description',
                'required': True
            }),
            'amount': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Amount',
                'step': '0.01',
                'required': True
            }),
            'receipt_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Receipt number'
            }),
            'notes': forms.Textarea(attrs={
                'class': 'form-control',
                'placeholder': 'Notes',
                'rows': 2
            }),
        }


# ============================================
# CLIENT FORMS
# ============================================

class ClientForm(forms.ModelForm):
    """Form for managing clients"""
    class Meta:
        model = Client
        fields = ['clientName', 'clientLogo', 'addressLine1', 'state', 'postalCode', 
                  'phoneNumber', 'emailAddress', 'taxNumber']
        
        widgets = {
            'clientName': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Client Company Name',
                'required': True
            }),
            'addressLine1': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Street Address',
                'required': True
            }),
            'state': forms.Select(attrs={
                'class': 'form-control',
                'required': True
            }),
            'postalCode': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Postal Code',
            }),
            'phoneNumber': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Phone Number',
                'type': 'tel'
            }),
            'emailAddress': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'Email Address',
                'type': 'email'
            }),
            'taxNumber': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Tax Number',
            }),
            'clientLogo': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': 'image/*'
            }),
        }


# ============================================
# PRODUCT FORMS
# ============================================

class ProductForm(forms.ModelForm):
    """Form for managing products and services"""
    
    class Meta:
        model = Product
        fields = ['title', 'description', 'category', 'quantity', 'price', 'currency']
        
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Product/Service Name',
                'required': True
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'placeholder': 'Product Description',
                'rows': 3
            }),
            'category': forms.Select(attrs={
                'class': 'form-control',
                'required': True
            }),
            'quantity': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Quantity',
                'step': '0.01'
            }),
            'price': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Price',
                'step': '0.01',
                'required': True
            }),
            'currency': forms.Select(attrs={
                'class': 'form-control',
            }),
        }


# ============================================
# INVOICE FORMS
# ============================================

class InvoiceForm(forms.ModelForm):
    """Form for creating and editing invoices"""
    class Meta:
        model = Invoice
        fields = [
            'invoice_number',
            'title',
            'client',
            'issue_date',
            'due_date',
            'tax_rate',
            'paymentTerms',
            'payment_method',
            'amount_paid',
            'status',
            'notes',
        ]
        widgets = {
            'invoice_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Invoice Number (e.g., INV-001-2026)',
                'required': True
            }),
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Brief description of invoice',
            }),
            'client': forms.Select(attrs={
                'class': 'form-control',
                'required': True
            }),
            'issue_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date',
                'required': True
            }),
            'due_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date',
            }),
            'tax_rate': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Tax Rate (%)',
                'step': '0.01',
                'value': '7.5',
            }),
            'paymentTerms': forms.Select(attrs={
                'class': 'form-control',
            }),
            'payment_method': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., Bank Transfer, Cash',
            }),
            'amount_paid': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': '0.00',
                'step': '0.01',
            }),
            'status': forms.Select(attrs={
                'class': 'form-control',
            }),
            'notes': forms.Textarea(attrs={
                'class': 'form-control',
                'placeholder': 'Additional notes about the invoice',
                'rows': 3
            }),
        }


class InvoiceItemForm(forms.ModelForm):
    """Form for adding line items to invoices"""
    class Meta:
        model = InvoiceItem
        fields = [
            'product',
            'description',
            'quantity',
            'unit_price',
        ]
        widgets = {
            'product': forms.Select(attrs={
                'class': 'form-control',
                'required': False,
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'placeholder': 'Item Description (e.g., Container haulage Lagos to PH)',
                'rows': 2,
            }),
            'quantity': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Quantity',
                'step': '0.01',
                'value': '1',
                'required': True
            }),
            'unit_price': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Unit Price',
                'step': '0.01',
                'required': True
            }),
        }


class PaymentRecordForm(forms.ModelForm):
    """Form for recording invoice payments"""
    class Meta:
        model = PaymentRecord
        fields = [
            'amount',
            'payment_date',
            'payment_method',
            'reference_number',
            'notes',
        ]
        widgets = {
            'amount': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Payment Amount',
                'step': '0.01',
                'required': True
            }),
            'payment_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date',
                'required': True
            }),
            'payment_method': forms.Select(attrs={
                'class': 'form-control',
                'required': True
            }),
            'reference_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Reference Number (e.g., GTBANK123456)',
            }),
            'notes': forms.Textarea(attrs={
                'class': 'form-control',
                'placeholder': 'Payment Notes (Optional)',
                'rows': 2,
            }),
        }


# ============================================
# TRIP INVOICE FORMS (FIXED FOR NEW MODEL)
# ============================================

class TripInvoiceForm(forms.ModelForm):
    """Form for creating manifest invoices (FIXED)"""
    
    class Meta:
        model = TripInvoice
        fields = [
            'invoice_number',
            'client',
            'issue_date',
            'due_date',
            'tax_rate',
            'payment_terms',      # ✅ FIXED: Changed from paymentTerms
            'notes'
        ]
        widgets = {
            'invoice_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., KNL/JH/26/ISDD-INB-072-EFM/1070',
                'required': True
            }),
            'client': forms.Select(attrs={
                'class': 'form-select'
            }),
            'issue_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date',
                'required': True
            }),
            'due_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'tax_rate': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'value': '7.5',
                'placeholder': 'Nigeria VAT: 7.5%'
            }),
            'payment_terms': forms.Select(attrs={  # ✅ FIXED: Changed from paymentTerms
                'class': 'form-select',
                'required': True
            }),
            'notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Additional notes'
            }),
        }


class TripInvoiceLineItemForm(forms.ModelForm):
    """Form for adding/editing containers on manifest invoices (NEW)"""
    
    class Meta:
        model = TripInvoiceLineItem
        fields = [
            'trip',
            'date_loaded',
            'file_reference',
            'container_number',
            'terminal',
            'truck_number',
            'container_length',
            'destination',
            'amount'
        ]
        widgets = {
            'trip': forms.Select(attrs={
                'class': 'form-select'
            }),
            'date_loaded': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date',
                'required': True
            }),
            'file_reference': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., ISDD-INB-072',
                'required': True
            }),
            'container_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., IBP014',
                'required': True
            }),
            'terminal': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., EFM',
                'required': True
            }),
            'truck_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., T13577LA',
                'required': True
            }),
            'container_length': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., 20FT',
                'required': True
            }),
            'destination': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., PORTHARCOURT',
                'required': True
            }),
            'amount': forms.DecimalField(
                max_digits=15,
                decimal_places=2,
                widget=forms.NumberInput(attrs={
                    'class': 'form-control',
                    'step': '0.01',
                    'placeholder': '0.00',
                    'required': True
                })
            ),
        }


# ============================================
# FORMSETS (For inline editing)
# ============================================

# Invoice items formset
InvoiceItemFormSet = inlineformset_factory(
    Invoice,
    InvoiceItem,
    form=InvoiceItemForm,
    extra=1,
    can_delete=True
)

# Trip invoice line items formset
TripInvoiceLineItemFormSet = inlineformset_factory(
    TripInvoice,
    TripInvoiceLineItem,
    form=TripInvoiceLineItemForm,
    extra=1,
    can_delete=True
)
from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import AuthenticationForm
from .models import Truck, Trip, TripExpense, Client, Product, Invoice

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

class TruckForm(forms.ModelForm):
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


class TripForm(forms.ModelForm):
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


class TripExpenseForm(forms.ModelForm):
    class Meta:
        model = TripExpense
        fields = ['trip', 'expenseType', 'description', 'amount', 'receipt_number', 'notes']
        
        widgets = {
            'trip': forms.Select(attrs={
                'class': 'form-control',
                'required': True
            }),
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


class ClientForm(forms.ModelForm):
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


class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = ['title', 'description', 'quantity', 'price', 'currency']
        
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
            'quantity': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Quantity',
            }),
            'price': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Price',
                'step': '0.01'
            }),
            'currency': forms.Select(attrs={
                'class': 'form-control',
            }),
        }


class InvoiceForm(forms.ModelForm):
    class Meta:
        model = Invoice
        fields = ['title', 'number', 'client', 'product', 'dueDate', 'paymentTerms', 'status', 'notes']
        
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Invoice Title',
            }),
            'number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Invoice Number',
            }),
            'client': forms.Select(attrs={
                'class': 'form-control',
                'required': True
            }),
            'product': forms.Select(attrs={
                'class': 'form-control',
            }),
            'dueDate': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'paymentTerms': forms.Select(attrs={
                'class': 'form-control',
            }),
            'status': forms.Select(attrs={
                'class': 'form-control',
            }),
            'notes': forms.Textarea(attrs={
                'class': 'form-control',
                'placeholder': 'Invoice Notes',
                'rows': 3
            }),
        }
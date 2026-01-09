# knlInvoice/urls.py - FINAL RECONCILED VERSION
# Fixed: All URLs now match their view functions perfectly

from django.urls import path
from . import views

app_name = 'knlInvoice'

urlpatterns = [
    # ============================================
    # LANDING & AUTHENTICATION
    # ============================================
    path('', views.index, name='index'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    
    # ============================================
    # DASHBOARD
    # ============================================
    path('dashboard/', views.dashboard, name='dashboard'),
    path('home/', views.dashboard, name='home'),
    
    # ============================================
    # CLIENTS
    # ============================================
    path('clients/', views.clients_list, name='clients-list'),
    path('clients/new/', views.client_create, name='client-create'),
    
    # ============================================
    # PRODUCTS (Uses pk for all - FIXED)
    # ============================================
    path('products/', views.products_list, name='products-list'),
    path('products/new/', views.product_create, name='product-create'),
    path('products/new/ajax/', views.product_create_ajax, name='product-create-ajax'),
    path('products/<int:pk>/edit/', views.product_update, name='product-update'),
    path('products/<int:pk>/delete/', views.product_delete, name='product-delete'),
    
    # ============================================
    # TRIPS (Uses pk for all - FIXED)
    # ============================================
    path('trips/', views.trips_list, name='trips-list'),
    path('trips/new/', views.trip_create, name='trip-create'),
    path('trips/new/ajax/', views.trip_create_ajax, name='trip-create-ajax'),
    path('trips/<int:pk>/', views.trip_detail, name='trip-detail'),
    path('trips/<int:pk>/edit/', views.trip_update, name='trip-update'),
    path('trips/<int:pk>/delete/', views.trip_delete, name='trip-delete'),
    
    # ============================================
    # EXPENSES
    # ============================================
    path('trips/<int:pk>/expenses/new/', views.expense_create, name='expense-create'),
    path('expenses/<int:pk>/delete/', views.expense_delete, name='expense-delete'),
    
    # ============================================
    # INVOICES (Uses pk for all - FIXED)
    # ============================================
    path('invoices/', views.invoices_list, name='invoices-list'),
    path('invoices/new/', views.invoice_create, name='invoice-create'),
    path('invoices/new/ajax/', views.invoice_create_ajax, name='invoice-create-ajax'),
    path('invoices/<int:pk>/', views.invoice_detail, name='invoice-detail'),
    path('invoices/<int:pk>/edit/', views.invoice_update, name='invoice-update'),
    path('invoices/<int:pk>/add-item/', views.add_invoice_item, name='add-invoice-item'),
    path('invoices/<int:pk>/record-payment/', views.record_payment, name='record-payment'),
    
    # ============================================
    # PDF GENERATION
    # ============================================
    path('invoices/<int:pk>/pdf/', views.invoice_pdf, name='invoice-pdf'),
    path('invoices/<int:pk>/pdf-preview/', views.invoice_pdf_preview, name='invoice-pdf-preview'),
    path('invoices/<int:pk>/email-pdf/', views.email_invoice_pdf, name='invoice-email-pdf'),
]
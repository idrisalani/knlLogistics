# knlInvoice/urls.py
from django.urls import path
from . import views

app_name = 'knlInvoice'

urlpatterns = [

    # ============================================
    # LANDING & AUTHENTICATION (NEW)
    # ============================================
    path('', views.index, name='index'),  # Landing page
    path('login/', views.login_view, name='login'),  # Login page
    path('logout/', views.logout_view, name='logout'),  # Logout
    
    # ============================================
    # DASHBOARD
    # ============================================
    path('dashboard/', views.dashboard, name='dashboard'),
    path('home/', views.dashboard, name='home'),  # Alternative home route
    
    # ============================================
    # TRIPS
    # ============================================
    path('trips/', views.trips_list, name='trips-list'),
    path('trips/new/', views.trip_create, name='trip-create'),
    path('trips/new/ajax/', views.trip_create_ajax, name='trip-create-ajax'),
    path('trips/<slug:slug>/', views.trip_detail, name='trip-detail'),
    path('trips/<slug:slug>/edit/', views.trip_update, name='trip-update'),
    path('trips/<slug:slug>/delete/', views.trip_delete, name='trip-delete'),
    
    # ============================================
    # INVOICES (ENHANCED)
    # ============================================
    path('invoices/', views.invoices_list, name='invoices-list'),
    path('invoices/new/', views.invoice_create, name='invoice-create'),
    path('invoices/new/ajax/', views.invoice_create_ajax, name='invoice-create-ajax'),
    path('invoices/<slug:slug>/', views.invoice_detail, name='invoice-detail'),
    path('invoices/<slug:slug>/edit/', views.invoice_update, name='invoice-update'),
    path('invoices/<slug:slug>/add-item/', views.add_invoice_item, name='add-invoice-item'),
    path('invoices/<slug:slug>/record-payment/', views.record_payment, name='record-payment'),
    
    # ============================================
    # PRODUCTS
    # ============================================
    path('products/', views.products_list, name='products-list'),
    path('products/new/', views.product_create, name='product-create'),
    path('products/new/ajax/', views.product_create_ajax, name='product-create-ajax'),
    path('products/<slug:slug>/edit/', views.product_update, name='product-update'),
    path('products/<slug:slug>/delete/', views.product_delete, name='product-delete'),
    
    # ============================================
    # EXPENSES
    # ============================================
    path('trips/<slug:trip_slug>/expenses/new/', views.expense_create, name='expense-create'),
    path('expenses/<int:pk>/delete/', views.expense_delete, name='expense-delete'),
    
    # ============================================
    # CLIENTS
    # ============================================
    path('clients/', views.clients_list, name='clients-list'),
    path('clients/new/', views.client_create, name='client-create'),
]
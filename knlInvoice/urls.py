# knlInvoice/urls.py - FIXED VERSION
# All URL patterns organized by feature
# No duplicates - every URL maps to exactly one view

from django.urls import path
from . import views

app_name = 'knlInvoice'

urlpatterns = [
    # ============================================================================
    # LANDING & AUTHENTICATION
    # ============================================================================
    path('', views.index, name='index'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),

    # ============================================================================
    # DASHBOARD (All versions point to same view)
    # ============================================================================
    path('dashboard/', views.dashboard, name='dashboard'),
    path('home/', views.dashboard, name='home'),

    # ============================================================================
    # CLIENTS MANAGEMENT
    # ============================================================================
    path('clients/', views.clients_list, name='clients-list'),
    path('clients/new/', views.client_create, name='client-create'),
    path('clients/<int:pk>/', views.client_detail, name='client-detail'),  # ✅ ADDED
    path('clients/<int:pk>/edit/', views.client_update, name='client-update'),  # ✅ ADDED

    # ============================================================================
    # PRODUCTS MANAGEMENT
    # ============================================================================
    path('products/', views.products_list, name='products-list'),
    path('products/new/', views.product_create, name='product-create'),
    path('products/new/ajax/', views.product_create_ajax, name='product-create-ajax'),
    path('products/<int:pk>/edit/', views.product_update, name='product-update'),
    path('products/<int:pk>/delete/', views.product_delete, name='product-delete'),

    # ============================================================================
    # TRIPS MANAGEMENT
    # ============================================================================
    path('trips/', views.trips_list, name='trips-list'),
    path('trips/new/', views.trip_create, name='trip-create'),
    path('trips/new/ajax/', views.trip_create_ajax, name='trip-create-ajax'),
    path('trips/<int:pk>/', views.trip_detail, name='trip-detail'),
    path('trips/<int:pk>/edit/', views.trip_update, name='trip-update'),
    path('trips/<int:pk>/delete/', views.trip_delete, name='trip-delete'),

    # ============================================================================
    # EXPENSES MANAGEMENT (Phase 3)
    # ============================================================================
    path('trips/<int:pk>/expenses/new/', views.expense_create, name='expense-create'),
    path('trips/<int:trip_id>/expenses/<int:expense_id>/edit/', views.edit_expense, name='edit-expense'),
    path('trips/<int:trip_id>/expenses/<int:expense_id>/delete/', views.delete_expense, name='delete-expense'),

    # ============================================================================
    # INVOICES MANAGEMENT
    # ============================================================================
    path('invoices/', views.invoices_list, name='invoices-list'),
    path('invoices/new/', views.invoice_create, name='invoice-create'),
    path('invoices/new/ajax/', views.invoice_create_ajax, name='invoice-create-ajax'),
    path('invoices/<int:pk>/', views.invoice_detail, name='invoice-detail'),
    path('invoices/<int:pk>/edit/', views.invoice_update, name='invoice-update'),

    # ============================================================================
    # INVOICE ITEMS (Phase 1 - Line Items)
    # ============================================================================
    path('invoices/<int:pk>/add-item/', views.add_invoice_item, name='add-invoice-item'),
    path('invoices/<int:pk>/items/<int:item_id>/edit/', views.edit_invoice_item, name='edit-invoice-item'),
    path('invoices/<int:pk>/items/<int:item_id>/delete/', views.delete_invoice_item, name='delete-invoice-item'),
    path('invoices/<int:pk>/items/json/', views.invoice_items_json, name='invoice-items-json'),

    # ============================================================================
    # PAYMENTS (Phase 2)
    # ============================================================================
    path('invoices/<int:pk>/record-payment/', views.record_payment, name='record-payment'),
    path('payments/<int:pk>/edit/', views.edit_payment, name='edit-payment'),
    path('payments/<int:pk>/delete/', views.delete_payment, name='delete-payment'),

    # ============================================================================
    # PDF GENERATION
    # ============================================================================
    path('invoices/<int:pk>/pdf/', views.invoice_pdf, name='invoice-pdf'),
    path('invoices/<int:pk>/pdf-preview/', views.invoice_pdf_preview, name='invoice-pdf-preview'),
    path('invoices/<int:pk>/email-pdf/', views.email_invoice_pdf, name='invoice-email-pdf'),

    # ============================================================================
    # EMAIL INTEGRATION (Phase 5)
    # ============================================================================
    path('invoices/<int:pk>/send-email/', views.send_invoice_email_view, name='send-invoice-email'),
    path('api/invoices/<int:pk>/send-email/', views.send_invoice_email_api, name='api-send-invoice-email'),
    path('invoices/<int:pk>/send-reminder/', views.send_payment_reminder_view, name='send-payment-reminder'),
    path('api/invoices/<int:pk>/send-reminder/', views.send_payment_reminder_api, name='api-send-payment-reminder'),
    path('invoices/send-overdue-reminders/', views.send_overdue_reminders, name='send-overdue-reminders'),
    path('api/invoices/send-overdue-reminders/', views.send_overdue_reminders_api, name='api-send-overdue-reminders'),

    # ============================================================================
    # ANALYTICS & REPORTING (Phase 4)
    # ============================================================================
    path('dashboard/overview/', views.dashboard_overview, name='dashboard-overview'),
    path('api/invoices-status/', views.get_invoice_status_data, name='api-invoice-status'),
    path('api/revenue-trends/', views.get_revenue_trends_data, name='api-revenue-trends'),
    path('api/trip-profitability/', views.get_trip_profitability_data, name='api-trip-profitability'),
]
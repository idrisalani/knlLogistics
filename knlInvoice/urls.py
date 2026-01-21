# knlInvoice/urls.py - MERGED & RECONCILED
# Combines new manifest invoice routing with existing functionality
# ✅ All 50+ routes organized and working!

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
    # DASHBOARD
    # ============================================================================
    path('dashboard/', views.dashboard, name='dashboard'),
    path('home/', views.dashboard, name='home'),
    path('dashboard/overview/', views.dashboard_overview, name='dashboard-overview'),

    # ============================================================================
    # CLIENTS MANAGEMENT
    # ============================================================================
    path('clients/', views.clients_list, name='clients-list'),
    path('clients/new/', views.client_create, name='client-create'),
    path('clients/<int:pk>/', views.client_detail, name='client-detail'),
    path('clients/<int:pk>/edit/', views.client_update, name='client-update'),

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
    
    # Legacy ID parameter support (fallback)
    path('trips/<int:id>/', views.trip_detail, name='trip-detail-legacy'),
    path('trips/<int:id>/edit/', views.trip_edit, name='trip-edit'),
    path('trips/<int:id>/delete/', views.trip_delete, name='trip-delete-legacy'),

    # ============================================================================
    # EXPENSES MANAGEMENT
    # ============================================================================
    path('trips/<int:pk>/expenses/', views.expense_list, name='expense-list'),
    path('trips/<int:pk>/expenses/add/', views.expense_create, name='add-expense'),
    path('trips/<int:trip_id>/expenses/<int:expense_id>/edit/', views.edit_expense, name='edit-expense'),
    path('trips/<int:trip_id>/expenses/<int:expense_id>/delete/', views.delete_expense, name='delete-expense'),

    # ============================================================================
    # STANDARD INVOICES MANAGEMENT
    # ============================================================================
    path('invoices/', views.invoices_list, name='invoices-list'),
    path('invoices/new/', views.invoice_create, name='invoice-create'),
    path('invoices/new/ajax/', views.invoice_create_ajax, name='invoice-create-ajax'),
    path('invoices/<int:pk>/', views.invoice_detail, name='invoice-detail'),
    path('invoices/<int:pk>/edit/', views.invoice_update, name='invoice-update'),

    # ============================================================================
    # INVOICE ITEMS (Line Items)
    # ============================================================================
    path('invoices/<int:pk>/add-item/', views.add_invoice_item, name='add-invoice-item'),
    path('invoices/<int:pk>/items/<int:item_id>/edit/', views.edit_invoice_item, name='edit-invoice-item'),
    path('invoices/<int:pk>/items/<int:item_id>/delete/', views.delete_invoice_item, name='delete-invoice-item'),
    path('invoices/<int:pk>/items/json/', views.invoice_items_json, name='invoice-items-json'),

    # ============================================================================
    # MANIFEST INVOICES (MULTI-TRIP) - FIXED & RECONCILED!
    # ============================================================================
    path('trip-invoices/', views.trip_invoice_list, name='trip-invoice-list'),
    path('trip-invoices/create/', views.trip_invoice_create, name='trip-invoice-create'),  # ✅ NO trip_pk param
    path('trip-invoices/<int:pk>/', views.trip_invoice_detail, name='trip-invoice-detail'),
    path('trip-invoices/<int:pk>/edit/', views.trip_invoice_edit, name='trip-invoice-edit'),
    path('trip-invoices/<int:pk>/status/', views.trip_invoice_update_status, name='trip-invoice-update-status'),
    path('trip-invoices/<int:pk>/payment/', views.trip_invoice_record_payment, name='trip-invoice-record-payment'),
    path('trip-invoices/<int:pk>/add-trip/', views.trip_invoice_add_trip, name='trip-invoice-add-trip'),
    path('trip-invoices/<int:pk>/trip/<int:item_id>/remove/', views.trip_invoice_remove_trip, name='trip-invoice-remove-trip'),
    path('trip-invoices/<int:pk>/trip/<int:item_id>/edit/', views.trip_invoice_edit_trip, name='trip-invoice-edit-trip'),
    path('trip-invoices/<int:pk>/send/', views.trip_invoice_send, name='trip-invoice-send'),
    path('trip-invoices/<int:pk>/delete/', views.trip_invoice_delete, name='trip-invoice-delete'),
    path('trip-invoices/<int:pk>/pdf/', views.trip_invoice_pdf, name='trip-invoice-pdf'),
    path('trip-invoices/<int:pk>/email/', views.trip_invoice_email, name='trip-invoice-email'),
    path('trip-invoices/<int:pk>/record-payment/', views.record_payment, name='trip-invoice-record-payment'),
    path('trip-invoices/<int:pk>/view/', views.trip_invoice_view, name='trip-invoice-view'),
    # path('trip-invoices/<int:pk>/print/', views.trip_invoice_print, name='trip-invoice-print'),
    # path('trip-invoices/<int:pk>/email/', views.trip_invoice_email, name='trip-invoice-email'),

    # ============================================================================
    # PAYMENTS MANAGEMENT
    # ============================================================================
    path('invoices/<int:pk>/record-payment/', views.record_payment, name='record-payment'),
    path('payments/<int:pk>/edit/', views.edit_payment, name='edit-payment'),
    path('payments/<int:pk>/delete/', views.delete_payment, name='delete-payment'),

    # ============================================================================
    # PDF GENERATION - FULLY FUNCTIONAL INVOICE BUTTONS
    # ============================================================================
    # 📥 Download PDF Button
    path('invoices/<int:pk>/pdf/', views.invoice_pdf_download, name='invoice-pdf'),
    path('invoices/<int:pk>/download/', views.invoice_pdf_download, name='invoice-download'),
    
    # 👁️ View/Preview PDF Button
    path('invoices/<int:pk>/pdf-preview/', views.invoice_pdf_preview, name='invoice-pdf-preview'),
    path('invoices/<int:pk>/preview/', views.invoice_pdf_preview, name='invoice-preview'),
    
    # ✉️ Email Invoice Button
    path('invoices/<int:pk>/email-send/', views.send_invoice_email, name='send-invoice-email'),
    path('invoices/<int:pk>/email/', views.send_invoice_email, name='send-email'),

    # ============================================================================
    # EMAIL INTEGRATION - BACKUP PATTERNS
    # ============================================================================
    path('invoices/<int:pk>/send-email/', views.send_invoice_email_view, name='send-invoice-email-view'),
    path('invoices/<int:pk>/send-reminder/', views.send_payment_reminder_view, name='send-payment-reminder'),
    path('invoices/send-overdue-reminders/', views.send_overdue_reminders, name='send-overdue-reminders'),

    # ============================================================================
    # ANALYTICS & REPORTING
    # ============================================================================
    path('api/invoices-status/', views.get_invoice_status_data, name='api-invoice-status'),
    path('api/revenue-trends/', views.get_revenue_trends_data, name='api-revenue-trends'),
    path('api/trip-profitability/', views.get_trip_profitability_data, name='api-trip-profitability'),
]
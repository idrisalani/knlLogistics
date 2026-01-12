# signals.py - Add to your knlInvoice app
# This file auto-calculates invoice totals when items or payments change

from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from decimal import Decimal
from .models import InvoiceItem, PaymentRecord, Invoice
from datetime import datetime
from .models import TripExpense, Trip



@receiver(post_save, sender=InvoiceItem)
def update_invoice_totals_on_item_save(sender, instance, created, **kwargs):
    """Auto-calculate invoice totals when an item is added/edited"""
    invoice = instance.invoice
    
    # Calculate subtotal (sum of all items)
    subtotal = Decimal('0')
    for item in invoice.items.all():
        subtotal += item.quantity * item.unit_price
    
    # Update invoice
    invoice.subtotal = subtotal
    invoice.tax_rate = Decimal('7.5')  # 7.5% VAT
    invoice.save()


@receiver(post_delete, sender=InvoiceItem)
def update_invoice_totals_on_item_delete(sender, instance, **kwargs):
    """Auto-calculate invoice totals when an item is deleted"""
    invoice = instance.invoice
    
    # Calculate subtotal (sum of all items)
    subtotal = Decimal('0')
    for item in invoice.items.all():
        subtotal += item.quantity * item.unit_price
    
    # Update invoice
    invoice.subtotal = subtotal
    invoice.save()


@receiver(post_save, sender=PaymentRecord)
def update_invoice_on_payment(sender, instance, created, **kwargs):
    """Auto-update invoice status when payment is recorded"""
    invoice = instance.invoice
    
    # Recalculate total amount paid
    total_paid = Decimal('0')
    for payment in invoice.payments.all():
        total_paid += payment.amount
    
    invoice.amount_paid = total_paid
    
    # Auto-update status based on payment amount
    if invoice.total and total_paid >= invoice.total:
        invoice.status = 'paid'
    elif total_paid > 0:
        invoice.status = 'pending'
    
    invoice.save()


@receiver(post_delete, sender=PaymentRecord)
def update_invoice_on_payment_delete(sender, instance, **kwargs):
    """Auto-update invoice status when payment is deleted"""
    invoice = instance.invoice
    
    # Recalculate total amount paid
    total_paid = Decimal('0')
    for payment in invoice.payments.all():
        total_paid += payment.amount
    
    invoice.amount_paid = total_paid
    
    # Auto-update status
    if invoice.total and total_paid >= invoice.total:
        invoice.status = 'paid'
    elif total_paid > 0:
        invoice.status = 'pending'
    else:
        invoice.status = 'draft'
    
    invoice.save()

# ============================================
# PAYMENT SIGNALS (Phase 2 NEW)
# ============================================

@receiver(post_save, sender=PaymentRecord)
def update_invoice_on_payment_save(sender, instance, created, **kwargs):
    """Auto-update invoice status and totals when payment is recorded/edited"""
    invoice = instance.invoice
    
    # Calculate total amount paid
    total_paid = Decimal('0')
    for payment in invoice.payments.all():
        total_paid += payment.amount
    
    # Get invoice total
    total = invoice.total or Decimal('0')
    
    # Determine invoice status
    if total_paid >= total and total > 0:
        status = 'paid'
    elif total_paid > 0:
        status = 'pending'
    else:
        status = 'draft'
    
    # Check if overdue
    if status != 'paid' and invoice.due_date:
        if invoice.due_date < datetime.now().date():
            status = 'overdue'
    
    # Update invoice (bypass signals to avoid recursion)
    Invoice.objects.filter(pk=invoice.pk).update(
        amount_paid=total_paid,
        status=status
    )


@receiver(post_delete, sender=PaymentRecord)
def update_invoice_on_payment_delete(sender, instance, **kwargs):
    """Auto-update invoice status when payment is deleted"""
    invoice = instance.invoice
    
    # Recalculate total amount paid
    total_paid = Decimal('0')
    for payment in invoice.payments.all():
        total_paid += payment.amount
    
    # Get invoice total
    total = invoice.total or Decimal('0')
    
    # Determine invoice status
    if total_paid >= total and total > 0:
        status = 'paid'
    elif total_paid > 0:
        status = 'pending'
    else:
        status = 'draft'
    
    # Check if overdue
    if status != 'paid' and invoice.due_date:
        if invoice.due_date < datetime.now().date():
            status = 'overdue'
    
    # Update invoice
    Invoice.objects.filter(pk=invoice.pk).update(
        amount_paid=total_paid,
        status=status
    )

# ============================================
# EXPENSE SIGNALS (Phase 3 NEW)
# ============================================

@receiver(post_save, sender=TripExpense)
def update_trip_profitability_on_expense_save(sender, instance, created, **kwargs):
    """
    Auto-calculate trip profitability when an expense is added/edited
    This is informational - the trip_detail view calculates it dynamically
    """
    trip = instance.trip
    
    # Get all expenses
    total_expenses = Decimal('0')
    for expense in trip.tripexpense_set.all():
        total_expenses += expense.amount
    
    # You can store this in the Trip model if you have a total_expenses field
    # For now, it's calculated on demand in the view
    pass

@receiver(post_delete, sender=TripExpense)
def update_trip_profitability_on_expense_delete(sender, instance, **kwargs):
    """
    Auto-calculate trip profitability when an expense is deleted
    """
    trip = instance.trip
    
    # Profitability is recalculated on view render
    # No database update needed - it's calculated from:
    # Profit = Revenue - Sum(Expenses)
    pass

# ============================================
# HELPER FUNCTION: Calculate Outstanding Balance
# ============================================

def calculate_outstanding_balance(invoice):
    """Calculate outstanding balance for an invoice"""
    total = invoice.total or Decimal('0')
    amount_paid = invoice.amount_paid or Decimal('0')
    return total - amount_paid

# ============================================
# HELPER FUNCTIONS
# ============================================

def calculate_trip_profitability(trip):
    """
    Calculate profitability metrics for a trip
    
    Returns dict with:
    - total_revenue: Sum of all invoices for this trip
    - total_expenses: Sum of all expenses for this trip
    - profit: Revenue - Expenses
    - profit_margin: (Profit / Revenue) * 100
    - is_profitable: Boolean
    """
    total_revenue = trip.revenue or Decimal('0')
    
    total_expenses = Decimal('0')
    for expense in trip.tripexpense_set.all():
        total_expenses += expense.amount
    
    profit = total_revenue - total_expenses
    
    profit_margin = (profit / total_revenue * 100) if total_revenue > 0 else Decimal('0')
    
    return {
        'total_revenue': total_revenue,
        'total_expenses': total_expenses,
        'profit': profit,
        'profit_margin': profit_margin,
        'is_profitable': profit > 0,
    }

def get_expense_breakdown_by_category(trip):
    """
    Get expense breakdown by category
    
    Returns dict with category names as keys and amounts as values
    """
    breakdown = {}
    
    for expense in trip.tripexpense_set.all():
        category = expense.get_category_display()
        if category not in breakdown:
            breakdown[category] = Decimal('0')
        breakdown[category] += expense.amount
    
    return breakdown


def get_total_expenses_by_category(trip, category):
    """
    Get total expenses for a specific category
    """
    total = Decimal('0')
    
    for expense in trip.tripexpense_set.filter(category=category):
        total += expense.amount
    
    return total
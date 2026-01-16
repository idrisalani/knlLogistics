# signals.py - knlInvoice app signal handlers
# Auto-calculates invoice totals, payments, and trip profitability
#
# KEY FIX: All Decimal conversions are explicit to avoid:
# "unsupported operand type(s) for *: 'float' and 'decimal.Decimal'" error

from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from decimal import Decimal
from datetime import datetime
from .models import InvoiceItem, PaymentRecord, Invoice, TripExpense, Trip


# ============================================
# INVOICE ITEM SIGNALS
# ============================================

@receiver(post_save, sender=InvoiceItem)
def update_invoice_totals_on_item_save(sender, instance, created, **kwargs):
    """Auto-calculate invoice totals when an item is added/edited"""
    try:
        invoice = instance.invoice
        
        # Calculate subtotal using explicit Decimal conversion
        subtotal = Decimal('0')
        for item in invoice.items.all():
            qty = Decimal(str(item.quantity or 0))
            price = Decimal(str(item.unit_price or 0))
            subtotal += qty * price
        
        # Calculate tax using Decimal
        tax_rate = Decimal(str(invoice.tax_rate or 7.5)) / Decimal('100')
        tax_amount = subtotal * tax_rate
        
        # Calculate total
        total = subtotal + tax_amount
        
        # Update invoice with specific fields
        invoice.subtotal = subtotal
        invoice.tax_amount = tax_amount
        invoice.total = total
        invoice.save(update_fields=['subtotal', 'tax_amount', 'total'])
        
    except Exception as e:
        print(f"Error updating invoice totals on item save: {str(e)}")


@receiver(post_delete, sender=InvoiceItem)
def update_invoice_totals_on_item_delete(sender, instance, **kwargs):
    """Auto-calculate invoice totals when an item is deleted"""
    try:
        invoice = instance.invoice
        
        # Recalculate totals after item deletion
        subtotal = Decimal('0')
        for item in invoice.items.all():
            qty = Decimal(str(item.quantity or 0))
            price = Decimal(str(item.unit_price or 0))
            subtotal += qty * price
        
        # Calculate tax using Decimal
        tax_rate = Decimal(str(invoice.tax_rate or 7.5)) / Decimal('100')
        tax_amount = subtotal * tax_rate
        total = subtotal + tax_amount
        
        # Update invoice
        invoice.subtotal = subtotal
        invoice.tax_amount = tax_amount
        invoice.total = total
        invoice.save(update_fields=['subtotal', 'tax_amount', 'total'])
        
    except Exception as e:
        print(f"Error updating invoice totals on item delete: {str(e)}")


# ============================================
# PAYMENT RECORD SIGNALS
# ============================================

@receiver(post_save, sender=PaymentRecord)
def update_invoice_on_payment_save(sender, instance, created, **kwargs):
    """Auto-update invoice status and totals when payment is recorded/edited"""
    try:
        invoice = instance.invoice
        
        # Calculate total amount paid using Decimal
        total_paid = Decimal('0')
        for payment in invoice.payments.all():
            total_paid += Decimal(str(payment.amount or 0))
        
        # Get invoice total
        total = Decimal(str(invoice.total or 0))
        
        # Determine invoice status
        if total_paid >= total and total > 0:
            status = 'paid'
        elif total_paid > 0:
            status = 'pending'
        else:
            status = 'draft'
        
        # Check if overdue (only if not paid)
        if status != 'paid' and invoice.due_date:
            if invoice.due_date < datetime.now().date():
                status = 'overdue'
        
        # Update invoice using queryset to avoid signal recursion
        Invoice.objects.filter(pk=invoice.pk).update(
            amount_paid=total_paid,
            status=status
        )
        
    except Exception as e:
        print(f"Error updating invoice on payment save: {str(e)}")


@receiver(post_delete, sender=PaymentRecord)
def update_invoice_on_payment_delete(sender, instance, **kwargs):
    """Auto-update invoice status when payment is deleted"""
    try:
        invoice = instance.invoice
        
        # Recalculate total amount paid using Decimal
        total_paid = Decimal('0')
        for payment in invoice.payments.all():
            total_paid += Decimal(str(payment.amount or 0))
        
        # Get invoice total
        total = Decimal(str(invoice.total or 0))
        
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
        
    except Exception as e:
        print(f"Error updating invoice on payment delete: {str(e)}")


# ============================================
# TRIP EXPENSE SIGNALS
# ============================================

@receiver(post_save, sender=TripExpense)
def update_trip_profitability_on_expense_save(sender, instance, created, **kwargs):
    """
    Auto-calculate trip profitability when an expense is added/edited
    Note: Profitability is calculated on-demand in the view for consistency
    """
    try:
        trip = instance.trip
        # Profitability is calculated dynamically in trip_detail view
        # This signal is a hook for future enhancements (e.g., notifications)
    except Exception as e:
        print(f"Error handling expense save: {str(e)}")


@receiver(post_delete, sender=TripExpense)
def update_trip_profitability_on_expense_delete(sender, instance, **kwargs):
    """
    Auto-calculate trip profitability when an expense is deleted
    Note: Profitability is calculated on-demand in the view for consistency
    """
    try:
        trip = instance.trip
        # Profitability is recalculated on view render
        # No database update needed - it's calculated from: Profit = Revenue - Sum(Expenses)
    except Exception as e:
        print(f"Error handling expense delete: {str(e)}")


# ============================================
# HELPER FUNCTIONS
# ============================================

def calculate_outstanding_balance(invoice):
    """Calculate outstanding balance for an invoice"""
    total = Decimal(str(invoice.total or 0))
    amount_paid = Decimal(str(invoice.amount_paid or 0))
    return total - amount_paid


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
    try:
        total_revenue = Decimal(str(trip.revenue or 0))
        
        total_expenses = Decimal('0')
        for expense in trip.tripexpense_set.all():
            total_expenses += Decimal(str(expense.amount or 0))
        
        profit = total_revenue - total_expenses
        
        # Calculate margin safely
        profit_margin = (profit / total_revenue * 100) if total_revenue > 0 else Decimal('0')
        
        return {
            'total_revenue': total_revenue,
            'total_expenses': total_expenses,
            'profit': profit,
            'profit_margin': profit_margin,
            'is_profitable': profit > 0,
        }
    except Exception as e:
        print(f"Error calculating trip profitability: {str(e)}")
        return {
            'total_revenue': Decimal('0'),
            'total_expenses': Decimal('0'),
            'profit': Decimal('0'),
            'profit_margin': Decimal('0'),
            'is_profitable': False,
        }


def get_expense_breakdown_by_category(trip):
    """
    Get expense breakdown by category
    
    Returns dict with category names as keys and Decimal amounts as values
    """
    try:
        breakdown = {}
        
        for expense in trip.tripexpense_set.all():
            category = expense.get_category_display()
            if category not in breakdown:
                breakdown[category] = Decimal('0')
            breakdown[category] += Decimal(str(expense.amount or 0))
        
        return breakdown
    except Exception as e:
        print(f"Error getting expense breakdown: {str(e)}")
        return {}


def get_total_expenses_by_category(trip, category):
    """
    Get total expenses for a specific category
    
    Returns Decimal amount
    """
    try:
        total = Decimal('0')
        
        for expense in trip.tripexpense_set.filter(category=category):
            total += Decimal(str(expense.amount or 0))
        
        return total
    except Exception as e:
        print(f"Error getting expenses by category: {str(e)}")
        return Decimal('0')
# EMAIL SERVICE - Core email sending functionality (Phase 5)

from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings
from django.core.files.base import ContentFile
from io import BytesIO
from decimal import Decimal
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

try:
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib import colors
    HAS_REPORTLAB = True
except ImportError:
    HAS_REPORTLAB = False
    logger.warning("ReportLab not installed. PDF generation will not work. Install: pip install reportlab")


# ============================================
# INVOICE EMAIL SERVICE
# ============================================

def send_invoice_email(invoice, recipient_email=None):
    """
    Send invoice via email with PDF attachment
    
    Args:
        invoice: Invoice object
        recipient_email: Email address (defaults to client email)
    
    Returns:
        bool: True if email sent successfully
    """
    try:
        # Use provided email or client email
        to_email = recipient_email or invoice.client.emailAddress
        
        if not to_email:
            logger.error(f"No email address for invoice {invoice.id}")
            return False
        
        # Prepare context for template
        context = {
            'invoice': invoice,
            'client': invoice.client,
            'company_name': settings.COMPANY_NAME or 'Kamrate Nigeria Limited',
            'company_email': settings.DEFAULT_FROM_EMAIL,
            'company_phone': getattr(settings, 'COMPANY_PHONE', ''),
            'company_address': getattr(settings, 'COMPANY_ADDRESS', ''),
            'invoice_url': f"{settings.SITE_URL}/invoices/{invoice.id}/" if hasattr(settings, 'SITE_URL') else '',
        }
        
        # Render HTML template
        html_content = render_to_string('knlInvoice/emails/invoice_email.html', context)
        
        # Create email
        subject = f"Invoice #{invoice.invoice_number or invoice.id} from {settings.COMPANY_NAME or 'Kamrate'}"
        
        email = EmailMultiAlternatives(
            subject=subject,
            body=f"Invoice {invoice.invoice_number or invoice.id} is attached.",
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[to_email]
        )
        
        # Attach HTML version
        email.attach_alternative(html_content, "text/html")
        
        # Generate and attach PDF
        try:
            pdf_content = generate_invoice_pdf(invoice)
            if pdf_content:
                email.attach(
                    f'Invoice_{invoice.invoice_number or invoice.id}.pdf',
                    pdf_content,
                    'application/pdf'
                )
        except Exception as e:
            logger.error(f"Error generating PDF for invoice {invoice.id}: {str(e)}")
        
        # Send email
        email.send(fail_silently=False)
        
        # Log email sent
        logger.info(f"Invoice email sent to {to_email} for invoice {invoice.id}")
        
        return True
        
    except Exception as e:
        logger.error(f"Error sending invoice email: {str(e)}")
        return False


def send_payment_reminder_email(invoice, recipient_email=None):
    """
    Send payment reminder email
    
    Args:
        invoice: Invoice object
        recipient_email: Email address (defaults to client email)
    
    Returns:
        bool: True if email sent successfully
    """
    try:
        # Use provided email or client email
        to_email = recipient_email or invoice.client.emailAddress
        
        if not to_email:
            logger.error(f"No email address for invoice {invoice.id}")
            return False
        
        # Calculate days overdue
        from django.utils import timezone
        today = timezone.now().date()
        days_overdue = (today - invoice.due_date).days if invoice.due_date else 0
        
        # Prepare context
        context = {
            'invoice': invoice,
            'client': invoice.client,
            'company_name': settings.COMPANY_NAME or 'Kamrate Nigeria Limited',
            'company_email': settings.DEFAULT_FROM_EMAIL,
            'company_phone': getattr(settings, 'COMPANY_PHONE', ''),
            'days_overdue': max(0, days_overdue),
            'outstanding_amount': invoice.total - (invoice.amount_paid or Decimal('0')),
            'invoice_url': f"{settings.SITE_URL}/invoices/{invoice.id}/" if hasattr(settings, 'SITE_URL') else '',
        }
        
        # Render HTML template
        html_content = render_to_string('knlInvoice/emails/payment_reminder_email.html', context)
        
        # Create email
        subject = f"Payment Reminder: Invoice #{invoice.invoice_number or invoice.id} is Due"
        
        email = EmailMultiAlternatives(
            subject=subject,
            body=f"This is a friendly reminder about invoice {invoice.invoice_number or invoice.id}.",
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[to_email]
        )
        
        # Attach HTML version
        email.attach_alternative(html_content, "text/html")
        
        # Send email
        email.send(fail_silently=False)
        
        logger.info(f"Payment reminder email sent to {to_email} for invoice {invoice.id}")
        
        return True
        
    except Exception as e:
        logger.error(f"Error sending payment reminder email: {str(e)}")
        return False


def send_welcome_email(user, email_address):
    """
    Send welcome email to new user
    
    Args:
        user: User object
        email_address: Email address to send to
    
    Returns:
        bool: True if email sent successfully
    """
    try:
        context = {
            'user': user,
            'first_name': user.first_name or user.username,
            'company_name': settings.COMPANY_NAME or 'Kamrate Nigeria Limited',
            'login_url': f"{settings.SITE_URL}/login/" if hasattr(settings, 'SITE_URL') else '',
            'support_email': getattr(settings, 'SUPPORT_EMAIL', settings.DEFAULT_FROM_EMAIL),
        }
        
        # Render HTML template
        html_content = render_to_string('knlInvoice/emails/welcome_email.html', context)
        
        subject = f"Welcome to {settings.COMPANY_NAME or 'Kamrate'}!"
        
        email = EmailMultiAlternatives(
            subject=subject,
            body="Welcome to our platform! Get started by logging in.",
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[email_address]
        )
        
        email.attach_alternative(html_content, "text/html")
        email.send(fail_silently=False)
        
        logger.info(f"Welcome email sent to {email_address}")
        
        return True
        
    except Exception as e:
        logger.error(f"Error sending welcome email: {str(e)}")
        return False


def send_admin_notification(subject, message, recipient_emails=None):
    """
    Send notification to admin
    
    Args:
        subject: Email subject
        message: Email message (HTML)
        recipient_emails: List of emails (defaults to ADMINS)
    
    Returns:
        bool: True if email sent successfully
    """
    try:
        if not recipient_emails:
            # Get admin emails from settings
            recipient_emails = [email for name, email in settings.ADMINS]
        
        if not recipient_emails:
            logger.warning("No admin emails configured")
            return False
        
        email = EmailMultiAlternatives(
            subject=f"[{settings.COMPANY_NAME or 'Kamrate'}] {subject}",
            body=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=recipient_emails
        )
        
        email.attach_alternative(message, "text/html")
        email.send(fail_silently=False)
        
        logger.info(f"Admin notification sent to {recipient_emails}")
        
        return True
        
    except Exception as e:
        logger.error(f"Error sending admin notification: {str(e)}")
        return False


# ============================================
# PDF GENERATION
# ============================================

def generate_invoice_pdf(invoice):
    """
    Generate invoice PDF
    
    Args:
        invoice: Invoice object
    
    Returns:
        bytes: PDF content or None if generation fails
    """
    if not HAS_REPORTLAB:
        logger.warning("ReportLab not installed, returning None for PDF")
        return None
    
    try:
        # Create PDF buffer
        pdf_buffer = BytesIO()
        doc = SimpleDocTemplate(
            pdf_buffer,
            pagesize=letter,
            rightMargin=72,
            leftMargin=72,
            topMargin=72,
            bottomMargin=18,
        )
        
        # Container for the 'Flowable' objects
        elements = []
        
        # Define styles
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#001F4D'),
            spaceAfter=30,
        )
        
        # Title
        elements.append(Paragraph(f"Invoice #{invoice.invoice_number or invoice.id}", title_style))
        elements.append(Spacer(1, 0.2*inch))
        
        # Company info
        company_info = f"""
        <b>{settings.COMPANY_NAME or 'Kamrate Nigeria Limited'}</b><br/>
        Email: {settings.DEFAULT_FROM_EMAIL}<br/>
        {getattr(settings, 'COMPANY_PHONE', '')}<br/>
        {getattr(settings, 'COMPANY_ADDRESS', '')}
        """
        elements.append(Paragraph(company_info, styles['Normal']))
        elements.append(Spacer(1, 0.3*inch))
        
        # Invoice details
        details = f"""
        <b>Invoice #:</b> {invoice.invoice_number or invoice.id}<br/>
        <b>Date:</b> {invoice.date_created.strftime('%d %B %Y')}<br/>
        <b>Due Date:</b> {invoice.due_date.strftime('%d %B %Y') if invoice.due_date else 'Not specified'}<br/>
        <b>Client:</b> {invoice.client.clientName}<br/>
        <b>Email:</b> {invoice.client.emailAddress}
        """
        elements.append(Paragraph(details, styles['Normal']))
        elements.append(Spacer(1, 0.3*inch))
        
        # Items table
        data = [['Description', 'Amount']]
        
        # Add items if they exist
        if hasattr(invoice, 'items'):
            for item in invoice.items.all():
                data.append([item.description, f"₦{item.amount:,.2f}"])
        
        # Add total
        data.append(['<b>Total</b>', f"<b>₦{invoice.total:,.2f}</b>"])
        
        table = Table(data, colWidths=[3*inch, 1.5*inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#001F4D')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#f0f0f0')),
            ('GRID', (0, 0), (-1, -1), 1, colors.grey),
        ]))
        
        elements.append(table)
        elements.append(Spacer(1, 0.3*inch))
        
        # Payment info
        payment_info = f"""
        <b>Payment Status:</b> {invoice.status or 'Pending'}<br/>
        <b>Amount Paid:</b> ₦{invoice.amount_paid or 0:,.2f}<br/>
        <b>Outstanding:</b> ₦{invoice.total - (invoice.amount_paid or 0):,.2f}
        """
        elements.append(Paragraph(payment_info, styles['Normal']))
        
        # Build PDF
        doc.build(elements)
        
        # Get PDF content
        pdf_buffer.seek(0)
        return pdf_buffer.read()
        
    except Exception as e:
        logger.error(f"Error generating PDF: {str(e)}")
        return None


# ============================================
# ASYNC EMAIL TASKS (Optional - using threading)
# ============================================

def send_invoice_email_async(invoice_id):
    """
    Send invoice email asynchronously using threading
    (Alternative: Use Celery for production)
    
    Args:
        invoice_id: Invoice ID to send
    """
    import threading
    from .models import Invoice
    
    def send_email():
        try:
            invoice = Invoice.objects.get(id=invoice_id)
            send_invoice_email(invoice)
        except Exception as e:
            logger.error(f"Error in async invoice email: {str(e)}")
    
    thread = threading.Thread(target=send_email)
    thread.daemon = True
    thread.start()


def send_payment_reminder_async(invoice_id):
    """
    Send payment reminder asynchronously using threading
    
    Args:
        invoice_id: Invoice ID to send reminder for
    """
    import threading
    from .models import Invoice
    
    def send_email():
        try:
            invoice = Invoice.objects.get(id=invoice_id)
            send_payment_reminder_email(invoice)
        except Exception as e:
            logger.error(f"Error in async payment reminder: {str(e)}")
    
    thread = threading.Thread(target=send_email)
    thread.daemon = True
    thread.start()
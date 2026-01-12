from django.apps import AppConfig

class KnlinvoiceConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'knlInvoice'

    def ready(self):
        import knlInvoice.signals
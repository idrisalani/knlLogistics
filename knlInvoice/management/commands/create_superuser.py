"""
Django management command to create superuser automatically.

Location: knlInvoice/management/commands/create_superuser.py

Usage: python manage.py create_superuser

This command is called during Render deployment to create an initial admin user.
It checks if a superuser exists, and creates one if needed.

Features:
- Uses environment variable for password (production safe)
- Idempotent (won't create if already exists)
- Provides clear feedback

Environment Variable:
- SUPERUSER_PASSWORD (optional) - If not set, uses default password

"""

from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
import os


class Command(BaseCommand):
    help = 'Creates a superuser if one does not exist'

    def handle(self, *args, **kwargs):
        """
        Create superuser if it doesn't exist.
        
        Checks if 'admin' user exists, and creates it with:
        - Username: admin
        - Email: admin@kamrate.com
        - Password: From SUPERUSER_PASSWORD env var, or default
        """
        
        # Check if admin user already exists
        if not User.objects.filter(username='admin').exists():
            
            # Get password from environment variable or use default
            password = os.getenv(
                'SUPERUSER_PASSWORD',
                'Kamrate@2026!Admin'  # Default password
            )
            
            # Create the superuser
            try:
                User.objects.create_superuser(
                    username='admin',
                    email='admin@kamrate.com',
                    password='limited1'
                )
                
                self.stdout.write(
                    self.style.SUCCESS('✅ Superuser created successfully!')
                )
                self.stdout.write('Username: admin')
                self.stdout.write('Email: admin@kamrate.com')
                self.stdout.write(
                    'Password: Set from SUPERUSER_PASSWORD environment variable'
                )
                
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'❌ Error creating superuser: {str(e)}')
                )
        else:
            # Superuser already exists
            self.stdout.write(
                self.style.WARNING('⚠️ Superuser already exists. Skipping creation.')
            )
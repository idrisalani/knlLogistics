#!/usr/bin/env python
import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'knlLogistics.settings')
django.setup()

from knlInvoice.models import Product

products = [
    {"title": "Container Transport (20FT)", "description": "20FT container haulage", "price": 1450000, "quantity": 1},
    {"title": "Container Transport (40FT)", "description": "40FT container haulage", "price": 2900000, "quantity": 1},
    {"title": "Engine", "description": "Complete engine assembly", "price": 350000, "quantity": 1},
    {"title": "Turbo Charger", "description": "Turbocharger unit", "price": 180000, "quantity": 1},
    {"title": "Radiator", "description": "Vehicle radiator", "price": 75000, "quantity": 1},
    {"title": "Spring", "description": "Vehicle spring", "price": 25000, "quantity": 1},
    {"title": "Brake Pad", "description": "Brake pad set", "price": 12000, "quantity": 1},
    {"title": "Engine Oil", "description": "Engine oil (20L)", "price": 15000, "quantity": 1},
    {"title": "Battery", "description": "Vehicle battery", "price": 35000, "quantity": 1},
    {"title": "Mechanic Workmanship", "description": "Mechanic labor per hour", "price": 25000, "quantity": 1},
    {"title": "GIT Insurance", "description": "Goods in Transit Insurance", "price": 75000, "quantity": 1},
    {"title": "Motor Policy Insurance", "description": "Motor vehicle insurance", "price": 125000, "quantity": 1},
    {"title": "Garage Monthly Payment", "description": "Monthly garage fee", "price": 150000, "quantity": 1},
]

print("\n" + "="*60)
print("🚀 LOADING PRODUCTS")
print("="*60 + "\n")

created_count = 0
for product_data in products:
    product, created = Product.objects.get_or_create(
        title=product_data['title'],
        defaults={
            'description': product_data.get('description', ''),
            'price': product_data.get('price', 0),
            'quantity': product_data.get('quantity', 1),
            'currency': 'R'
        }
    )
    if created:
        created_count += 1
        print(f"✅ {product.title} @ ₦{product.price:,.0f}")

print("\n" + "="*60)
print(f"✅ Created: {created_count} products")
print(f"✅ Total: {Product.objects.count()} products")
print("="*60 + "\n")
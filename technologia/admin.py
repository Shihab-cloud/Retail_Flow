

from django.contrib import admin
from .models import Product, Customer, Sale, Alert

admin.site.register(Product)
admin.site.register(Customer)
admin.site.register(Sale)
admin.site.register(Alert)


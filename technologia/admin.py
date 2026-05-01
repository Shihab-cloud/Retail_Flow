

from django.contrib import admin
from .models import Product, Customer, Sale, Alert, SystemAuditLog

admin.site.register(Product)
admin.site.register(Customer)
admin.site.register(Sale)
admin.site.register(Alert)
#admin.site.register(SystemAuditLog)


@admin.register(SystemAuditLog)
class SystemAuditLogAdmin(admin.ModelAdmin):
    list_display = ('timestamp', 'agent_name', 'action', 'status')
    list_filter = ('status', 'agent_name')
    search_fields = ('action',)
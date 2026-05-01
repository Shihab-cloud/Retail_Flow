from django.db import models


class Product(models.Model):
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=100)
    category = models.CharField(max_length=50)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    stock = models.IntegerField()
    threshold = models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'products'

    def __str__(self):
        return self.name


class Customer(models.Model):
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=100)
    email = models.CharField(max_length=100)
    phone = models.CharField(max_length=20)
    birthdate = models.DateField()
    address = models.TextField()
    password = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'customers'

    def __str__(self):
        return self.name


class Sale(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    quantity = models.IntegerField()
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'sales'

    def __str__(self):
        return f"{self.quantity} × {self.product.name} for {self.customer.name}"


class Alert(models.Model):
    # --- EXISTING INVENTORY FIELDS ---
    # Note: We need to add null=True, blank=True to 'product' so that 
    # fraud alerts don't crash the database looking for a physical item!
    product = models.ForeignKey(Product, on_delete=models.CASCADE, null=True, blank=True)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    # --- NEW FRAUD DETECTION FIELDS ---
    invoice = models.ForeignKey('Invoice', on_delete=models.CASCADE, null=True, blank=True)
    reason = models.CharField(max_length=255, null=True, blank=True)

    class Meta:
        db_table = 'alerts'

    def __str__(self):
        # A smart string representation to distinguish the alerts in your admin panel
        if self.invoice:
            return f"Fraud Alert: Invoice {self.invoice.id}"
        elif self.product:
            return f"Stock Alert: {self.product.name}"
        return "General Alert"

class Invoice(models.Model):
    supplier_name = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    date = models.DateField()

    class Meta:
        # This tells Django to name the table exactly 'invoices' in MySQL
        # so it perfectly matches the n8n query we just wrote!
        db_table = 'invoices' 

    def __str__(self):
        return f"{self.supplier_name} - ${self.amount}"

class Supplier(models.Model):
    name = models.CharField(max_length=255)
    email = models.EmailField()
    reliability_score = models.IntegerField(default=98) # e.g., 98 for 98%
    avg_delivery_days = models.IntegerField(default=2)

    def __str__(self):
        return self.name

class SystemAuditLog(models.Model):
    action = models.CharField(max_length=255)
    agent_name = models.CharField(max_length=100) # e.g., 'OCR Agent', 'Reorder Agent'
    timestamp = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=50) # e.g., 'Success', 'Flagged for Fraud'

    def __str__(self):
        return f"{self.timestamp} - {self.agent_name}: {self.action}"
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
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'alerts'

    def __str__(self):
        return f"Alert for {self.product.name}"

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
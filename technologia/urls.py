from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('customers/', views.customers, name='customers'),
    path('sales/', views.sales, name='sales'),
    path('alerts/', views.alerts, name='alerts'),
    path('categories/', views.categories, name='categories'),
    path('category/<str:category_name>/', views.category_products, name='category_products'),
    path('cart/', views.cart, name='cart'),
    path('cart/add/<int:product_id>/', views.add_to_cart, name='add_to_cart'),
    path('cart/remove/<int:product_id>/', views.remove_from_cart, name='remove_from_cart'),
    path('cart/update/', views.update_cart, name='update_cart'),
    path('purchase/cart/', views.purchase_cart, name='purchase_cart'),
    path('checkout/', views.checkout, name='checkout'),
    path('purchase/<int:product_id>/', views.purchase_product, name='purchase_product'),
    path('signup/', views.signup, name='signup'),
    path('login/', views.login, name='login'),
    path('logout/', views.logout, name='logout'),
    path('buy/<int:product_id>/', views.buy_product, name='buy_product'),
    path('admin-dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('admin-inventory/', views.admin_inventory, name='admin_inventory'),
    path('admin-suppliers/', views.admin_suppliers, name='admin_suppliers'),
    path('admin-accounting/', views.admin_accounting, name='admin_accounting'),
    path('admin-reports/', views.admin_reports, name='admin_reports'),
    path('admin-settings/', views.admin_settings, name='admin_settings'),
]

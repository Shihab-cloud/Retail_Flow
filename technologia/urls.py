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
]

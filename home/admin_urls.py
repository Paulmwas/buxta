# home/admin_urls.py
from django.urls import path
from django.contrib.auth.views import LogoutView
from . import admin_views



urlpatterns = [
    # Dashboard
    path('', admin_views.admin_dashboard, name='dashboard'),
    
    # Books management
    
    path('books/', admin_views.books_management, name='books'),
    
    # Book Status Operations
    path('books/<int:book_id>/toggle-status/', admin_views.toggle_book_status, name='toggle_book_status'),
    path('books/<int:book_id>/delete/', admin_views.delete_book, name='delete_book'),
    
    # API Endpoints
    path('api/books/<int:book_id>/', admin_views.book_api_detail, name='book_api_detail'),
    
    # Image Management
    path('books/<int:book_id>/images/', admin_views.book_images_list, name='book_images_list'),
    path('books/<int:book_id>/upload-images/', admin_views.upload_book_images, name='upload_book_images'),
    path('books/<int:book_id>/set-primary-image/<int:image_id>/', admin_views.set_primary_image, name='set_primary_image'),
    path('books/<int:book_id>/delete-image/<int:image_id>/', admin_views.delete_image, name='delete_image'),
    
    # Orders management
    path('orders/', admin_views.admin_orders, name='orders'),
    path('orders/<uuid:order_id>/', admin_views.admin_order_detail, name='order_detail'),
    
    # Customers management
    path('customers/', admin_views.admin_customers, name='customers'),
    
    # Authors management
    path('authors/', admin_views.admin_authors, name='authors'),
    path('authors/add/', admin_views.add_edit_author, name='author_add'),
    path('authors/<int:author_id>/edit/', admin_views.add_edit_author, name='author_edit'),
    path('authors/<int:author_id>/delete/', admin_views.delete_author, name='author_delete'),
    
    # Categories management
# Categories management
path('categories/', admin_views.admin_categories, name='categories'),
path('categories/<int:category_id>/toggle-status/', admin_views.toggle_category_status, name='toggle_category_status'),
path('categories/<int:category_id>/delete/', admin_views.delete_category, name='delete_category'),
    
    # Publishers management
    path('publishers/', admin_views.admin_publishers, name='publishers'),
    
    # Reviews management
path('reviews/', admin_views.admin_reviews, name='admin_reviews'),
path('reviews/bulk/', admin_views.bulk_review_actions, name='bulk_review_actions'),

    
    # Coupons management
    path('coupons/', admin_views.admin_coupons, name='coupons'),
    path('coupons/add/', admin_views.admin_coupons, name='coupon_add'),
    
    # API endpoints
    path('api/sales-data/', admin_views.admin_api_sales_data, name='api_sales_data'),

    # Publishers management
    path('publishers/', admin_views.admin_publishers, name='publishers'),
    path('publishers/add/', admin_views.admin_publishers, name='publisher_add'),
    path('publishers/<int:publisher_id>/edit/', admin_views.admin_publishers, name='publisher_edit'),
    path('publishers/<int:publisher_id>/delete/', admin_views.delete_publisher, name='publisher_delete'),
    # Auth
    path('logout/', LogoutView.as_view(next_page='/admin/login/'), name='logout'),
]
# home/admin_views.py
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.views.decorators.http import require_POST
from django.db.models import Q, Sum, Count, Avg, F
from django.http import JsonResponse
from django.utils import timezone
from datetime import datetime, timedelta
from decimal import Decimal

from .models import (
    Book, Author, Category, Publisher, Customer, Order, OrderItem,
    Review, Coupon, Cart, CartItem, OrderStatusHistory
)


@staff_member_required
def admin_dashboard(request):
    """Main admin dashboard with key metrics and recent activity."""
    
    # Calculate key metrics
    total_revenue = Order.objects.filter(
        status__in=['confirmed', 'processing', 'shipped', 'delivered']
    ).aggregate(total=Sum('total_amount'))['total'] or Decimal('0')
    
    total_orders = Order.objects.count()
    total_books = Book.objects.filter(is_active=True).count()
    active_customers = Customer.objects.count()
    pending_orders = Order.objects.filter(status='pending').count()
    pending_reviews = Review.objects.filter(is_approved=False).count()
    
    # Get recent orders
    recent_orders = Order.objects.select_related('customer__user').order_by('-created_at')[:10]
    
    # Get top selling books
    top_books = Book.objects.filter(is_active=True, is_bestseller=True)[:5]
    
    # Get low stock books
    low_stock_books = Book.objects.filter(
        is_active=True,
        stock_quantity__lte=F('low_stock_threshold')
    )[:10]
    
    context = {
        'total_revenue': total_revenue,
        'total_orders': total_orders,
        'total_books': total_books,
        'active_customers': active_customers,
        'pending_orders': pending_orders,
        'pending_reviews': pending_reviews,
        'recent_orders': recent_orders,
        'top_books': top_books,
        'low_stock_books': low_stock_books,
    }
    
    return render(request, 'dashboard/dashboard.html', context)


# home/admin_views.py - Add these imports at the top
import json
from django.forms.models import model_to_dict
from django.db import transaction

# Add these functions to your admin_views.py

# Add these views to your dashboard/views.py or appropriate file
# Assuming you have the necessary imports already, but I'll include them for completeness

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.admin.views.decorators import staff_member_required
from django.http import JsonResponse
from django.db.models import Count
from django.utils.text import slugify
from django.contrib import messages
from django.core.exceptions import ValidationError
from .models import Book, Category, Author, Publisher, BookImage  # Adjust import path as needed
import os

# admin_views.py
import os
from decimal import Decimal
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from django.http import JsonResponse
from django.db.models import F
from django.utils.text import slugify
from django.core.exceptions import ValidationError
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from .models import Book, Author, Category, Publisher, BookImage


@staff_member_required
def books_management(request):
    """
    Single view to handle all books management operations (list, add, edit, delete)
    """
    if request.method == 'POST':
        # Check if it's an AJAX request
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            try:
                action = request.POST.get('action')
                
                if action == 'add':
                    return handle_add_book(request)
                elif action == 'edit':
                    return handle_edit_book(request)
                else:
                    return JsonResponse({'success': False, 'message': 'Invalid action'})
                    
            except Exception as e:
                return JsonResponse({'success': False, 'message': f'An error occurred: {str(e)}'})

    # GET request - display the books management page
    books = Book.objects.select_related('publisher').prefetch_related(
        'authors', 'categories', 'images'
    ).order_by('-created_at')
    
    categories = Category.objects.filter(is_active=True).order_by('name')
    authors = Author.objects.order_by('first_name', 'last_name')
    publishers = Publisher.objects.order_by('name')
    
    # Calculate statistics
    active_books_count = books.filter(is_active=True).count()
    low_stock_count = books.filter(
        stock_quantity__lte=F('low_stock_threshold'), 
        stock_quantity__gt=0
    ).count()
    out_of_stock_count = books.filter(stock_quantity=0).count()

    context = {
        'books': books,
        'categories': categories,
        'authors': authors,
        'publishers': publishers,
        'active_books_count': active_books_count,
        'low_stock_count': low_stock_count,
        'out_of_stock_count': out_of_stock_count,
    }
    return render(request, 'dashboard/books_management.html', context)


def handle_add_book(request):
    """Handle adding a new book"""
    # Extract and validate form data
    title = request.POST.get('title', '').strip()
    subtitle = request.POST.get('subtitle', '').strip()
    isbn_10 = request.POST.get('isbn_10', '').strip()
    isbn_13 = request.POST.get('isbn_13', '').strip()
    description = request.POST.get('description', '').strip()
    authors = request.POST.getlist('authors')
    categories = request.POST.getlist('categories')
    publisher_id = request.POST.get('publisher', '')
    format_type = request.POST.get('format', 'paperback')
    condition = request.POST.get('condition', 'new')
    pages = request.POST.get('pages')
    language = request.POST.get('language', 'English')
    publication_date = request.POST.get('publication_date')
    price = request.POST.get('price')
    compare_at_price = request.POST.get('compare_at_price')
    stock_quantity = request.POST.get('stock_quantity', 0)
    low_stock_threshold = request.POST.get('low_stock_threshold', 5)
    is_active = request.POST.get('is_active') == 'on'
    is_featured = request.POST.get('is_featured') == 'on'
    is_bestseller = request.POST.get('is_bestseller') == 'on'
    is_new_arrival = request.POST.get('is_new_arrival') == 'on'

    # Validation
    if not title:
        return JsonResponse({'success': False, 'message': 'Title is required'})
    if not description:
        return JsonResponse({'success': False, 'message': 'Description is required'})
    if not authors:
        return JsonResponse({'success': False, 'message': 'At least one author is required'})
    if not categories:
        return JsonResponse({'success': False, 'message': 'At least one category is required'})
    if not price or Decimal(price) <= 0:
        return JsonResponse({'success': False, 'message': 'Valid price is required'})

    # Check for duplicates
    if Book.objects.filter(title__iexact=title).exists():
        return JsonResponse({'success': False, 'message': 'A book with this title already exists'})
    if isbn_13 and Book.objects.filter(isbn_13=isbn_13).exists():
        return JsonResponse({'success': False, 'message': 'ISBN-13 already exists'})

    # Create the book
    book = Book.objects.create(
        title=title,
        slug=slugify(title),
        subtitle=subtitle,
        isbn_10=isbn_10 or None,
        isbn_13=isbn_13 or None,
        description=description,
        format=format_type,
        condition=condition,
        pages=int(pages) if pages else None,
        language=language,
        publication_date=publication_date if publication_date else None,
        price=Decimal(price),
        compare_at_price=Decimal(compare_at_price) if compare_at_price else None,
        stock_quantity=int(stock_quantity),
        low_stock_threshold=int(low_stock_threshold),
        is_active=is_active,
        is_featured=is_featured,
        is_bestseller=is_bestseller,
        is_new_arrival=is_new_arrival
    )

    # Set relationships
    if publisher_id:
        book.publisher = get_object_or_404(Publisher, id=publisher_id)
        book.save()

    book.authors.set(Author.objects.filter(id__in=authors))
    book.categories.set(Category.objects.filter(id__in=categories))

    # Handle cover image
    if 'cover_image' in request.FILES:
        BookImage.objects.create(
            book=book,
            image=request.FILES['cover_image'],
            is_primary=True,
            alt_text=f"Cover for {title}"
        )

    return JsonResponse({'success': True, 'message': 'Book added successfully!'})


@staff_member_required
def toggle_book_status(request, book_id):
    """Toggle book active status"""
    if request.method == 'POST':
        book = get_object_or_404(Book, id=book_id)
        book.is_active = not book.is_active
        book.save()
        return JsonResponse({
            'status': 'success',
            'is_active': book.is_active,
            'message': f'Book {"activated" if book.is_active else "deactivated"} successfully'
        })
    return JsonResponse({'status': 'error', 'message': 'Invalid request'})


@staff_member_required
def delete_book(request, book_id):
    """Delete a book"""
    if request.method == 'POST':
        book = get_object_or_404(Book, id=book_id)
        
        # Delete associated images
        for image in book.images.all():
            if os.path.exists(image.image.path):
                os.remove(image.image.path)
        
        book.delete()
        return JsonResponse({
            'status': 'success',
            'message': 'Book deleted successfully'
        })
    return JsonResponse({'status': 'error', 'message': 'Invalid request'})


@staff_member_required
def book_api_detail(request, book_id):
    """API endpoint to fetch book details for editing"""
    book = get_object_or_404(Book, id=book_id)
    
    # Get primary image URL
    primary_image = book.images.filter(is_primary=True).first()
    cover_image_url = primary_image.image.url if primary_image else ''
    
    data = {
        'success': True,
        'book': {
            'id': book.id,
            'title': book.title,
            'subtitle': book.subtitle,
            'isbn_10': book.isbn_10,
            'isbn_13': book.isbn_13,
            'description': book.description,
            'publisher': book.publisher.id if book.publisher else '',
            'format': book.format,
            'condition': book.condition,
            'pages': book.pages,
            'language': book.language,
            'publication_date': book.publication_date.strftime('%Y-%m-%d') if book.publication_date else '',
            'price': str(book.price),
            'compare_at_price': str(book.compare_at_price) if book.compare_at_price else '',
            'stock_quantity': book.stock_quantity,
            'low_stock_threshold': book.low_stock_threshold,
            'is_active': book.is_active,
            'is_featured': book.is_featured,
            'is_bestseller': book.is_bestseller,
            'is_new_arrival': book.is_new_arrival,
            'authors': [author.id for author in book.authors.all()],
            'categories': [category.id for category in book.categories.all()],
            'cover_image': cover_image_url
        }
    }
    return JsonResponse(data)


@staff_member_required
def book_images_list(request, book_id):
    """API endpoint to fetch book images"""
    book = get_object_or_404(Book, id=book_id)
    images = book.images.all().order_by('-is_primary', 'order', 'created_at')
    
    data = {
        'success': True,
        'images': [{
            'id': img.id,
            'image_url': img.image.url,
            'alt_text': img.alt_text,
            'is_primary': img.is_primary
        } for img in images]
    }
    return JsonResponse(data)


@staff_member_required
def upload_book_images(request, book_id):
    """Upload additional images for a book"""
    if request.method == 'POST':
        book = get_object_or_404(Book, id=book_id)
        images = request.FILES.getlist('images')
        
        if not images:
            return JsonResponse({'success': False, 'message': 'No images provided'})
        
        uploaded_images = []
        for image_file in images:
            # Validate image
            if image_file.size > 5 * 1024 * 1024:  # 5MB limit
                return JsonResponse({'success': False, 'message': 'Image size must be less than 5MB'})
            
            img = BookImage.objects.create(
                book=book,
                image=image_file,
                alt_text=f"Image for {book.title}",
                is_primary=False  # Additional images are not primary by default
            )
            uploaded_images.append({
                'id': img.id,
                'image_url': img.image.url
            })
        
        return JsonResponse({
            'success': True, 
            'images': uploaded_images,
            'message': f'{len(uploaded_images)} image(s) uploaded successfully'
        })
    
    return JsonResponse({'success': False, 'message': 'Invalid request method'})


@staff_member_required
def set_primary_image(request, book_id, image_id):
    """Set an image as the primary book image"""
    if request.method == 'POST':
        book = get_object_or_404(Book, id=book_id)
        image = get_object_or_404(BookImage, id=image_id, book=book)
        
        # Remove primary status from all images
        book.images.update(is_primary=False)
        
        # Set this image as primary
        image.is_primary = True
        image.save()
        
        return JsonResponse({
            'success': True, 
            'message': 'Primary image updated successfully'
        })
    
    return JsonResponse({'success': False, 'message': 'Invalid request method'})


@staff_member_required
def delete_image(request, book_id, image_id):
    """Delete a book image"""
    if request.method == 'POST':
        book = get_object_or_404(Book, id=book_id)
        image = get_object_or_404(BookImage, id=image_id, book=book)
        
        # Don't allow deletion of primary image if it's the only one
        if image.is_primary and book.images.count() == 1:
            return JsonResponse({
                'success': False, 
                'message': 'Cannot delete the only image. Please upload a replacement first.'
            })
        
        # Delete the file from storage
        if os.path.exists(image.image.path):
            os.remove(image.image.path)
        
        # If deleting primary image, set another as primary
        if image.is_primary:
            next_image = book.images.exclude(id=image.id).first()
            if next_image:
                next_image.is_primary = True
                next_image.save()
        
        image.delete()
        
        return JsonResponse({
            'success': True, 
            'message': 'Image deleted successfully'
        })
    
    return JsonResponse({'success': False, 'message': 'Invalid request method'})


def handle_edit_book(request):
    """Handle editing an existing book"""
    book_id = request.POST.get('book_id')
    if not book_id:
        return JsonResponse({'success': False, 'message': 'Book ID is required'})

    book = get_object_or_404(Book, id=book_id)

    # Extract and validate form data (same as add)
    title = request.POST.get('title', '').strip()
    subtitle = request.POST.get('subtitle', '').strip()
    isbn_10 = request.POST.get('isbn_10', '').strip()
    isbn_13 = request.POST.get('isbn_13', '').strip()
    description = request.POST.get('description', '').strip()
    authors = request.POST.getlist('authors')
    categories = request.POST.getlist('categories')
    publisher_id = request.POST.get('publisher', '')
    format_type = request.POST.get('format', 'paperback')
    condition = request.POST.get('condition', 'new')
    pages = request.POST.get('pages')
    language = request.POST.get('language', 'English')
    publication_date = request.POST.get('publication_date')
    price = request.POST.get('price')
    compare_at_price = request.POST.get('compare_at_price')
    stock_quantity = request.POST.get('stock_quantity', 0)
    low_stock_threshold = request.POST.get('low_stock_threshold', 5)
    is_active = request.POST.get('is_active') == 'on'
    is_featured = request.POST.get('is_featured') == 'on'
    is_bestseller = request.POST.get('is_bestseller') == 'on'
    is_new_arrival = request.POST.get('is_new_arrival') == 'on'

    # Validation
    if not title:
        return JsonResponse({'success': False, 'message': 'Title is required'})
    if not description:
        return JsonResponse({'success': False, 'message': 'Description is required'})
    if not authors:
        return JsonResponse({'success': False, 'message': 'At least one author is required'})
    if not categories:
        return JsonResponse({'success': False, 'message': 'At least one category is required'})
    if not price or Decimal(price) <= 0:
        return JsonResponse({'success': False, 'message': 'Valid price is required'})

    # Check for duplicates
    if Book.objects.filter(title__iexact=title).exists():
        return JsonResponse({'success': False, 'message': 'A book with this title already exists'})
    if isbn_13 and Book.objects.filter(isbn_13=isbn_13).exists():
        return JsonResponse({'success': False, 'message': 'ISBN-13 already exists'})

    # Create the book
    book = Book.objects.create(
        title=title,
        slug=slugify(title),
        subtitle=subtitle,
        isbn_10=isbn_10 or None,
        isbn_13=isbn_13 or None,
        description=description,
        format=format_type,
        condition=condition,
        pages=int(pages) if pages else None,
        language=language,
        publication_date=publication_date if publication_date else None,
        price=Decimal(price),
        compare_at_price=Decimal(compare_at_price) if compare_at_price else None,
        stock_quantity=int(stock_quantity),
        low_stock_threshold=int(low_stock_threshold),
        is_active=is_active,
        is_featured=is_featured,
        is_bestseller=is_bestseller,
        is_new_arrival=is_new_arrival
    )

    # Set relationships
    if publisher_id:
        book.publisher = get_object_or_404(Publisher, id=publisher_id)
        book.save()

    book.authors.set(Author.objects.filter(id__in=authors))
    book.categories.set(Category.objects.filter(id__in=categories))

    # Handle cover image
    if 'cover_image' in request.FILES:
        BookImage.objects.create(
            book=book,
            image=request.FILES['cover_image'],
            is_primary=True,
            alt_text=f"Cover for {title}"
        )

    return JsonResponse({'success': True, 'message': 'Book added successfully!'})


def handle_edit_book(request):
    """Handle editing an existing book"""
    book_id = request.POST.get('book_id')
    if not book_id:
        return JsonResponse({'success': False, 'message': 'Book ID is required'})

    book = get_object_or_404(Book, id=book_id)

    # Extract and validate form data (same as add)
    title = request.POST.get('title', '').strip()
    subtitle = request.POST.get('subtitle', '').strip()
    isbn_10 = request.POST.get('isbn_10', '').strip()
    isbn_13 = request.POST.get('isbn_13', '').strip()
    description = request.POST.get('description', '').strip()
    authors = request.POST.getlist('authors')
    categories = request.POST.getlist('categories')
    publisher_id = request.POST.get('publisher', '')
    format_type = request.POST.get('format', 'paperback')
    condition = request.POST.get('condition', 'new')
    pages = request.POST.get('pages')
    language = request.POST.get('language', 'English')
    publication_date = request.POST.get('publication_date')
    price = request.POST.get('price')
    compare_at_price = request.POST.get('compare_at_price')
    stock_quantity = request.POST.get('stock_quantity', 0)
    low_stock_threshold = request.POST.get('low_stock_threshold', 5)
    is_active = request.POST.get('is_active') == 'on'
    is_featured = request.POST.get('is_featured') == 'on'
    is_bestseller = request.POST.get('is_bestseller') == 'on'
    is_new_arrival = request.POST.get('is_new_arrival') == 'on'

    # Validation
    if not title:
        return JsonResponse({'success': False, 'message': 'Title is required'})
    if not description:
        return JsonResponse({'success': False, 'message': 'Description is required'})
    if not authors:
        return JsonResponse({'success': False, 'message': 'At least one author is required'})
    if not categories:
        return JsonResponse({'success': False, 'message': 'At least one category is required'})
    if not price or Decimal(price) <= 0:
        return JsonResponse({'success': False, 'message': 'Valid price is required'})

    # Check for duplicates (excluding current book)
    if Book.objects.filter(title__iexact=title).exclude(id=book.id).exists():
        return JsonResponse({'success': False, 'message': 'A book with this title already exists'})
    if isbn_13 and Book.objects.filter(isbn_13=isbn_13).exclude(id=book.id).exists():
        return JsonResponse({'success': False, 'message': 'ISBN-13 already exists'})

    # Update the book
    book.title = title
    book.slug = slugify(title)
    book.subtitle = subtitle
    book.isbn_10 = isbn_10 or None
    book.isbn_13 = isbn_13 or None
    book.description = description
    book.format = format_type
    book.condition = condition
    book.pages = int(pages) if pages else None
    book.language = language
    book.publication_date = publication_date if publication_date else None
    book.price = Decimal(price)
    book.compare_at_price = Decimal(compare_at_price) if compare_at_price else None
    book.stock_quantity = int(stock_quantity)
    book.low_stock_threshold = int(low_stock_threshold)
    book.is_active = is_active
    book.is_featured = is_featured
    book.is_bestseller = is_bestseller
    book.is_new_arrival = is_new_arrival

    # Update relationships
    if publisher_id:
        book.publisher = get_object_or_404(Publisher, id=publisher_id)
    else:
        book.publisher = None

    book.authors.set(Author.objects.filter(id__in=authors))
    book.categories.set(Category.objects.filter(id__in=categories))
    book.save()

    # Handle cover image update
    if 'cover_image' in request.FILES:
        # Delete old primary image if exists
        old_primary = book.images.filter(is_primary=True).first()
        if old_primary:
            if os.path.exists(old_primary.image.path):
                os.remove(old_primary.image.path)
            old_primary.delete()
        # Create new primary image
        BookImage.objects.create(
            book=book,
            image=request.FILES['cover_image'],
            is_primary=True,
            alt_text=f"Cover for {title}"
        )

    return JsonResponse({'success': True, 'message': 'Book updated successfully!'})
@staff_member_required
def admin_orders(request):
    """Orders management page."""
    
    # Get filter parameters
    search = request.GET.get('search', '')
    status = request.GET.get('status', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    
    # Base queryset
    orders = Order.objects.select_related('customer__user').order_by('-created_at')
    
    # Apply filters
    if search:
        orders = orders.filter(
            Q(order_number__icontains=search) |
            Q(customer__user__first_name__icontains=search) |
            Q(customer__user__last_name__icontains=search) |
            Q(customer__user__email__icontains=search)
        )
    
    if status:
        orders = orders.filter(status=status)
    
    if date_from:
        orders = orders.filter(created_at__date__gte=date_from)
    
    if date_to:
        orders = orders.filter(created_at__date__lte=date_to)
    
    # Pagination
    paginator = Paginator(orders, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'order_statuses': Order.ORDER_STATUS_CHOICES,
        'current_filters': {
            'search': search,
            'status': status,
            'date_from': date_from,
            'date_to': date_to,
        }
    }
    
    return render(request, 'dashboard/orders_list.html', context)


@staff_member_required
def admin_order_detail(request, order_id):
    """Order detail and management page."""
    order = get_object_or_404(Order, id=order_id)
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'update_status':
            new_status = request.POST.get('status')
            notes = request.POST.get('notes', '')
            
            # Update order status
            order.status = new_status
            order.save()
            
            # Create status history entry
            OrderStatusHistory.objects.create(
                order=order,
                status=new_status,
                notes=notes,
                created_by=request.user
            )
            
            messages.success(request, f'Order status updated to {order.get_status_display()}')
            return redirect('order_detail', order_id=order.id)
    
    context = {
        'order': order,
        'order_items': order.items.select_related('book').all(),
        'status_history': order.status_history.select_related('created_by').all(),
        'order_statuses': Order.ORDER_STATUS_CHOICES,
    }
    
    return render(request, 'dashboard/orders_detail.html', context)


@staff_member_required
def admin_customers(request):
    """Customers management page."""
    
    search = request.GET.get('search', '')
    
    customers = Customer.objects.select_related('user')
    
    if search:
        customers = customers.filter(
            Q(user__first_name__icontains=search) |
            Q(user__last_name__icontains=search) |
            Q(user__email__icontains=search) |
            Q(phone__icontains=search)
        )
    
    # Add order statistics
    customers = customers.annotate(
        total_orders=Count('orders'),
        total_spent=Sum('orders__total_amount')
    )
    
    paginator = Paginator(customers, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'current_search': search,
    }
    
    return render(request, 'dashboard/customers_list.html', context)


@staff_member_required
def admin_authors(request):
    """Authors management page."""
    search = request.GET.get('search', '')
    
    authors = Author.objects.all().annotate(book_count=Count('books'))
    
    if search:
        authors = authors.filter(
            Q(first_name__icontains=search) |
            Q(last_name__icontains=search) |
            Q(bio__icontains=search)
        )
    
    # Statistics
    total_authors = authors.count()
    authors_with_books = authors.filter(book_count__gt=0).count()
    most_productive = authors.order_by('-book_count').first()
    authors_without_books = authors.filter(book_count=0).count()
    
    paginator = Paginator(authors, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'current_search': search,
        'total_authors': total_authors,
        'authors_with_books': authors_with_books,
        'most_productive': most_productive,
        'authors_without_books': authors_without_books,
    }
    
    return render(request, 'dashboard/authors_list.html', context)

@require_POST
@staff_member_required
def add_edit_author(request, author_id=None):
    """Add or edit an author"""
    try:
        if author_id:
            author = get_object_or_404(Author, id=author_id)
            action = 'edit'
        else:
            author = Author()
            action = 'add'
        
        # Update fields
        author.first_name = request.POST.get('first_name')
        author.last_name = request.POST.get('last_name')
        author.bio = request.POST.get('bio', '')
        author.website = request.POST.get('website', '')
        
        # Handle dates
        birth_date = request.POST.get('birth_date')
        death_date = request.POST.get('death_date')
        author.birth_date = birth_date if birth_date else None
        author.death_date = death_date if death_date else None
        
        # Handle photo upload
        if 'photo' in request.FILES:
            author.photo = request.FILES['photo']
        
        author.save()
        
        return JsonResponse({
            'status': 'success',
            'message': f'Author {action}ed successfully!'
        })
        
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': f'Error: {str(e)}'
        }, status=400)

@require_POST
@staff_member_required
def delete_author(request, author_id):
    """Delete an author"""
    try:
        author = get_object_or_404(Author, id=author_id)
        
        # Check if author has books
        if author.books.exists():
            return JsonResponse({
                'status': 'error',
                'message': 'Cannot delete author with associated books. Please remove books first.'
            }, status=400)
        
        author.delete()
        
        return JsonResponse({
            'status': 'success',
            'message': 'Author deleted successfully!'
        })
        
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': f'Error: {str(e)}'
        }, status=400)


from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.admin.views.decorators import staff_member_required
from django.http import JsonResponse
from django.contrib import messages
from django.db.models import Count
from django.utils.text import slugify
from .models import Category


@staff_member_required
def admin_categories(request):
    """Categories management page (list + add/edit via AJAX)."""
    if request.method == 'POST':
        # Check if it's an AJAX request
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            try:
                action = request.POST.get('action')
                
                if action == 'add':
                    name = request.POST.get('name', '').strip()
                    description = request.POST.get('description', '').strip()
                    is_active = request.POST.get('is_active') == 'on'

                    # Validation
                    if not name:
                        return JsonResponse({
                            'status': 'error',
                            'message': 'Category name is required'
                        })

                    # Check for duplicates
                    if Category.objects.filter(name__iexact=name).exists():
                        return JsonResponse({
                            'status': 'error',
                            'message': 'A category with this name already exists'
                        })

                    # Create category
                    category = Category.objects.create(
                        name=name,
                        slug=slugify(name),
                        description=description,
                        is_active=is_active
                    )
                    
                    return JsonResponse({
                        'status': 'success',
                        'message': 'Category added successfully!'
                    })
                    
                elif action == 'edit':
                    category_id = request.POST.get('category_id')
                    if not category_id:
                        return JsonResponse({
                            'status': 'error',
                            'message': 'Category ID is required'
                        })
                    
                    category = get_object_or_404(Category, id=category_id)
                    name = request.POST.get('name', '').strip()
                    description = request.POST.get('description', '').strip()
                    is_active = request.POST.get('is_active') == 'on'
                    
                    # Validation
                    if not name:
                        return JsonResponse({
                            'status': 'error',
                            'message': 'Category name is required'
                        })
                    
                    # Check for duplicates (excluding current category)
                    if Category.objects.filter(name__iexact=name).exclude(id=category_id).exists():
                        return JsonResponse({
                            'status': 'error',
                            'message': 'A category with this name already exists'
                        })
                    
                    # Update category
                    category.name = name
                    category.description = description
                    category.is_active = is_active
                    category.slug = slugify(name)
                    category.save()
                    
                    return JsonResponse({
                        'status': 'success',
                        'message': 'Category updated successfully!'
                    })
                
                return JsonResponse({
                    'status': 'error',
                    'message': 'Invalid action'
                })
                
            except Exception as e:
                return JsonResponse({
                    'status': 'error',
                    'message': f'An error occurred: {str(e)}'
                })

    # GET request - list categories
    categories = Category.objects.annotate(
        book_count=Count('books')
    ).order_by('name')
    
    return render(request, 'dashboard/categories_list.html', {
        'categories': categories
    })


@staff_member_required
def toggle_category_status(request, category_id):
    """Toggle category active status via AJAX."""
    if request.method == 'POST':
        category = get_object_or_404(Category, id=category_id)
        category.is_active = not category.is_active
        category.save()
        
        return JsonResponse({
            'status': 'success',
            'is_active': category.is_active,
            'message': f'Category {"activated" if category.is_active else "deactivated"} successfully'
        })
    
    return JsonResponse({
        'status': 'error',
        'message': 'Invalid request method'
    }, status=405)


@staff_member_required
def delete_category(request, category_id):
    """Delete a category via AJAX."""
    if request.method == 'POST':
        category = get_object_or_404(Category, id=category_id)
        
        # Check if category has books
        if category.books.exists():
            return JsonResponse({
                'status': 'error', 
                'message': 'Cannot delete category with associated books. Please reassign or remove books first.'
            })
        
        category_name = category.name
        category.delete()
        
        return JsonResponse({
            'status': 'success',
            'message': f'Category "{category_name}" deleted successfully'
        })
    
    return JsonResponse({
        'status': 'error',
        'message': 'Invalid request method'
    }, status=405)
# views.py
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, render
from django.contrib.admin.views.decorators import staff_member_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.utils.text import slugify
from .models import Publisher

@staff_member_required
def admin_publishers(request):
    """Publishers management page (list + add/edit)."""
    if request.method == 'POST':
        # Check if it's an AJAX request
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            try:
                action = request.POST.get('action')
                if action == 'add':
                    name = request.POST.get('name', '').strip()
                    address = request.POST.get('address', '').strip()
                    website = request.POST.get('website', '').strip()
                    email = request.POST.get('email', '').strip()
                    founded_year = request.POST.get('founded_year', '').strip()

                    # Validation
                    if not name:
                        return JsonResponse({
                            'success': False,
                            'message': 'Publisher name is required'
                        })

                    # Check for duplicates
                    if Publisher.objects.filter(name__iexact=name).exists():
                        return JsonResponse({
                            'success': False,
                            'message': 'A publisher with this name already exists'
                        })

                    # Validate email format if provided
                    if email:
                        from django.core.validators import validate_email
                        from django.core.exceptions import ValidationError
                        try:
                            validate_email(email)
                        except ValidationError:
                            return JsonResponse({
                                'success': False,
                                'message': 'Please enter a valid email address'
                            })

                    # Validate website URL if provided
                    if website and not website.startswith(('http://', 'https://')):
                        website = 'https://' + website

                    # Validate founded year if provided
                    if founded_year:
                        try:
                            founded_year = int(founded_year)
                            if founded_year < 1000 or founded_year > 2024:
                                return JsonResponse({
                                    'success': False,
                                    'message': 'Please enter a valid founding year (1000-2024)'
                                })
                        except ValueError:
                            return JsonResponse({
                                'success': False,
                                'message': 'Please enter a valid year for founding date'
                            })

                    # Create publisher
                    publisher = Publisher.objects.create(
                        name=name,
                        address=address,
                        website=website,
                        email=email,
                        founded_year=founded_year if founded_year else None
                    )
                    
                    return JsonResponse({
                        'success': True,
                        'message': 'Publisher added successfully!'
                    })
                    
                elif action == 'edit':
                    publisher_id = request.POST.get('publisher_id')
                    if not publisher_id:
                        return JsonResponse({
                            'success': False,
                            'message': 'Publisher ID is required'
                        })
                    
                    publisher = get_object_or_404(Publisher, id=publisher_id)
                    name = request.POST.get('name', '').strip()
                    address = request.POST.get('address', '').strip()
                    website = request.POST.get('website', '').strip()
                    email = request.POST.get('email', '').strip()
                    founded_year = request.POST.get('founded_year', '').strip()
                    
                    # Validation
                    if not name:
                        return JsonResponse({
                            'success': False,
                            'message': 'Publisher name is required'
                        })
                    
                    # Check for duplicates (excluding current publisher)
                    if Publisher.objects.filter(name__iexact=name).exclude(id=publisher_id).exists():
                        return JsonResponse({
                            'success': False,
                            'message': 'A publisher with this name already exists'
                        })
                    
                    # Validate email format if provided
                    if email:
                        from django.core.validators import validate_email
                        from django.core.exceptions import ValidationError
                        try:
                            validate_email(email)
                        except ValidationError:
                            return JsonResponse({
                                'success': False,
                                'message': 'Please enter a valid email address'
                            })

                    # Validate website URL if provided
                    if website and not website.startswith(('http://', 'https://')):
                        website = 'https://' + website

                    # Validate founded year if provided
                    if founded_year:
                        try:
                            founded_year = int(founded_year)
                            if founded_year < 1000 or founded_year > 2024:
                                return JsonResponse({
                                    'success': False,
                                    'message': 'Please enter a valid founding year (1000-2024)'
                                })
                        except ValueError:
                            return JsonResponse({
                                'success': False,
                                'message': 'Please enter a valid year for founding date'
                            })

                    # Update publisher
                    publisher.name = name
                    publisher.address = address
                    publisher.website = website
                    publisher.email = email
                    publisher.founded_year = founded_year if founded_year else None
                    publisher.save()
                    
                    return JsonResponse({
                        'success': True,
                        'message': 'Publisher updated successfully!'
                    })
                
                return JsonResponse({
                    'success': False,
                    'message': 'Invalid action'
                })
                
            except Exception as e:
                return JsonResponse({
                    'success': False,
                    'message': f'An error occurred: {str(e)}'
                })
        
        # Non-AJAX POST request (fallback)
        action = request.POST.get('action')
        if action == 'add':
            name = request.POST.get('name')
            address = request.POST.get('address', '')
            website = request.POST.get('website', '')
            email = request.POST.get('email', '')
            founded_year = request.POST.get('founded_year')

            Publisher.objects.create(
                name=name,
                address=address,
                website=website,
                email=email,
                founded_year=founded_year if founded_year else None
            )
            messages.success(request, 'Publisher added successfully!')
            return redirect('publishers')
            
        elif action == 'edit':
            publisher_id = request.POST.get('publisher_id')
            publisher = get_object_or_404(Publisher, id=publisher_id)
            publisher.name = request.POST.get('name')
            publisher.address = request.POST.get('address', '')
            publisher.website = request.POST.get('website', '')
            publisher.email = request.POST.get('email', '')
            publisher.founded_year = request.POST.get('founded_year') if request.POST.get('founded_year') else None
            publisher.save()
            messages.success(request, 'Publisher updated successfully!')
            return redirect('publishers')

    # GET request - list publishers
    search = request.GET.get('search', '')
    
    publishers = Publisher.objects.annotate(
        book_count=Count('book')
    ).order_by('name')
    
    if search:
        publishers = publishers.filter(
            Q(name__icontains=search) |
            Q(address__icontains=search) |
            Q(email__icontains=search)
        )
    
    # Statistics
    total_publishers = publishers.count()
    publishers_with_books = publishers.filter(book_count__gt=0).count()
    most_productive = publishers.order_by('-book_count').first()
    publishers_without_books = publishers.filter(book_count=0).count()
    
    context = {
        'publishers': publishers,
        'current_search': search,
        'total_publishers': total_publishers,
        'publishers_with_books': publishers_with_books,
        'most_productive': most_productive,
        'publishers_without_books': publishers_without_books,
    }
    
    return render(request, 'dashboard/publishers_list.html', context)

@require_POST
@staff_member_required
def delete_publisher(request, publisher_id):
    """Delete a publisher."""
    try:
        publisher = get_object_or_404(Publisher, id=publisher_id)
        
        # Check if publisher has books
        if publisher.book_set.exists():
            return JsonResponse({
                'status': 'error', 
                'message': 'Cannot delete publisher with associated books. Please reassign or delete books first.'
            })
            
        publisher.delete()
        return JsonResponse({
            'status': 'success',
            'message': 'Publisher deleted successfully'
        })
    
    except Exception as e:
        return JsonResponse({
            'status': 'error', 
            'message': f'An error occurred: {str(e)}'
        })


@staff_member_required
def admin_reviews(request):
    """Reviews management page (list + approve/reject/delete)."""
    if request.method == 'POST':
        # Check if it's an AJAX request
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            try:
                action = request.POST.get('action')
                review_id = request.POST.get('review_id')
                
                if not review_id:
                    return JsonResponse({
                        'success': False,
                        'message': 'Review ID is required'
                    })
                
                review = get_object_or_404(Review, id=review_id)
                
                if action == 'approve':
                    review.is_approved = True
                    review.save()
                    
                    return JsonResponse({
                        'success': True,
                        'message': 'Review approved successfully!'
                    })
                    
                elif action == 'reject':
                    review.is_approved = False
                    review.save()
                    
                    return JsonResponse({
                        'success': True,
                        'message': 'Review rejected successfully!'
                    })
                    
                elif action == 'delete':
                    review.delete()
                    
                    return JsonResponse({
                        'success': True,
                        'message': 'Review deleted successfully!'
                    })
                    
                elif action == 'toggle_verified':
                    review.is_verified_purchase = not review.is_verified_purchase
                    review.save()
                    
                    return JsonResponse({
                        'success': True,
                        'is_verified': review.is_verified_purchase,
                        'message': f'Review {"marked as verified purchase" if review.is_verified_purchase else "marked as unverified"}'
                    })
                
                return JsonResponse({
                    'success': False,
                    'message': 'Invalid action'
                })
                
            except Exception as e:
                return JsonResponse({
                    'success': False,
                    'message': f'An error occurred: {str(e)}'
                })

    # GET request - list reviews with filters
    reviews = Review.objects.select_related('book', 'customer__user').all()
    
    # Filter by status
    status_filter = request.GET.get('status', 'all')
    if status_filter == 'pending':
        reviews = reviews.filter(is_approved=False)
    elif status_filter == 'approved':
        reviews = reviews.filter(is_approved=True)
    elif status_filter == 'verified':
        reviews = reviews.filter(is_verified_purchase=True)
    
    # Filter by rating
    rating_filter = request.GET.get('rating')
    if rating_filter:
        reviews = reviews.filter(rating=rating_filter)
    
    # Search functionality
    search_query = request.GET.get('search', '').strip()
    if search_query:
        reviews = reviews.filter(
            Q(title__icontains=search_query) |
            Q(content__icontains=search_query) |
            Q(book__title__icontains=search_query) |
            Q(customer__user__first_name__icontains=search_query) |
            Q(customer__user__last_name__icontains=search_query)
        )
    
    # Order reviews
    reviews = reviews.order_by('-created_at')
    
    # Calculate statistics
    total_reviews = Review.objects.count()
    pending_reviews = Review.objects.filter(is_approved=False).count()
    approved_reviews = Review.objects.filter(is_approved=True).count()
    verified_reviews = Review.objects.filter(is_verified_purchase=True).count()
    
    # Calculate average rating
    avg_rating = Review.objects.filter(is_approved=True).aggregate(
        avg_rating=Avg('rating')
    )['avg_rating'] or 0
    
    context = {
        'reviews': reviews,
        'total_reviews': total_reviews,
        'pending_reviews': pending_reviews,
        'approved_reviews': approved_reviews,
        'verified_reviews': verified_reviews,
        'avg_rating': round(avg_rating, 1),
        'status_filter': status_filter,
        'rating_filter': rating_filter,
        'search_query': search_query,
    }
    
    return render(request, 'dashboard/reviews_list.html', context)


@staff_member_required
def bulk_review_actions(request):
    """Handle bulk actions on reviews."""
    if request.method == 'POST' and request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        try:
            action = request.POST.get('action')
            review_ids = request.POST.getlist('review_ids[]')
            
            if not review_ids:
                return JsonResponse({
                    'success': False,
                    'message': 'No reviews selected'
                })
            
            reviews = Review.objects.filter(id__in=review_ids)
            
            if action == 'approve':
                reviews.update(is_approved=True)
                message = f'{reviews.count()} reviews approved successfully!'
                
            elif action == 'reject':
                reviews.update(is_approved=False)
                message = f'{reviews.count()} reviews rejected successfully!'
                
            elif action == 'delete':
                count = reviews.count()
                reviews.delete()
                message = f'{count} reviews deleted successfully!'
                
            else:
                return JsonResponse({
                    'success': False,
                    'message': 'Invalid action'
                })
            
            return JsonResponse({
                'success': True,
                'message': message
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'An error occurred: {str(e)}'
            })
    
    return JsonResponse({'success': False, 'message': 'Invalid request'})


@staff_member_required
def admin_coupons(request):
    """Coupons management page."""
    
    status = request.GET.get('status', '')
    
    coupons = Coupon.objects.all().order_by('-created_at')
    
    if status == 'active':
        coupons = coupons.filter(is_active=True)
    elif status == 'inactive':
        coupons = coupons.filter(is_active=False)
    elif status == 'expired':
        from django.utils import timezone
        coupons = coupons.filter(valid_until__lt=timezone.now())
    
    paginator = Paginator(coupons, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'current_status': status,
    }
    
    return render(request, 'dashboard/coupons/list.html', context)


@staff_member_required
def admin_api_sales_data(request):
    """API endpoint for sales chart data."""
    
    period = request.GET.get('period', '7')  # 7, 30, or 90 days
    days = int(period)
    
    end_date = timezone.now().date()
    start_date = end_date - timedelta(days=days)
    
    # Get daily sales data
    sales_data = []
    current_date = start_date
    
    while current_date <= end_date:
        daily_sales = Order.objects.filter(
            created_at__date=current_date,
            status__in=['confirmed', 'processing', 'shipped', 'delivered']
        ).aggregate(total=Sum('total_amount'))['total'] or 0
        
        sales_data.append({
            'date': current_date.strftime('%Y-%m-%d'),
            'sales': float(daily_sales)
        })
        
        current_date += timedelta(days=1)
    
    return JsonResponse({'sales_data': sales_data})


@staff_member_required
def admin_toggle_book_status(request, book_id):
    """Toggle book active status."""
    if request.method == 'POST':
        book = get_object_or_404(Book, id=book_id)
        book.is_active = not book.is_active
        book.save()
        
        return JsonResponse({
            'status': 'success',
            'is_active': book.is_active,
            'message': f'Book {"activated" if book.is_active else "deactivated"} successfully'
        })
    
    return JsonResponse({'status': 'error', 'message': 'Invalid request'})


@staff_member_required
def admin_approve_review(request, review_id):
    """Approve or reject a review."""
    if request.method == 'POST':
        review = get_object_or_404(Review, id=review_id)
        action = request.POST.get('action')
        
        if action == 'approve':
            review.is_approved = True
            review.save()
            message = 'Review approved successfully'
        elif action == 'reject':
            review.delete()
            message = 'Review rejected and deleted'
        else:
            return JsonResponse({'status': 'error', 'message': 'Invalid action'})
        
        return JsonResponse({'status': 'success', 'message': message})
    
    return JsonResponse({'status': 'error', 'message': 'Invalid request'})
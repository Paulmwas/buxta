from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib import messages
from .models import Book, Category, Cart, CartItem, Customer, Order, OrderItem, Address
from decimal import Decimal
from django.views.decorators.csrf import csrf_protect
import json

def home(request):
    """Homepage with trending books"""
    trending_books = Book.objects.filter(
        is_active=True,
        is_featured=True
    ).order_by('-created_at')[:8]
    
    context = {
        'trending_books': trending_books,
    }
    return render(request, 'home.html', context)


def shop(request):
    """Shop page with all books"""
    books = Book.objects.filter(is_active=True).order_by('-created_at')
    categories = Category.objects.filter(is_active=True, parent=None)
    
    # Filter by category if provided
    category_slug = request.GET.get('category')
    if category_slug:
        category = get_object_or_404(Category, slug=category_slug)
        books = books.filter(categories=category)
    
    # Search functionality
    search_query = request.GET.get('search')
    if search_query:
        books = books.filter(title__icontains=search_query)
    
    context = {
        'books': books,
        'categories': categories,
        'current_category': category_slug,
    }
    return render(request, 'shop.html', context)


def book_detail(request, slug):
    """Book detail page"""
    book = get_object_or_404(Book, slug=slug, is_active=True)
    related_books = Book.objects.filter(
        categories__in=book.categories.all(),
        is_active=True
    ).exclude(id=book.id).distinct()[:4]
    
    context = {
        'book': book,
        'related_books': related_books,
    }
    return render(request, 'book_detail.html', context)


def get_or_create_cart(request):
    """Get or create cart for user/session"""
    if request.user.is_authenticated:
        try:
            customer = Customer.objects.get(user=request.user)
        except Customer.DoesNotExist:
            # Create customer profile for the user
            customer = Customer.objects.create(user=request.user)
        cart, created = Cart.objects.get_or_create(customer=customer)
    else:
        session_key = request.session.session_key
        if not session_key:
            request.session.create()
            session_key = request.session.session_key
        cart, created = Cart.objects.get_or_create(session_key=session_key)
    return cart


@require_POST
def add_to_cart(request, book_id):
    """Add book to cart via AJAX"""
    book = get_object_or_404(Book, id=book_id, is_active=True)
    
    if not book.is_in_stock:
        return JsonResponse({
            'success': False,
            'message': 'This book is out of stock'
        })
    
    cart = get_or_create_cart(request)
    
    cart_item, created = CartItem.objects.get_or_create(
        cart=cart,
        book=book,
        defaults={'price': book.price}
    )
    
    if not created:
        if cart_item.quantity < book.stock_quantity:
            cart_item.quantity += 1
            cart_item.save()
        else:
            return JsonResponse({
                'success': False,
                'message': 'Maximum stock quantity reached'
            })
    
    return JsonResponse({
        'success': True,
        'message': 'Book added to cart',
        'cart_count': cart.total_items,
        'cart_subtotal': str(cart.subtotal)
    })


@require_POST
def update_cart_item(request, item_id):
    """Update cart item quantity"""
    data = json.loads(request.body)
    quantity = int(data.get('quantity', 1))
    
    cart = get_or_create_cart(request)
    cart_item = get_object_or_404(CartItem, id=item_id, cart=cart)
    
    if quantity <= 0:
        cart_item.delete()
        return JsonResponse({
            'success': True,
            'message': 'Item removed from cart',
            'cart_count': cart.total_items,
            'cart_subtotal': str(cart.subtotal)
        })
    
    if quantity > cart_item.book.stock_quantity:
        return JsonResponse({
            'success': False,
            'message': 'Quantity exceeds available stock'
        })
    
    cart_item.quantity = quantity
    cart_item.save()
    
    return JsonResponse({
        'success': True,
        'message': 'Cart updated',
        'item_total': str(cart_item.total_price),
        'cart_count': cart.total_items,
        'cart_subtotal': str(cart.subtotal)
    })


@require_POST
def remove_from_cart(request, item_id):
    """Remove item from cart"""
    cart = get_or_create_cart(request)
    cart_item = get_object_or_404(CartItem, id=item_id, cart=cart)
    cart_item.delete()
    
    return JsonResponse({
        'success': True,
        'message': 'Item removed from cart',
        'cart_count': cart.total_items,
        'cart_subtotal': str(cart.subtotal)
    })


def cart_data(request):
    """Get cart data for sidebar"""
    cart = get_or_create_cart(request)
    cart_items = cart.items.select_related('book').all()
    
    items_data = [{
        'id': item.id,
        'book_title': item.book.title,
        'book_slug': item.book.slug,
        'book_image': item.book.images.filter(is_primary=True).first().image.url if item.book.images.filter(is_primary=True).exists() else '',
        'quantity': item.quantity,
        'price': str(item.price),
        'total': str(item.total_price),
    } for item in cart_items]
    
    return JsonResponse({
        'items': items_data,
        'total_items': cart.total_items,
        'subtotal': str(cart.subtotal),
        'is_empty': cart.is_empty
    })
def checkout(request):
    """Checkout page"""
    cart = get_or_create_cart(request)
    
    if cart.is_empty:
        messages.warning(request, "Your cart is empty")
        return redirect('shop')
    
    # Check stock availability
    for item in cart.items.all():
        if item.quantity > item.book.stock_quantity:
            messages.error(request, f"Sorry, only {item.book.stock_quantity} copies of '{item.book.title}' are available")
            return redirect('cart_detail')
    
    # Get or create customer if user is authenticated
    customer = None
    addresses = []
    if request.user.is_authenticated:
        try:
            customer = Customer.objects.get(user=request.user)
            addresses = customer.addresses.filter(is_default=True)
        except Customer.DoesNotExist:
            pass
    
    context = {
        'cart': cart,
        'customer': customer,
        'addresses': addresses,
    }
    return render(request, 'checkout.html', context)

@require_POST
@csrf_protect
def place_order(request):
    """Place order and redirect to WhatsApp"""
    cart = get_or_create_cart(request)
    
    if cart.is_empty:
        messages.error(request, "Your cart is empty")
        return redirect('shop')
    
    # Validate cart items stock
    for item in cart.items.all():
        if item.quantity > item.book.stock_quantity:
            messages.error(request, f"Sorry, only {item.book.stock_quantity} copies of '{item.book.title}' are available")
            return redirect('checkout')
    
    # Get form data
    billing_first_name = request.POST.get('billing_first_name')
    billing_last_name = request.POST.get('billing_last_name')
    billing_email = request.POST.get('billing_email')
    billing_phone = request.POST.get('billing_phone')
    billing_address_line_1 = request.POST.get('billing_address_line_1')
    billing_address_line_2 = request.POST.get('billing_address_line_2', '')
    billing_city = request.POST.get('billing_city')
    billing_state = request.POST.get('billing_state')
    billing_postal_code = request.POST.get('billing_postal_code')
    billing_country = request.POST.get('billing_country', 'Kenya')
    
    # Shipping address (same as billing if not provided separately)
    use_same_shipping = request.POST.get('use_same_shipping', 'on')
    
    if use_same_shipping == 'on':
        shipping_first_name = billing_first_name
        shipping_last_name = billing_last_name
        shipping_address_line_1 = billing_address_line_1
        shipping_address_line_2 = billing_address_line_2
        shipping_city = billing_city
        shipping_state = billing_state
        shipping_postal_code = billing_postal_code
        shipping_country = billing_country
        shipping_phone = billing_phone
    else:
        shipping_first_name = request.POST.get('shipping_first_name')
        shipping_last_name = request.POST.get('shipping_last_name')
        shipping_address_line_1 = request.POST.get('shipping_address_line_1')
        shipping_address_line_2 = request.POST.get('shipping_address_line_2', '')
        shipping_city = request.POST.get('shipping_city')
        shipping_state = request.POST.get('shipping_state')
        shipping_postal_code = request.POST.get('shipping_postal_code')
        shipping_country = request.POST.get('shipping_country', 'Kenya')
        shipping_phone = request.POST.get('shipping_phone')
    
    # Get customer
    customer = None
    if request.user.is_authenticated:
        try:
            customer = Customer.objects.get(user=request.user)
        except Customer.DoesNotExist:
            pass
    
    # Create order
    order = Order.objects.create(
        customer=customer,
        # Billing address
        billing_first_name=billing_first_name,
        billing_last_name=billing_last_name,
        billing_address_line_1=billing_address_line_1,
        billing_address_line_2=billing_address_line_2,
        billing_city=billing_city,
        billing_state=billing_state,
        billing_postal_code=billing_postal_code,
        billing_country=billing_country,
        billing_phone=billing_phone,
        # Shipping address
        shipping_first_name=shipping_first_name,
        shipping_last_name=shipping_last_name,
        shipping_address_line_1=shipping_address_line_1,
        shipping_address_line_2=shipping_address_line_2,
        shipping_city=shipping_city,
        shipping_state=shipping_state,
        shipping_postal_code=shipping_postal_code,
        shipping_country=shipping_country,
        shipping_phone=shipping_phone,
        # Order totals
        subtotal=cart.subtotal,
        shipping_cost=Decimal('0.00'),  # Free shipping for now
        tax_amount=Decimal('0.00'),     # No tax for now
        total_amount=cart.subtotal,
        status='pending'
    )
    
    # Create order items
    for cart_item in cart.items.all():
        OrderItem.objects.create(
            order=order,
            book=cart_item.book,
            quantity=cart_item.quantity,
            price=cart_item.price,
            total=cart_item.total_price
        )
    
    # Clear the cart
    cart.items.all().delete()
    
    # Generate WhatsApp URL
    whatsapp_message = order.generate_whatsapp_message()
    whatsapp_number = "254712345678"  # Replace with your actual WhatsApp number
    whatsapp_url = f"https://wa.me/{whatsapp_number}?text={whatsapp_message.replace(' ', '%20').replace('\n', '%0A')}"
    
    # Store order ID in session for confirmation page
    request.session['last_order_id'] = str(order.id)
    
    return redirect(whatsapp_url)

def order_confirmation(request):
    """Order confirmation page"""
    order_id = request.session.get('last_order_id')
    if not order_id:
        messages.warning(request, "No recent order found")
        return redirect('home')
    
    try:
        order = Order.objects.get(id=order_id)
    except Order.DoesNotExist:
        messages.error(request, "Order not found")
        return redirect('home')
    
    # Clear the session
    if 'last_order_id' in request.session:
        del request.session['last_order_id']
    
    context = {
        'order': order,
    }
    return render(request, 'order_confirmation.html', context)

# Add this to your existing cart views if you don't have a cart detail page
def cart_detail(request):
    """Cart detail page"""
    cart = get_or_create_cart(request)
    context = {
        'cart': cart,
    }
    return render(request, 'cart.html', context)
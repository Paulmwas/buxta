from django.contrib import admin
from .models import (
    Category,
    Author,
    Publisher,
    Book,
    BookImage,
    Customer,
    Address,
    Review,
    Wishlist,
    Cart,
    CartItem,
    Order,
    OrderItem,
    OrderStatusHistory,
    Coupon,
    CouponUsage,
)

admin.site.register(Category)
admin.site.register(Author)
admin.site.register(Publisher)
admin.site.register(Book)
admin.site.register(BookImage)
admin.site.register(Customer)
admin.site.register(Address)
admin.site.register(Review)
admin.site.register(Wishlist)
admin.site.register(Cart)
admin.site.register(CartItem)
admin.site.register(Order)
admin.site.register(OrderItem)
admin.site.register(OrderStatusHistory)
admin.site.register(Coupon)
admin.site.register(CouponUsage)


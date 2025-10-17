from django.urls import path, include
from django.contrib import admin
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth.views import LoginView

urlpatterns = [
    # Django admin (optional, you can disable this)
    path('django-admin/', admin.site.urls),
    
    # Custom admin dashboard
    path('admin/login/', LoginView.as_view(template_name='admin/login.html'), name='admin_login'),
    path('admin/', include('home.admin_urls')),
    
    # Your main app URLs
    path('', include('home.urls')),
]

# This serves static and media files during development
if settings.DEBUG:
    # Serve static files
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATICFILES_DIRS[0])
    
    # Serve media files
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
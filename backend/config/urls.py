from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from accounts.views import AuthView, ProfileView, AddressViewSet, PasswordChangeView, PreferencesView
from vendors.views import VendorRegistration, VendorViewSet
from products.views import ProductViewSet
from orders.views import OrderViewSet
from payments.views import PaymentView, WebhookView, RefundView, AdminPaymentList
from core.views import (CategoryViewSet, ReviewViewSet, PromotionViewSet, BannerViewSet,
    ReportViewSet, CustomerViewSet, BootstrapView, CartView, WishlistView,
    SettingsView, AnalyticsView, AuditView, ContactView, NewsletterView)
from core.health import readiness

router = DefaultRouter()
for prefix, view, basename in [
    ('products',ProductViewSet,'product'),('categories',CategoryViewSet,'category'),
    ('vendors',VendorViewSet,'vendor'),('orders',OrderViewSet,'order'),
    ('reviews',ReviewViewSet,'review'),('addresses',AddressViewSet,'address'),
    ('admin/promotions',PromotionViewSet,'promotion'),('admin/banners',BannerViewSet,'banner'),
    ('admin/reports',ReportViewSet,'report'),('admin/users',CustomerViewSet,'customer')]:
    router.register(prefix,view,basename=basename)
urlpatterns = [path('health/ready/',readiness),path('internal-admin/',admin.site.urls),
    path('api/auth/profile/',ProfileView.as_view()),
    path('api/auth/password-change/',PasswordChangeView.as_view()),
    path('api/auth/preferences/',PreferencesView.as_view()),
    path('api/vendor-applications/',VendorRegistration.as_view()),
    path('api/bootstrap/',BootstrapView.as_view()),path('api/cart/',CartView.as_view()),
    path('api/wishlist/',WishlistView.as_view()),path('api/admin/settings/',SettingsView.as_view()),
    path('api/contact/',ContactView.as_view()),path('api/newsletter/',NewsletterView.as_view()),
    path('api/admin/audit/',AuditView.as_view()),path('api/analytics/',AnalyticsView.as_view()),
    path('api/admin/payments/',AdminPaymentList.as_view()),
    path('api/payments/',PaymentView.as_view(http_method_names=['post','options'])),
    path('api/payments/<uuid:pk>/',PaymentView.as_view(http_method_names=['get','head','options'])),
    path('api/payments/<uuid:pk>/verify/',PaymentView.as_view(http_method_names=['post','options'])),
    path('api/payments/<uuid:pk>/refunds/',RefundView.as_view()),
    path('api/payments/webhooks/<str:provider>/',WebhookView.as_view()),
    path('api/schema/',SpectacularAPIView.as_view(),name='schema'),
    path('api/docs/',SpectacularSwaggerView.as_view(url_name='schema')),
    path('api/',include(router.urls))]
for auth_action in ['csrf','session','register','login','logout','password-reset','password-reset-confirm','verify-email','resend-verification']:
    methods = ['get','head','options'] if auth_action in ['csrf','session'] else ['post','options']
    urlpatterns.append(path(f'api/auth/{auth_action}/',AuthView.as_view(http_method_names=methods),{'action':auth_action},name='auth-'+auth_action))
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL,document_root=settings.MEDIA_ROOT)
handler400 = 'core.errors.bad_request'
handler403 = 'core.errors.forbidden'
handler404 = 'core.errors.not_found'
handler500 = 'core.errors.server_error'

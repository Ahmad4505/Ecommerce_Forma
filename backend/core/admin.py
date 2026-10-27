from django.contrib import admin
from .models import AuditLog, PlatformSettings, Notification
from products.models import Product, ProductImage
from categories.models import Category
from orders.models import Order, OrderItem
from payments.models import Payment, WebhookEvent
from reviews.models import Review
from promotions.models import Promotion, Banner, ProductReport

class ImageInline(admin.TabularInline):
    model = ProductImage
    extra = 0
    def has_add_permission(self, request, obj=None):
        return False
    readonly_fields = ['image','source_url','attribution']

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ['name','vendor','category','price','stock','status']
    list_filter = ['status','category','featured']
    search_fields = ['name','sku','vendor__name']
    readonly_fields = ['created_at','updated_at']
    inlines = [ImageInline]

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ['id','user','status','payment_status','total','created_at']
    list_filter = ['status','payment_status']
    search_fields = ['id','user__email']
    readonly_fields = [field.name for field in Order._meta.fields]
    def has_add_permission(self, request):
        return False
    def has_delete_permission(self, request, obj=None):
        return False

class ReadOnlyAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False
    def has_change_permission(self, request, obj=None):
        return False
    def has_delete_permission(self, request, obj=None):
        return False

admin.site.register(AuditLog,ReadOnlyAdmin)
admin.site.register(Payment,ReadOnlyAdmin)
admin.site.register(WebhookEvent,ReadOnlyAdmin)
admin.site.register(Notification,ReadOnlyAdmin)
admin.site.register(OrderItem,ReadOnlyAdmin)
for model in [Category,Review,Promotion,Banner,ProductReport,PlatformSettings]:
    admin.site.register(model)

from .models import ContactMessage, NewsletterSubscriber
admin.site.register(ContactMessage)
admin.site.register(NewsletterSubscriber)

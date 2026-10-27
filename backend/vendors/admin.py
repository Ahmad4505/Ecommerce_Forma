from django.contrib import admin, messages
from rest_framework.exceptions import APIException
from .models import Vendor
from .services import decide_vendor

@admin.register(Vendor)
class VendorAdmin(admin.ModelAdmin):
    list_display = ['name','user','status','created_at','decision_by','decision_at']
    list_filter = ['status']
    search_fields = ['name','user__email','user__name']
    readonly_fields = ['status','decision_by','decision_at','decision_reason','created_at','updated_at']
    actions = ['approve','reject','suspend']
    def decide(self, request, queryset, status):
        for vendor in queryset:
            try:
                decide_vendor(request.user,vendor.pk,status)
            except APIException as exc:
                self.message_user(request,str(exc),level=messages.ERROR)
    @admin.action(description='Approve selected applications')
    def approve(self, request, queryset):
        self.decide(request,queryset,'APPROVED')
    @admin.action(description='Reject selected applications')
    def reject(self, request, queryset):
        self.decide(request,queryset,'REJECTED')
    @admin.action(description='Suspend selected stores')
    def suspend(self, request, queryset):
        self.decide(request,queryset,'SUSPENDED')

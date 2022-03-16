from django.contrib import admin

# Register your models here.
from register.models import Register, Customer


@admin.register(Register)
class RegisterAdmin(admin.ModelAdmin):
    readonly_fields = ['get_customer']  # Read Only Fields
    ordering = ('-log_date',)
    search_fields = ('customer',)
    list_filter = ('tenant__tenant', 'log_date', 'customer__name')
    list_display = (
        'get_customer',
        'log_date',
        'schedule',
        'quantity',
        'paid',
    )

    fieldsets = (
        ('Register Entry', {'fields': (
        'get_customer', 'log_date', 'schedule', 'quantity', 'current_price', 'paid')}),
    )

    def get_customer(self, obj):
        return obj.customer.name

    get_customer.short_description = 'customer'
    get_customer.admin_order_field = 'customer__name'


@admin.register(Customer)
class RegisterAdmin(admin.ModelAdmin):
    readonly_fields = ['member_since']  # Read Only Fields
    ordering = ('name',)
    search_fields = ('name',)
    list_filter = ('tenant__tenant', 'status', 'morning', 'evening', 'name',)
    list_display = (
        'name',
        'contact',
        'email',
        'morning',
        'evening',
        'm_quantity',
        'e_quantity',
        'status',
        'member_since',
    )

    fieldsets = (
        ('Customer Details', {'fields': ('name', 'contact', 'email')}),
        ('Schedule', {'fields': ('morning', 'evening', 'm_quantity', 'e_quantity')}),
        ('Status Details', {'fields': ('status', 'member_since')}),
    )

    def get_customer(self, obj):
        return obj.customer.name

    get_customer.short_description = 'customer'
    get_customer.admin_order_field = 'customer__name'

from django.contrib import admin

from loan.models import Loan, Transaction


class TransactionInline(admin.TabularInline):
    model = Transaction
    extra = 0


@admin.register(Loan)
class LoanAdmin(admin.ModelAdmin):
    ordering = ('-status', '-lending_date',)
    search_fields = ('name',)
    list_filter = ('status', 'tenant__tenant')
    list_display = (
        'tenant_name',
        'name',
        'amount',
        'interest_rate',
        'lending_date',
        'status',
        'notes',
    )
    inlines = [TransactionInline]

    def tenant_name(self, obj):
        return obj.tenant.tenant.username

    tenant_name.short_description = 'Tenant'

    class Meta:
        verbose_name = 'Loan'
        verbose_name_plural = 'Loans'

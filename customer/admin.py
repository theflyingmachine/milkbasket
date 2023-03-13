# Register your models here.
from django.contrib import admin
from django.contrib.sessions.models import Session
from django.utils import timezone

# Register your models here.
from customer.models import WhatsAppMessage


@admin.register(WhatsAppMessage)
class WhatsAppMessage(admin.ModelAdmin):
    readonly_fields = ['to_number',
                       'message_id',
                       'sender_number',
                       'sender_display_name',
                       'message_type',
                       'message_body',
                       'media_id',
                       'route',
                       'status',
                       'payload',
                       'sent_payload',
                       'related_message_id',
                       'received_at']  # Read Only Fields
    ordering = ('-received_at',)
    search_fields = ('sender_display_name', 'sender_number', 'to_number')
    list_filter = ('route', 'status', 'sender_display_name', 'sender_number')
    list_display = (
        'to_number',
        'sender_number',
        'sender_display_name',
        'message_type',
        'message_body',
        'media_id',
        'route',
        'status',
        'received_at'
    )

    class Meta:
        verbose_name = 'WhatsApp Message'
        verbose_name_plural = 'WhatsApp Messages'


class SessionStatusFilter(admin.SimpleListFilter):
    title = 'Session Status'
    parameter_name = 'status'

    def lookups(self, request, model_admin):
        return [
            ('active', 'Active Sessions'),
            ('expired', 'Expired Sessions'),
        ]

    def queryset(self, request, queryset):
        if self.value() == 'active':
            return queryset.filter(expire_date__gt=timezone.now())
        elif self.value() == 'expired':
            return queryset.filter(expire_date__lte=timezone.now())


@admin.register(Session)
class SessionManager(admin.ModelAdmin):
    readonly_fields = ['session_key',
                       'expire_date',
                       'session_data'
                       ]  # Read Only Fields
    ordering = ('-expire_date',)
    list_filter = (SessionStatusFilter,)
    list_display = (
        'session_key',
        'expire_date',

    )

    class Meta:
        verbose_name = 'Active Session'
        verbose_name_plural = 'Active Sessions'

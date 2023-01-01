# Register your models here.
from django.contrib import admin

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
                       'related_message_id',
                       'received_at']  # Read Only Fields
    ordering = ('-received_at',)
    search_fields = ('sender_display_name', 'sender_number', 'to_number')
    list_filter = ('sender_display_name', 'sender_number', 'route',)
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

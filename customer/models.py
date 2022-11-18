from django.db import models


class WhatsAppMessage(models.Model):
    message_id = models.CharField(max_length=100, primary_key=True)
    related_message_id = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True)
    route = models.CharField(max_length=20, null=False, blank=False)
    status = models.CharField(max_length=20, null=True, blank=True)
    to_number = models.IntegerField(null=False, blank=False)
    sender_display_name = models.CharField(max_length=50, null=True, default=None)
    sender_number = models.IntegerField(null=False, blank=False)
    message_type = models.CharField(max_length=50, default=None)
    message_body = models.TextField(null=True, blank=True)
    media_id = models.IntegerField(null=True, blank=True)
    received_at = models.DateTimeField(auto_now_add=True)
    payload = models.JSONField(default=None, null=True)

    class Meta:
        indexes = [
            models.Index(fields=["received_at"]),
        ]

    @staticmethod
    def insert_message(message_id, related_id, route, to_number, sender_name, sender_number,
                       message_type, message_body, media_id, payload):
        WhatsAppMessage.objects.create(message_id=message_id, related_message_id=related_id,
                                       route=route,
                                       to_number=to_number, sender_display_name=sender_name,
                                       sender_number=sender_number, message_type=message_type,
                                       message_body=message_body, media_id=media_id,
                                       payload=payload)

    @staticmethod
    def update_status(message_id, status):
        WhatsAppMessage.objects.filter(message_id=message_id).update(status=status)

    @staticmethod
    def get_related_message(message_id):
        return WhatsAppMessage.objects.filter(message_id=message_id).first()

    @staticmethod
    def create_or_update_reaction(message_id, related_id, route, to_number, sender_name,
                                  sender_number,
                                  message_type, message_body, payload):
        reaction_message = WhatsAppMessage.objects.filter(related_message_id=related_id,
                                                          message_type=message_type).first()
        if reaction_message:
            if message_body is None:
                reaction_message.delete()
            else:
                reaction_message.message_body = message_body
                reaction_message.save()
        else:
            WhatsAppMessage.insert_message(message_id, related_id, route, to_number, sender_name,
                                           sender_number,
                                           message_type, message_body, None, payload)

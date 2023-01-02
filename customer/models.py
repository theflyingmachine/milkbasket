import random
from datetime import datetime, timedelta

from django.db import models

from customer.constant import WA_OTP_MESSAGE_TEMPLATE, WA_OTP_MESSAGE
from milkbasket.secret import DEV_NUMBER, RUN_ENVIRONMENT
from register.models import Customer


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
    sent_payload = models.JSONField(default=None, null=True)

    class Meta:
        indexes = [
            models.Index(fields=["received_at"]),
        ]

    @staticmethod
    def insert_message(message_id, related_id, route, to_number, sender_name, sender_number,
                       message_type, message_body, media_id, payload, sent_payload=None):
        WhatsAppMessage.objects.create(message_id=message_id, related_message_id=related_id,
                                       route=route,
                                       to_number=to_number, sender_display_name=sender_name,
                                       sender_number=sender_number, message_type=message_type,
                                       message_body=message_body, media_id=media_id,
                                       payload=payload, sent_payload=sent_payload)

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


class LoginOTP(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT)
    otp_password = models.CharField(max_length=6)
    login_attempt = models.DecimalField(max_digits=1, decimal_places=0)
    generated_date = models.DateTimeField(null=False, default=datetime.now)

    @staticmethod
    def get_otp(customer):
        # Cleanup 24 hours old OTP
        time_threshold = datetime.now() - timedelta(hours=24)
        LoginOTP.objects.filter(generated_date__lt=time_threshold).delete()

        # Check if OPT exists, and attempt remaining
        current_otp = LoginOTP.objects.filter(customer=customer).first()
        if not current_otp:
            # Generate New OPT and return
            current_otp = LoginOTP(customer=customer,
                                   otp_password=random.randrange(111111, 999999, 6),
                                   login_attempt=0)
            current_otp.save()

            # send OTP Notification
            from register.utils import send_whatsapp_message
            wa_body = WA_OTP_MESSAGE_TEMPLATE
            wa_body[
                'to'] = f"91{DEV_NUMBER}" if RUN_ENVIRONMENT == 'dev' else f"91{customer.contact}"
            wa_body['template']['components'][0]['parameters'][0]['text'] = customer.name.title()
            wa_body['template']['components'][0]['parameters'][1][
                'text'] = current_otp.otp_password
            wa_message = WA_OTP_MESSAGE.format(customer.name, current_otp.otp_password)
            send_whatsapp_message(wa_body, wa_message, route='API_OTP')

        return current_otp

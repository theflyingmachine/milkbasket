import calendar
import datetime
import json
import logging
from hashlib import sha256
from hmac import compare_digest, HMAC

import numpy as np
from django.http import HttpResponseForbidden, HttpResponse
from django.shortcuts import render, redirect
# Create your views here.
from django.utils.safestring import mark_safe
from django.views.decorators.csrf import csrf_exempt

from customer.models import WhatsAppMessage, LoginOTP
from milkbasket.secret import WHATSAPP_WEBHOOK_TOKEN, DEV_NUMBER
from register.constant import WA_NEW_MESSAGE, WA_NEW_MESSAGE_TEMPLATE
from register.models import Customer, Payment, Register, Tenant
from register.utils import get_customer_due_amount, get_mongo_client, send_whatsapp_message, \
    is_mobile, get_client_ip, is_dev

logger = logging.getLogger()


def customer_dashboard(request):
    today = datetime.date.today()
    first = today.replace(day=1)
    last_month = first - datetime.timedelta(days=1)
    template = 'customer/index.html'
    customer = Customer.objects.filter(id=request.session.get('customer')).first()
    if not customer:
        return redirect('customer_dashboard_login')
    transactions = Payment.objects.filter(customer=customer).order_by('-log_date')
    register = Register.objects.filter(customer=customer, log_date__month=today.month,
                                       log_date__year=today.year)
    orders = [e.quantity for e in register if 'yes' in e.schedule]
    values, counts = np.unique(orders, return_counts=True)

    total_due, prev_month_due, advance = get_customer_due_amount(customer)

    seller = Tenant.objects.filter(tenant_id=customer.tenant_id).values('milk_price',
                                                                        'date_effective',
                                                                        'tenant__first_name',
                                                                        'tenant__last_name',
                                                                        'tenant__email',
                                                                        'contact',
                                                                        'email').first()

    days_in_month = calendar.monthrange(today.year, today.month)[1]

    today_entry = register.filter(log_date__day=today.day, schedule__contains='yes').values(
        'quantity', 'schedule')
    today_summary = [f"{e['schedule'].split('-')[0].capitalize()} {e['quantity']} ML" for e in
                     today_entry]
    # Fetch all bills in list of customer ids
    metadata = get_mongo_client()
    bills = metadata.find({'customer_id': {'$in': [customer.id]}},
                          {'bill_number': 1, 'customer_id': 1, 'customer_name': 1, 'bill_date': 1,
                           'views': 1, 'transaction_ids': 1, 'bill_summary': 1})
    bill_list, count_due_bill, count_paid_bill = [], 0, 0
    for bill in bills:
        string_date = bill['bill_date']  # 09 January 2021, 09:32 AM
        bill['bill_date_obj'] = datetime.datetime.strptime(string_date, '%d %B %Y, %I:%M %p')
        bill['payment_status'] = False if Register.objects.filter(id__in=bill['transaction_ids'],
                                                                  paid=0) else True
        bill['bill_amount'] = bill['bill_summary'][-1]['sum_total']
        bill_list.append(bill)
        if bill['payment_status']:
            count_paid_bill += 1
        else:
            count_due_bill += 1
    bill_list.sort(key=lambda x: x['bill_date_obj'], reverse=True)

    # Fetch Register Entries
    days, morning_entry, evening_entry = [], [], []
    for day in range(1, today.day + 1):
        days.append(day)
        m_e = register.filter(log_date__day=day, schedule__contains='morning').first()
        morning_entry.append(m_e.quantity if m_e and 'yes' in m_e.schedule else None)
        e_e = register.filter(log_date__day=day, schedule__contains='evening').first()
        evening_entry.append(e_e.quantity if e_e and 'yes' in e_e.schedule else None)

    context = {
        'customer': customer,
        'seller': seller,
        'summary': f'You have taken {",".join(today_summary)} today. Have a great day ahead!' if today_summary else 'You have not taken milk today.',
        'bills': bill_list,
        'bill_stats': {'count_due_bill': count_due_bill, 'count_paid_bill': count_paid_bill,
                       'percent': round((count_due_bill / len(bill_list) * 100),
                                        1) if count_due_bill else 100},
        'register_stats': {'days': mark_safe([f'{day} {today.strftime("%b")}' for day in days]),
                           'morning_entry': json.dumps(morning_entry),
                           'evening_entry': json.dumps(evening_entry)},
        'transactions': transactions,
        'order_statistics': {
            'labels': mark_safe([f"{v} ML" for v in values]),
            'series': list(counts),
            'orders': dict(zip(list(values), list(counts))),
            'total': sum(values * counts),
            'total_orders': sum(counts),
            'attendance': round((sum(counts) / register.count()) * 100,
                                1) if register.count() > 0 else 0,
        },
        'date': {'today': today, 'last_month': last_month},
        'payment': {'total_due': total_due, 'prev_month_due': prev_month_due, 'advance': advance},
        'days_in_month': {'days': days_in_month,
                          'percent': round((today.day / days_in_month) * 100, 1),
                          'remaining': days_in_month - today.day},
        'page_title': 'Milk Basket - Register',
        'is_mobile': is_mobile(request),
    }
    return render(request, template, context)


def customer_dashboard_logout(request):
    try:
        del request.session['customer_session']
        del request.session['customer']
    except:
        pass
    return redirect('customer_dashboard_login')


def customer_dashboard_login(request):
    template = 'customer/login.html'
    context = {}
    if request.method == "POST":
        username = request.POST.get("username")
        username = username.lower()
        password = request.POST.get("password")
        customer = Customer.objects.filter(contact=username).first()
        if customer:
            otp = LoginOTP.get_otp(customer, 'customer')
            context.update({'request_otp': otp.login_attempt < 3,
                            'remaining_attempt': otp.login_attempt < 3,
                            'current_username': username})
            if otp and password:
                if password == otp.otp_password and otp.login_attempt < 3:
                    request.session['customer_session'] = True
                    request.session['customer'] = customer.id
                    request.session.save()
                    logger.info(
                        'Customer Login - UserName:{0} Password:{1}, IP:{2}'.format(username,
                                                                                    password,
                                                                                    get_client_ip(
                                                                                        request)))
                    return redirect('customer_dashboard')
                else:
                    otp.login_attempt += 1
                    otp.save()
                    logger.warning(
                        'Failed Customer Login Attempt - UserName:{0} Password:{1} IP:{2}'.format(
                            username, password, get_client_ip(request)))
                    context.update({'message': 'Login Failed, {0}'.format(
                        f'{3 - otp.login_attempt} attempt remaining' if otp.login_attempt < 3 else 'please try again later')})
    if request.session.get('customer_session'):
        return redirect('customer_dashboard')

    return render(request, template, context)


def process_wa_payload(pl):
    try:
        # API Sent message status update
        status = pl['entry'][0]['changes'][0]['value']['statuses'][0]['status']
        related_message_id = pl['entry'][0]['changes'][0]['value']['statuses'][0]['id']
        if status in ['sent', 'delivered', 'read'] and related_message_id:
            WhatsAppMessage.update_status(related_message_id, status)
            return 'API Status Update'
    except KeyError:
        pass

    to_number = pl['entry'][0]['changes'][0]['value']['metadata']['phone_number_id']
    sender_name = pl['entry'][0]['changes'][0]['value']['contacts'][0]['profile']['name']
    sender_number = pl['entry'][0]['changes'][0]['value']['messages'][0]['from']
    message_id = pl['entry'][0]['changes'][0]['value']['messages'][0]['id']
    message_type = pl['entry'][0]['changes'][0]['value']['messages'][0]['type']
    try:
        # Message Emoji Reaction
        related_message_id = WhatsAppMessage.get_related_message(
            pl['entry'][0]['changes'][0]['value']['messages'][0]['reaction'][
                'message_id'])
        try:
            emoji = pl['entry'][0]['changes'][0]['value']['messages'][0]['reaction']['emoji']
        except KeyError:
            emoji = None

        WhatsAppMessage.create_or_update_reaction(message_id, related_message_id, 'User Reply',
                                                  to_number, sender_name, sender_number,
                                                  message_type, emoji, pl)
        return 'Message Reaction'
    except KeyError:
        pass

    try:
        # Message Reply
        try:
            related_message_id = WhatsAppMessage.get_related_message(
                pl['entry'][0]['changes'][0]['value']['messages'][0]['context']['id'])
        except KeyError:
            related_message_id = None

        text, media_id = None, None
        if message_type == 'text':
            text = pl['entry'][0]['changes'][0]['value']['messages'][0]['text']['body']

        else:
            try:
                text = pl['entry'][0]['changes'][0]['value']['messages'][0][message_type][
                    'caption']
            except KeyError:
                text = None
            try:
                media_id = pl['entry'][0]['changes'][0]['value']['messages'][0][message_type]['id']
            except KeyError:
                media_id = None

        WhatsAppMessage.insert_message(message_id, related_message_id, 'User Reply',
                                       to_number, sender_name, sender_number,
                                       message_type, text, media_id, pl)

        # Send Notification to seller
        send_new_message_notification(sender_number)
        return 'Message Reply'
    except KeyError:
        pass
    return 'Unknown'


def verify_signature(req):
    received_sign = req.headers.get('X-Hub-Signature-256').split('sha256=')[-1].strip()
    secret = WHATSAPP_WEBHOOK_TOKEN.encode()
    expected_sign = HMAC(key=secret, msg=req.data, digestmod=sha256).hexdigest()
    return compare_digest(received_sign, expected_sign)


@csrf_exempt
def whatsapp_webhook(request):
    if request.method == 'POST':
        # import facebook
        # xx=facebook.parse_signed_request(request, WHATSAPP_WEBHOOK_TOKEN)
        # print(xx)
        # given_token = request.headers.get("Webhook-Token", "")
        # if not compare_digest(given_token, WHATSAPP_WEBHOOK_TOKEN):
        #     return HttpResponseForbidden(
        #         "Incorrect token in WhatsApp-Webhook-Token header.",
        #         content_type="text/plain",
        #     )

        # WhatsAppWebhookMessage.objects.filter(
        #     received_at__lte=datetime.datetime.now() - datetime.timedelta(days=7)
        # ).delete()
        # signature = request.headers.get("X-Hub-Signature-256", "")
        payload = json.loads(request.body)
        # print(payload)
        # mac = hmac.new(bytes(WHATSAPP_WEBHOOK_TOKEN.encode(), 'UTF-8'), payload, digestmod=hashlib.sha256)
        # secret = WHATSAPP_WEBHOOK_TOKEN.encode()
        # calculated_signature = hmac.new(secret, payload, hashlib.sha256).hexdigest()
        # valid = calculated_signature == signature
        # print(valid)
        process_wa_payload(payload)
        # if verify_signature(request):
        #     process_wa_payload(payload)
        # else:
        #     return HttpResponse("unknown sig", content_type="text/plain")
        return HttpResponse("EVENT_RECEIVED", content_type="text/plain")

    if request.method == 'GET':
        if request.GET['hub.mode'] == "subscribe" and compare_digest(
            request.GET['hub.verify_token'], WHATSAPP_WEBHOOK_TOKEN):
            return HttpResponse(request.GET['hub.challenge'], content_type="text/plain")
        return HttpResponseForbidden(
            "Incorrect token",
            content_type="text/plain",
        )


def send_new_message_notification(from_sender):
    sender = Customer.objects.filter(contact=str(from_sender)[2:]).order_by('-member_since',
                                                                            '-status').first()
    if sender:
        wa_message = WA_NEW_MESSAGE.format(sender.name)
        wa_body = WA_NEW_MESSAGE_TEMPLATE
        wa_body[
            'to'] = f"91{DEV_NUMBER}" if is_dev() else f"91{sender.tenant.contact}"
        wa_body['template']['components'][0]['parameters'][0]['text'] = sender.name
        send_whatsapp_message(wa_body, wa_message, route='API_INFO')

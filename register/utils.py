import base64
import logging
import random
import re
import string
import threading
from calendar import monthrange
from datetime import datetime, date
from io import BytesIO

import barcode
import requests
from barcode.writer import ImageWriter
from dateutil.relativedelta import relativedelta
from django.contrib import messages
from django.core.mail import EmailMessage
from django.db.models import Q, Sum, F, FloatField
from django.http import HttpResponse
from django.http import JsonResponse
from django.shortcuts import render
from django.template.loader import get_template
from django.urls import reverse
from pymongo import MongoClient
from xhtml2pdf import pisa

from customer.models import WhatsAppMessage
from milkbasket.secret import ALEXA_KEY, WA_NUMBER_ID, WA_TOKEN, DEV_NUMBER, RUN_ENVIRONMENT
from milkbasket.secret import MONGO_COLLECTION
from milkbasket.secret import MONGO_DATABASE
from milkbasket.secret import MONGO_KEY
from register.constant import WA_PAYMENT_MESSAGE, WA_PAYMENT_MESSAGE_TEMPLATE
from register.models import Balance, Payment
from register.models import Bill
from register.models import Customer
from register.models import Register
from register.models import Tenant

# ======== UTILITY ============
# Only helper function beyond this point

logger = logging.getLogger()


def get_mongo_client():
    """ Helper function to return mongo DB client based on correct environment """
    client = MongoClient(
        f'mongodb+srv://milkbasket:{MONGO_KEY}@cluster0.4wgsn.mongodb.net/{MONGO_DATABASE}?retryWrites=true&w=majority')
    db = client[MONGO_DATABASE]
    # Fetch Bill Metadata
    return db[MONGO_COLLECTION]


def get_active_month(customer_id, only_paid=False, only_due=False, all_active=False):
    """ Returns active month list of customer """
    active_months = None
    if customer_id:
        if all_active:
            active_months = Register.objects.filter(customer_id=customer_id)
        if only_paid:
            active_months = Register.objects.filter(customer_id=customer_id,
                                                    schedule__endswith='-yes', paid=1)
        if only_due:
            tenant = Tenant.objects.get(customer__id=customer_id)
            prev_month_due = Register.objects.filter(customer_id=customer_id, paid=0,
                                                     schedule__in=['morning-yes',
                                                                   'evening-yes']).exclude(
                log_date__month=datetime.now().month, log_date__year=datetime.now().year)

            if not prev_month_due or tenant.bill_till_date or is_last_day_of_month():

                active_months = Register.objects.filter(customer_id=customer_id,
                                                        schedule__endswith='-yes', paid=0)
            else:
                active_months = Register.objects.filter(customer_id=customer_id,
                                                        schedule__endswith='-yes', paid=0).exclude(
                    log_date__month=datetime.now().month, log_date__year=datetime.now().year)

    return active_months.dates('log_date', 'month', order='DESC')


def get_register_month_entry(customer_id, month=False, year=False):
    """ Returns register entry of a given month """
    register_entry = None
    if customer_id:
        if month and year:
            register_entry = Register.objects.filter(customer_id=customer_id,
                                                     log_date__month=month, log_date__year=year)
        else:
            register_entry = Register.objects.filter(customer_id=customer_id)

    return register_entry


def get_register_day_entry(customer_id, day=False, month=False, year=False,
                           transaction_list=False):
    """  Returns register entry of a given day """
    register_entry = None
    if customer_id:
        if day and month and year:
            register_entry = Register.objects.filter(customer_id=customer_id,
                                                     log_date__day=day,
                                                     log_date__month=month,
                                                     log_date__year=year,
                                                     id__in=transaction_list) if transaction_list else Register.objects.filter(
                customer_id=customer_id,
                log_date__day=day,
                log_date__month=month,
                log_date__year=year)
        else:
            register_entry = Register.objects.filter(customer_id=customer_id,
                                                     id__in=transaction_list) if transaction_list else Register.objects.filter(
                customer_id=customer_id)

    for entry in register_entry:
        entry.morning = True if entry.schedule == 'morning-yes' or entry.schedule == 'morning-no' else False
        entry.evening = True if entry.schedule == 'evening-yes' or entry.schedule == 'evening-no' else False
        entry.absent = True if entry.schedule == 'evening-no' or entry.schedule == 'morning-no' else False
        entry.quantity = '' if entry.absent else f'{int(entry.quantity)} ML'

    return register_entry


def get_bill_summary(customer_id, month=False, year=False):
    """ Return bill summary for the customer id """
    bill_summary = None
    if customer_id:
        # check if customer has due
        if month and year:
            due = Register.objects.filter(customer_id=customer_id, paid=0,
                                          schedule__endswith='-yes', log_date__month=month,
                                          log_date__year=year).values_list('quantity',
                                                                           'current_price')
        else:
            due = Register.objects.filter(customer_id=customer_id, paid=0,
                                          schedule__endswith='-yes').values_list('quantity',
                                                                                 'current_price')

        if due:
            summary_sheet = [{'quantity': entry[0],
                              'unit_price': float(entry[1]),
                              'cost_price': (float(entry[0]) * float(entry[1])) / 1000
                              } for entry in due]
            unique_quantity = sorted(set([quantity['quantity'] for quantity in summary_sheet]))
            bill_summary = [{'quantity': quantity,
                             'desc': sum(
                                 1 for entry in summary_sheet if
                                 entry.get('quantity') == quantity),
                             'total_units': int(
                                 sum(entry.get('quantity') for entry in summary_sheet if
                                     entry.get('quantity') == quantity)),
                             'amount': sum(entry.get('cost_price') for entry in summary_sheet if
                                           entry.get('quantity') == quantity),
                             } for quantity in unique_quantity]
            total = {'total': sum(entry.get('amount') for entry in bill_summary)}
            bill_summary.append(total)

    return bill_summary


def customer_register_last_updated(customer_id):
    """ Returns date when the register entry for customer was last updated"""
    last_updated = None
    if customer_id:
        last_updated = Register.objects.filter(customer_id=customer_id).values_list('log_date',
                                                                                    flat=True).last()

    return last_updated


def get_customer_balance_amount(customer_id):
    """ Returns Balance / advance paid amount of customer"""
    balance_amount = None
    if customer_id:
        balance_amount = Balance.objects.filter(customer_id=customer_id).first()
        balance_amount = abs(float(
            getattr(balance_amount, 'balance_amount'))) if balance_amount else 0
    return balance_amount


def get_customer_due_amount(customer_id):
    """ Returns DUE - Balance / advance paid amount of customer"""
    today = datetime.today()
    register_due_qs = Register.objects.filter(customer=customer_id, paid=False,
                                              schedule__in=('evening-yes', 'morning-yes'))
    # Calculate due till today
    total_due = register_due_qs.annotate(
        total_due=Sum(F('current_price') * F('quantity'), output_field=FloatField())).aggregate(
        Sum('total_due'))['total_due__sum']
    total_due = total_due / 1000 if total_due else 0
    # Calculate due till previous month
    prv_month_qs = register_due_qs.exclude(log_date__year=today.year, log_date__month=today.month)
    prev_month_due = prv_month_qs.annotate(
        total_due=Sum(F('current_price') * F('quantity'), output_field=FloatField())).aggregate(
        Sum('total_due'))['total_due__sum']
    prev_month_due = prev_month_due / 1000 if prev_month_due else 0
    adv = get_customer_balance_amount(customer_id)
    return (total_due - adv), (prev_month_due - adv), adv


def render_to_pdf(template_src, context_dict={}):
    """ Utility for Bill PDF generation """
    template = get_template(template_src)
    html = template.render(context_dict)
    result = BytesIO()
    pdf = pisa.pisaDocument(BytesIO(html.encode("ISO-8859-1")), result)
    if not pdf.err:
        return HttpResponse(result.getvalue(), content_type='application/pdf')
    return None


def get_base_64_barcode(barcode_text):
    """ Return base 64 bar code """
    barcode_file_base64 = None
    if barcode_text:
        rv = BytesIO()
        barcode.get('code128', barcode_text, writer=ImageWriter()).write(rv)
        barcode_file_base64 = base64.b64encode(rv.getvalue()).decode()
    return barcode_file_base64

def send_sms_api(contact, sms_text, template_id):
    """ Send SMS api """
    response = None

    try:
        from milkbasket.secret import SMS_API_KEY
    except ModuleNotFoundError as e:
        print('API key not found')
        SMS_API_KEY = ''
        logger.critical('SMS API KEY NOT FOUND')
    if contact and sms_text:
        url = 'https://cyberboy.in/sms/milk_smsapi.php'
        payload = {'apikey': SMS_API_KEY,
                   'mobile': contact,
                   'message': sms_text,
                   'template_id': template_id,
                   }
        print(payload)
        response = requests.post(url, data=payload)
        logger.info(response.text)
    return response


def save_bill_to_mongo(bill_metadata, bill, bill_number):
    """ Upload bill metadata to cloud mongo db """
    # Upload Bill Metadata
    try:
        metadata = get_mongo_client()
        bill_metadata_id = metadata.insert(bill_metadata)
        bill.mongo_id = str(bill_metadata_id)
        bill.save()
        logger.info(f'MongoDB bill uploaded {str(bill_metadata_id)} - Bill Number: {bill_number}')
        return bill_metadata_id
    except:
        logger.critical(
            f'MongoDB bill upload failed : {bill_metadata} - Bill Number: {bill_number}')


def get_register_transactions(cust_id, only_paid=False, only_due=True):
    """ Fetch register transactions """
    transactions = None
    if cust_id:
        if only_due:
            tenant = Tenant.objects.get(customer__id=cust_id)
            # Get all due Transactions till last month
            transactions = Register.objects.filter(customer_id=cust_id, paid=0,
                                                   schedule__in=['morning-yes',
                                                                 'evening-yes']).exclude(
                log_date__month=datetime.now().month, log_date__year=datetime.now().year)
            # Get All Transactions if Settings Enabled OR Last date of the Month OR no previous due
            if tenant.bill_till_date or is_last_day_of_month() or not transactions:
                transactions = Register.objects.filter(customer_id=cust_id, paid=0,
                                                       schedule__in=['morning-yes',
                                                                     'evening-yes'])

        elif only_paid:
            transactions = Register.objects.filter(customer_id=cust_id, paid=1,
                                                   schedule__in=['morning-yes',
                                                                 'evening-yes'])
        else:
            transactions = Register.objects.filter(customer_id=cust_id)

    return transactions.values_list('id', flat=True)


def get_milk_current_price(tenant_id, description=False):
    """ Get Current milk price with or without description """
    tenant = Tenant.objects.get(tenant_id=tenant_id)
    if description:
        current_price = f'Effective {tenant.date_effective.strftime("%d %B %Y")}, current milk price is ₹ {tenant.milk_price} per liter.'
    else:
        current_price = tenant.milk_price
    return current_price


def check_customer_is_active(cust_id):
    """ Check if the given customer is active """
    is_active = False
    if cust_id:
        status = Customer.objects.filter(id=cust_id).filter(Q(morning=1) | Q(evening=1))
        is_active = True if status else False
    return is_active


def send_email_api(to_email, subject, data):
    """ Send email message """
    status = {'status': 'failed'}
    if to_email and data:
        email_body = get_template('register/email_bill_template.html').render(data)
        email = EmailMessage(subject, email_body, to=[to_email])
        email.content_subtype = "html"
        if email.send():
            logger.info('Email Sent Successfully {0}, {1}'.format(to_email, subject))
            status['status'] = 'success'
    return status


def generate_bill(request, cust_id, no_download=False, raw_data=False):
    """Generate bill and upload to mongo """
    res = ''.join(random.choices(string.ascii_uppercase + string.digits, k=7))
    bill_number = f'MB-{cust_id}-{datetime.now().year}-{datetime.now().month}-{res}'
    customer = Customer.objects.get(id=cust_id)
    # Extract only due months for bill
    due_months = get_active_month(cust_id, only_paid=False, only_due=True)
    bill_summary = [{'month_year': f'{due_month.strftime("%B")} {due_month.year}',
                     'desc': get_bill_summary(cust_id, month=due_month.month,
                                              year=due_month.year)}
                    for due_month in due_months]
    bill_month = bill_summary[0]['month_year'] if bill_summary else ''
    bill_summary.reverse()
    bill_sum_total = {
        'last_updated': customer_register_last_updated(cust_id).strftime("%d %B %Y"),
        'today': datetime.now().strftime("%d %B %Y, %I:%M %p"),
        'sum_total': (
            sum([bill.get('desc')[-1]['total'] for bill in bill_summary if bill.get('desc')]))}

    # Check for balance / Due amount
    balance_amount = get_customer_balance_amount(cust_id)
    if balance_amount:
        bill_sum_total['balance'] = balance_amount
        bill_sum_total['sub_total'] = bill_sum_total['sum_total']
        bill_sum_total['sum_total'] = bill_sum_total['sum_total'] - balance_amount

    bill_summary.append(bill_sum_total)
    barcode = get_base_64_barcode(bill_number)

    # Save to database before rendering PDF
    bill = Bill(customer_id=customer, bill_number=bill_number,
                amount=bill_sum_total['sum_total'],
                bill_last_data_date=customer_register_last_updated(cust_id))

    # Render PDF data
    data = {'barcode': barcode, 'bill_number': bill_number, 'page_title': bill_number,
            'customer_id': cust_id, 'customer_name': customer.name,
            'bill_date': datetime.now().strftime("%d %B %Y, %I:%M %p"),
            'last_update': customer_register_last_updated(cust_id).strftime("%d %B %Y"),
            'bill_summary': bill_summary,
            'milk_price': get_milk_current_price(request.user.id, description=True).replace('₹',
                                                                                            'Rs.'),
            'transaction_ids': list(get_register_transactions(cust_id, only_due=True))}
    # Upload Bill metadata to Mongo
    mongo_upload_thread = threading.Thread(target=save_bill_to_mongo,
                                           args=(data, bill, bill_number))
    mongo_upload_thread.start()
    if no_download:
        return JsonResponse(
            {'status': 'success', 'amount': bill_sum_total['sum_total'],
             'bill_number': data['bill_number'], 'month_year': bill_month, })
    elif raw_data:
        return (
            {'status': 'success', 'amount': bill_sum_total['sum_total'],
             'bill_number': data['bill_number'], 'raw_data': data})
    return data


def is_last_day_of_month():
    """Function to check if today is the last day of the month"""
    today = datetime.today().date()
    last_day = today.replace(day=monthrange(today.year, today.month)[1])
    return True if today == last_day else False


def get_tenant_perf(request):
    """Function used to fetch the tenant preference """
    # Get Tenant Preference
    try:
        return Tenant.objects.get(tenant_id=request.user.id)
    except Tenant.DoesNotExist:
        if not request.user.is_superuser:
            messages.add_message(request, messages.WARNING,
                                 'You need to set milk price and update preferences.')
        return None


def get_last_transaction(request, customer):
    """ Function to get last transaction of a customer"""
    try:
        return Payment.objects.filter(tenant_id=request.user.id, customer=customer).latest('id')
    except Payment.DoesNotExist:
        return None


def is_transaction_revertible(request, customer):
    """ Function to check if last is revertible"""
    return True if Balance.objects.filter(tenant_id=request.user.id, customer=customer).exclude(
        last_balance_amount=None) else False


def is_mobile(request):
    """Return True if the request comes from a mobile device."""
    MOBILE_AGENT_RE = re.compile(r".*(iphone|mobile|androidtouch)", re.IGNORECASE)
    if MOBILE_AGENT_RE.match(request.META['HTTP_USER_AGENT']):
        return True
    else:
        return False


def authenticate_alexa(request):
    """ Authenticates the key for get request from Alexa """
    if request.method == "GET" and request.GET.get("key") != ALEXA_KEY:
        return JsonResponse({
            'status': 'Unauthorised',
        }, status=400)


def get_last_autopilot(tenant_id=2):
    """ Gets next day from which autopilot is possible. Last entry day + 1 """
    today = datetime.today()
    try:
        last_entry_date = Register.objects.filter(tenant_id=tenant_id,
                                                  log_date__month=today.month,
                                                  log_date__year=today.year).latest(
            'log_date__day')
        last_entry_date = int(last_entry_date.log_date.strftime("%d")) + 1
    except Register.DoesNotExist:
        last_entry_date = 1
    return last_entry_date


def get_customer_all_due(request, cust_id=None):
    """ Get formatted due for billing """
    tenant = Tenant.objects.filter(tenant_id=request.user.id).first()
    current_date = date.today()
    prev_month_name = (current_date + relativedelta(months=-1)).strftime("%B")
    current_month_name = current_date.strftime("%B")
    due_customer = Register.objects.filter(tenant_id=request.user.id, schedule__endswith='yes',
                                           paid=0).values('customer_id',
                                                          'customer__name',
                                                          'customer__contact',
                                                          'customer__email').distinct()
    if cust_id:
        due_customer = due_customer.filter(customer_id=cust_id)

    for customer in due_customer:
        customer['total_due'], customer['prev_month_due'], customer[
            'adv'] = get_customer_due_amount(
            customer['customer_id'])
    bill_till_date = is_last_day_of_month() or tenant.bill_till_date
    due_cust = []
    for c in due_customer:
        if c['customer__contact'] and c['total_due'] > 0:
            if bill_till_date or not c['prev_month_due'] > 0:
                to_be_paid, due_month = c['total_due'], current_month_name
            else:
                to_be_paid, due_month = c['prev_month_due'], prev_month_name
            due_cust.append(
                dict(id=c['customer_id'],
                     name=c['customer__name'],
                     contact=c['customer__contact'],
                     to_be_paid=to_be_paid,
                     due_month=due_month,
                     profile_url=reverse('customer_profile', args=[c['customer_id']]),
                     advance=c['adv'])
            )
    return due_cust


def get_customer_due_amount_by_month(request, customer_id=None):
    """ Returns DUE amount of customers by month"""
    register_due_qs = Register.objects.filter(tenant_id=request.user.id, schedule__endswith='yes',
                                              paid=0)
    due_customer = register_due_qs.values('customer_id',
                                          'customer__name',
                                          'customer__contact',
                                          'customer__email').distinct()
    if customer_id:
        due_customer = due_customer.filter(tenant_id=request.user.id, customer_id=customer_id)
    due_list = []
    for customer in due_customer:
        due_qs = register_due_qs.filter(customer_id=customer['customer_id'])
        total_due = sum([float(entry.current_price / 1000) * entry.quantity for entry in due_qs])
        due_dict = {
            'customer_id': customer['customer_id'],
            'customer_name': customer['customer__name'],
            'total_due': total_due,
        }
        months = due_qs.dates('log_date', 'month', order='DESC')
        for month in months:
            month_due = sum(
                [float(entry.current_price / 1000) * entry.quantity for entry in due_qs if
                 entry.log_date.month == month.month and entry.log_date.year == month.year])
            due_dict[month.strftime("%B-%Y")] = month_due
        due_list.append(due_dict)
    due_list = (sorted(due_list, key=lambda i: (i['total_due'], i['customer_name'])))
    due_months = [d.strftime("%B-%Y") for d in
                  register_due_qs.dates('log_date', 'month', order='DESC')]
    return due_list, due_months


def send_whatsapp_message(wa_body, wa_message, route=None, cust_id=None, cust_number=None):
    url = f"https://graph.facebook.com/v13.0/{WA_NUMBER_ID}/messages"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {WA_TOKEN}",
    }
    data = wa_body
    response = requests.post(url, headers=headers, json=data)
    if response.status_code == 200:
        resp = response.json()
        message_id = resp['messages'][0]['id']
        related_id = None
        route = 'API' if route is None else route
        to_number = resp['contacts'][0]['input']
        sender_number = WA_NUMBER_ID
        message_type = wa_body['template']['name']
        payload = resp
        WhatsAppMessage.insert_message(message_id, related_id, route, to_number, 'Milk Basket',
                                       sender_number, message_type, wa_message, None, payload,
                                       sent_payload=wa_body)
        logger.info(
            'WhatsApp Message Sent Cust_ID:{0}  resp_to:{1} payload_to:{2} response:{3} payload:{4}'.format(
                cust_id, to_number, cust_number, payload, wa_body))
    elif response.status_code == 400:
        logger.warning(
            'WhatsApp Message Undeliverable. Cust_ID:{0} payload_to:{1} response:{2} payload:{3}'.format(
                cust_id, cust_number, response.json(), wa_body))

    else:
        logger.error(
            'Sending WhatsApp Message Failed. Cust_ID:{0} payload_to:{1} response:{2} payload:{3}'.format(
                cust_id, cust_number, response.json(), wa_body))

    return response.status_code == 200


def get_whatsapp_media_by_id(media_id):
    """ Fetch Whatsapp Media by media_id"""
    url = f"https://graph.facebook.com/v15.0/{media_id}"
    headers = {
        "Authorization": f"Bearer {WA_TOKEN}",
    }
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        resp = response.json()
        response = requests.get(resp['url'], headers=headers)
        if response.status_code == 200:
            return response.content, resp['mime_type']
    return False


def get_customer_contact(request, cust_id):
    """ Fetch contact number of a customer """
    return Customer.objects.filter(tenant_id=request.user.id, id=cust_id).first().contact


def send_wa_payment_notification(cust_number, cust_name, payment_amount, payment_time,
                                 transaction_number):
    """ Send WA notification for Payment received """
    wa_body = WA_PAYMENT_MESSAGE_TEMPLATE
    wa_body['to'] = f"91{DEV_NUMBER}" if RUN_ENVIRONMENT == 'dev' else f"91{cust_number}"
    wa_body['template']['components'][0]['parameters'][0]['text'] = cust_name
    wa_body['template']['components'][0]['parameters'][1]['text'] = payment_amount
    wa_body['template']['components'][0]['parameters'][2]['text'] = payment_time
    wa_body['template']['components'][0]['parameters'][3]['text'] = transaction_number
    wa_message = WA_PAYMENT_MESSAGE.format(cust_name, payment_amount, payment_time,
                                           transaction_number)
    return send_whatsapp_message(wa_body, wa_message)


def get_client_ip(request):
    """ Extract user IP address for logging purpose """
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


def calculate_milk_price(register_qs):
    """ Takes Register queryset and returns the amount payable in float"""
    total_due = 0
    if register_qs:
        total_due = register_qs.annotate(total_due=Sum(F('current_price') * F('quantity'),
                                                       output_field=FloatField())).aggregate(
            Sum('total_due'))['total_due__sum']
    return total_due / 1000 if total_due else 0


#  ===================== Custom Error Handler Views ==============================
def error_403_view(request, *args, **argv):
    return render(request, 'register/errors/403.html', status=403)


def error_404_view(request, *args, **argv):
    return render(request, 'register/errors/404.html', status=404)


def error_500_view(request, *args, **argv):
    return render(request, 'register/errors/500.html', status=500)

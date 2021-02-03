import base64
import random
import string
from calendar import monthrange
from datetime import datetime
from io import BytesIO

import requests
from django.core.mail import EmailMessage
from django.db.models import Q
from django.http import HttpResponse
from django.http import JsonResponse
from django.template.loader import get_template
from pymongo import MongoClient
from xhtml2pdf import pisa

from milkbasket.secret import MONGO_COLLECTION
from milkbasket.secret import MONGO_DATABASE
from milkbasket.secret import MONGO_KEY
from register.models import Balance
from register.models import Bill
from register.models import Customer
from register.models import Milk
from register.models import Register


# ======== UTILITY ============
# Only helper function beyond this point
def get_active_month(customer_id, only_paid=False, only_due=False, all_active=False):
    """ Returns active month list of customer """
    active_months = None
    if customer_id:
        if all_active:
            active_months = Register.objects.filter(customer_id=customer_id).dates(
                'log_date', 'month', order='DESC')
        if only_paid:
            active_months = Register.objects.filter(customer_id=customer_id,
                                                    schedule__endswith='-yes', paid=1).dates(
                'log_date', 'month', order='DESC')
        if only_due:
            active_months = Register.objects.filter(customer_id=customer_id,
                                                    schedule__endswith='-yes', paid=0).dates(
                'log_date', 'month', order='DESC')

    return active_months


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
    barcode = None
    if barcode_text:
        url = f'https://mobiledemand-barcode.azurewebsites.net/barcode/image?content={barcode_text}&size=100&symbology=CODE_128&format=png&text=true'
        barcode = base64.b64encode(requests.get(url).content).decode('utf-8')
    return barcode


def send_sms_api(contact, sms_text):
    """ Send SMS api """
    response = None

    try:
        from milkbasket.secret import SMS_API_KEY
    except ModuleNotFoundError as e:
        print('API key not found')
        SMS_API_KEY = ''
    if contact and sms_text:
        url = 'https://cyberboy.in/sms/milk_smsapi.php'
        payload = {'apikey': SMS_API_KEY,
                   'mobile': contact,
                   'message': sms_text,
                   }
        response = requests.post(url, data=payload)
    return response


def save_bill_to_mongo(bill_metadata):
    """ Upload bill metadata to cloud mongo db """
    client = MongoClient(
        f'mongodb+srv://milkbasket:{MONGO_KEY}@cluster0.4wgsn.mongodb.net/{MONGO_DATABASE}?retryWrites=true&w=majority')
    db = client[MONGO_DATABASE]
    # Upload Bill Metadata
    metadata = db[MONGO_COLLECTION]
    bill_metadata_id = metadata.insert(bill_metadata)

    return bill_metadata_id


def get_register_transactions(cust_id, only_paid=False, only_due=True):
    """ Fetch register transactions """
    transactions = None
    if cust_id:
        if only_due:
            transactions = Register.objects.filter(customer_id=cust_id, paid=0,
                                                   schedule__in=['morning-yes',
                                                                 'evening-yes']).values_list('id',
                                                                                             flat=True)
        elif only_paid:
            transactions = Register.objects.filter(customer_id=cust_id, paid=1,
                                                   schedule__in=['morning-yes',
                                                                 'evening-yes']).values_list('id',
                                                                                             flat=True)
        else:
            transactions = Register.objects.filter(customer_id=cust_id).values_list('id',
                                                                                    flat=True)

    return transactions


def get_milk_current_price(description=False):
    """ Get Current milk price with or without description """
    milk = Milk.objects.last()
    if description:
        current_price = f'Effective {milk.date_effective.strftime("%d %B %Y")}, current milk price is ₹ {milk.price} per liter.'
    else:
        current_price = milk.price
    return current_price


def check_customer_is_active(cust_id):
    """ Check if the given customer is active """
    is_active = False
    if cust_id:
        status = Customer.objects.filter(id=cust_id).filter(Q(morning=1) | Q(evening=1))
        is_active = True if status else False
    return is_active


def send_email_api(to_email, data):
    """ Send email message """
    status = {'status': 'failed'}
    if to_email and data:
        email_body = get_template('register/email_bill_template.html').render(data)
        email = EmailMessage('MilkBasket Bill', email_body, to=[to_email])
        email.content_subtype = "html"
        if email.send():
            status['status'] = 'success'
    return status


def generate_bill(cust_id, no_download=False, raw_data=False):
    """Generate bill and upload to mongo """
    res = ''.join(random.choices(string.ascii_uppercase + string.digits, k=7))
    bill_number = f'MB-{cust_id}-{datetime.now().year}-{datetime.now().month}-{res}'
    customer = Customer.objects.get(id=cust_id)
    # Extract months which has due for calendar
    active_months = get_active_month(cust_id, all_active=True)
    calendar = [{'month': active_month.strftime('%B'),
                 'year': active_month.strftime('%Y'),
                 'week_start_day': [x for x in range(0, active_month.weekday())],
                 'days_in_month': [{'day': day,
                                    'data': get_register_day_entry(cust_id, day=day,
                                                                   month=active_month.month,
                                                                   year=active_month.year)
                                    } for day in range(1, (
                     monthrange(active_month.year, active_month.month)[1]) + 1)]
                 } for active_month in active_months]

    # Extract only due months for bill
    due_months = get_active_month(cust_id, only_paid=False, only_due=True)
    bill_summary = [{'month_year': f'{due_month.strftime("%B")} {due_month.year}',
                     'desc': get_bill_summary(cust_id, month=due_month.month,
                                              year=due_month.year)}
                    for due_month in due_months]
    bill_summary.reverse()
    bill_sum_total = {
        'last_updated': customer_register_last_updated(cust_id).strftime("%d %B, %Y"),
        'today': datetime.now().strftime("%d %B, %Y, %H:%M %p"),
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
    bill.save()

    # Render PDF data
    data = {'barcode': barcode, 'bill_number': bill_number, 'page_title': bill_number,
            'customer_id': cust_id, 'customer_name': customer.name,
            'bill_date': datetime.now().strftime("%d %B, %Y, %H:%M %p"),
            'last_update': customer_register_last_updated(cust_id).strftime("%d %B, %Y"),
            'bill_summary': bill_summary,
            'milk_price': get_milk_current_price(description=True).replace('₹', 'Rs.'),
            'transaction_ids': list(get_register_transactions(cust_id, only_due=True))}
    # Upload Bill metadata to Mongo
    mongo_id = save_bill_to_mongo(data)
    if no_download:
        return JsonResponse(
            {'status': 'success', 'amount': bill_sum_total['sum_total'],
             'mongo': str(mongo_id), 'bill_number': data['bill_number'],
             'raw_data': data})
    elif raw_data:
        return (
            {'status': 'success', 'amount': bill_sum_total['sum_total'],
             'mongo': str(mongo_id), 'bill_number': data['bill_number'],
             'raw_data': data})
    return data

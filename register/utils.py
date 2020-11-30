import base64
import requests

from register.models import Customer, Register, Milk, Expense, Payment, Balance, Income

from django.http import HttpResponse
from django.template.loader import get_template

from io import BytesIO
from xhtml2pdf import pisa


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


def get_register_day_entry(customer_id, day=False, month=False, year=False):
    """  Returns register entry of a given day """
    register_entry = None
    if customer_id:
        if day and month and year:
            register_entry = Register.objects.filter(customer_id=customer_id, log_date__day=day,
                                                     log_date__month=month, log_date__year=year)
        else:
            register_entry = Register.objects.filter(customer_id=customer_id)
        for entry in register_entry:
            entry.morning = True if entry.schedule == 'morning-yes' or entry.schedule == 'morning-no' else False
            entry.evening = True if entry.schedule == 'evening-yes' or entry.schedule == 'evening-no' else False
            entry.absent = True if entry.schedule == 'evening-no' or entry.schedule == 'morniing-no' else False
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
        balance_amount = float(
            getattr(balance_amount, 'balance_amount')) if balance_amount else 0
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

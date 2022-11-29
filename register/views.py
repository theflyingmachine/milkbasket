import ast
import decimal
import json
from calendar import monthrange
from datetime import date
from datetime import datetime
from datetime import timedelta

from dateutil.relativedelta import relativedelta
from django.contrib import messages
from django.contrib.auth import authenticate
from django.contrib.auth import login
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Sum, Q
from django.http import HttpResponse
from django.http import JsonResponse
from django.shortcuts import redirect
from django.shortcuts import render
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.views.generic import View

from customer.models import WhatsAppMessage
from milkbasket.secret import RUN_ENVIRONMENT, DEV_NUMBER, WA_NUMBER_ID
from register.constant import DUE_TEMPLATE_ID
from register.constant import PAYMENT_TEMPLATE_ID
from register.forms import CustomerForm
from register.forms import RegisterForm
from register.models import Balance
from register.models import Customer
from register.models import Expense
from register.models import Income
from register.models import Payment
from register.models import Register
from register.models import Tenant
from register.utils import authenticate_alexa, get_customer_contact, send_wa_payment_notification, \
    get_whatsapp_media_by_id
from register.utils import check_customer_is_active
from register.utils import customer_register_last_updated
from register.utils import generate_bill
from register.utils import get_active_month
from register.utils import get_all_due_customer
from register.utils import get_bill_summary
from register.utils import get_customer_balance_amount
from register.utils import get_customer_due_amount
from register.utils import get_customer_due_amount_by_month
from register.utils import get_last_autopilot
from register.utils import get_last_transaction
from register.utils import get_milk_current_price
from register.utils import get_mongo_client
from register.utils import get_register_day_entry
from register.utils import get_tenant_perf
from register.utils import is_last_day_of_month
from register.utils import is_mobile
from register.utils import is_transaction_revertible
from register.utils import render_to_pdf
from register.utils import send_email_api
from register.utils import send_sms_api
from register.utils import send_whatsapp_message


@login_required
def index(request, year=None, month=None):
    # Get Tenant Preference
    tenant = get_tenant_perf(request)
    if tenant is None:
        return redirect('setting')
    template = 'register/register.html'
    context = {
        'page_title': 'Milk Basket - Register',
        'menu_register': True,
        'is_mobile': is_mobile(request),
    }
    custom_month = None
    active_customers = Customer.objects.filter(tenant_id=request.user.id, status=1)
    if year and month:
        date_time_str = f'01/{month}/{year} 01:01:01'
        custom_month = datetime.strptime(date_time_str, '%d/%m/%Y %H:%M:%S')
    register_date = custom_month if custom_month else date.today()
    # Get morning register for given month
    register = Register.objects.filter(tenant_id=request.user.id,
                                       log_date__month=register_date.month,
                                       log_date__year=register_date.year,
                                       schedule__in=['morning-yes', 'morning-no',
                                                     'e-morning']).values('customer_id',
                                                                          'customer__name',
                                                                          'customer__m_quantity').distinct()
    register_entry = Register.objects.filter(tenant_id=request.user.id,
                                             log_date__month=register_date.month,
                                             log_date__year=register_date.year,
                                             schedule__in=['morning-yes', 'morning-no',
                                                           'e-morning'])
    m_register = [{
        'customer_name': customer['customer__name'],
        'customer_id': customer['customer_id'],
        'register_entry': [re for re in register_entry if
                           re.customer_id == customer['customer_id']],
        'customer_m_quantity': customer['customer__m_quantity'],
        'default_price': tenant.milk_price,
        'is_active': check_customer_is_active(customer['customer_id']),
    } for customer in register]
    # Get evening register for given month
    register = Register.objects.filter(tenant_id=request.user.id,
                                       log_date__month=register_date.month,
                                       log_date__year=register_date.year,
                                       schedule__in=['evening-yes', 'evening-no',
                                                     'e-evening']).values('customer_id',
                                                                          'customer__name',
                                                                          'customer__e_quantity').distinct()
    register_entry = Register.objects.filter(tenant_id=request.user.id,
                                             log_date__month=register_date.month,
                                             log_date__year=register_date.year,
                                             schedule__in=['evening-yes', 'evening-no',
                                                           'e-evening'])
    e_register = [{
        'customer_name': customer['customer__name'],
        'customer_id': customer['customer_id'],
        'register_entry': [re for re in register_entry if
                           re.customer_id == customer['customer_id']],
        'customer_e_quantity': customer['customer__e_quantity'],
        'default_price': tenant.milk_price,
        'is_active': check_customer_is_active(customer['customer_id']),
    } for customer in register]

    # Get All customers if no entry is added - will be used in autopilot mode
    autopilot_morning_register, autopilot_evening_register = [], []
    if not e_register or not m_register:
        all_customers = Customer.objects.filter(tenant_id=request.user.id, status=1)
        autopilot_morning_register = [{
            'customer_name': customer.name,
            'customer_id': customer.id,
            'customer_m_quantity': customer.m_quantity,
        } for customer in all_customers if customer.morning]
        autopilot_evening_register = [{
            'customer_name': customer.name,
            'customer_id': customer.id,
            'customer_e_quantity': customer.e_quantity,
        } for customer in all_customers if customer.evening]

    # plot calendar days
    days = monthrange(register_date.year, register_date.month)
    month_year = register_date.strftime("%B, %Y")
    cal_days = range(1, days[1] + 1)

    # Get last entry date
    try:
        last_entry_date = Register.objects.filter(tenant_id=request.user.id,
                                                  log_date__month=register_date.month,
                                                  log_date__year=register_date.year).latest(
            'log_date__day')
        last_entry_date = int(last_entry_date.log_date.strftime("%d")) + 1
    except Register.DoesNotExist:
        last_entry_date = 1

    # Get only active customers not added on register
    all_register = m_register + e_register
    customer_in_register = set([c['customer_id'] for c in all_register])
    active_customers_not_in_register = [cust for cust in active_customers if
                                        cust.id not in customer_in_register]

    context.update({
        'month_year': month_year,
        'm_register': m_register,
        'e_register': e_register,
        'today_day': date.today().day,
        'last_entry_day': last_entry_date,
        'days': cal_days,
        'max_date': f'{date.today().year}-{date.today().month}-{days[1]}',
        'active_customers': active_customers,
        'default_price': tenant.milk_price,
        'autopilot_morning_register': autopilot_morning_register,
        'autopilot_evening_register': autopilot_evening_register,
        'active_customers_not_in_register': active_customers_not_in_register,
    })
    return render(request, template, context)


# --- ************************** -----
# --- Experimental Alexa Feature -----
# --- ************************** -----

def alexa_get_last_autopilot(request):
    unauthorised = authenticate_alexa(request)
    if unauthorised:
        return unauthorised
    today = date.today()
    last_date = today.replace(day=get_last_autopilot())
    return JsonResponse({'status': 'success',
                         'last_date': last_date,
                         'is_allowed': True if last_date <= today else False,
                         })


def alexa_customer_list(request):
    unauthorised = authenticate_alexa(request)
    if unauthorised:
        return unauthorised
    customers_qs = Customer.objects.filter(tenant=2)
    all_customers = [{'id': c.id, 'name': c.name, 'is_active': any([c.m_quantity, c.e_quantity])}
                     for c in customers_qs]
    return JsonResponse({'status': 'success',
                         'all_customers': all_customers
                         })


def alexa_customer_due(request):
    unauthorised = authenticate_alexa(request)
    if unauthorised:
        return unauthorised
    customer = Customer.objects.filter(pk=request.GET.get("cust_id")).first()
    if customer:
        total_due, prev_month_due, adv = get_customer_due_amount(customer)
        return JsonResponse({'status': 'success',
                             'name': customer.name,
                             'total_due': total_due,
                             'prev_month_due': prev_month_due,
                             'advance': adv
                             })
    return JsonResponse({'status': 'failed',
                         'message': 'unable to find customer'
                         })


def alexa_run_autopilot(request):
    unauthorised = authenticate_alexa(request)
    if unauthorised:
        return unauthorised
    tenant_id = 2  # todo set for all tenants when auth is added
    tenant = Tenant.objects.get(tenant_id=tenant_id)
    today = datetime.today().replace(microsecond=0)

    m_register = Register.objects.filter(tenant=tenant,
                                         log_date__month=today.month,
                                         log_date__year=today.year,
                                         customer__status=1,
                                         schedule__in=['morning-yes', 'morning-no',
                                                       'e-morning']).values('customer_id',
                                                                            'customer__m_quantity').distinct()
    e_register = Register.objects.filter(tenant=tenant,
                                         log_date__month=today.month,
                                         log_date__year=today.year,
                                         customer__status=1,
                                         schedule__in=['evening-yes', 'evening-no',
                                                       'e-evening']).values('customer_id',
                                                                            'customer__e_quantity').distinct()
    m_register = [{
        'customer_id': customer['customer_id'],
        'schedule': 'morning',
        'quantity': customer['customer__m_quantity'],
    } for customer in m_register]
    e_register = [{
        'customer_id': customer['customer_id'],
        'schedule': 'evening',
        'quantity': customer['customer__e_quantity'],
    } for customer in e_register]
    if not e_register or not m_register:
        all_customers = Customer.objects.filter(tenant=tenant, status=1)
        m_register = [{
            'customer_id': customer.id,
            'schedule': 'morning',
            'quantity': customer.m_quantity,
        } for customer in all_customers if customer.morning]
        e_register = [{
            'customer_id': customer.id,
            'schedule': 'evening',
            'quantity': customer.e_quantity,
        } for customer in all_customers if customer.evening]

    autopilot_data = m_register + e_register

    start_date = today.replace(day=get_last_autopilot())
    delta = today - start_date
    for i in range(delta.days + 1):
        day = start_date + timedelta(days=i)
        for cust in autopilot_data:
            full_log_date = datetime.strptime(str(day), '%Y-%m-%d %H:%M:%S')
            record_exists = Register.objects.filter(tenant=tenant_id,
                                                    customer_id=cust['customer_id'],
                                                    log_date=full_log_date,
                                                    schedule__startswith=cust['schedule']).first()
            if not record_exists and cust['quantity']:
                entry = Register(tenant=tenant, customer_id=cust['customer_id'],
                                 log_date=full_log_date, schedule=f'{cust["schedule"]}-yes',
                                 quantity=cust['quantity'], current_price=tenant.milk_price)
                entry.save()

    return JsonResponse({'status': 'success',
                         'message': 'Autopilot completed'
                         })


# --- Experimental Alexa Feature -----^^^^^^


@login_required
def add_customer(request):
    # Get Tenant Preference
    tenant = get_tenant_perf(request)
    if tenant is None:
        return redirect('setting')
    template = 'register/customer.html'
    context = {
        'page_title': 'Milk Basket - Add new customer',
        'menu_customer': True,
        'is_mobile': is_mobile(request),
    }
    if request.method == "POST":
        customer_id = request.POST.get("id", None)
        no_redirect = request.POST.get("redirect_url", False)
        customer_contact, customer_email, customer_morning, customer_evening, m_quantity, e_quantity = '', '', '', '', '', ''
        if customer_id:
            customer_name = Customer.objects.filter(id=customer_id).first()
            customer_contact = request.POST.get("contact")
            customer_email = request.POST.get("email")
            customer_morning = True if request.POST.get("morning", False) else False
            customer_evening = True if request.POST.get("evening", False) else False
            m_quantity = request.POST.get("m_quantity", None) if customer_morning else None
            e_quantity = request.POST.get("e_quantity", None) if customer_evening else None
            if not customer_morning and not customer_evening:
                Customer.objects.filter(tenant_id=request.user.id, id=customer_id).update(
                    contact=customer_contact,
                    email=customer_email,
                    morning=customer_morning,
                    evening=customer_evening,
                    m_quantity=m_quantity,
                    e_quantity=e_quantity,
                    status=0)
                messages.add_message(request, messages.WARNING,
                                     f'You have deactivated {customer_name.name}')
            else:
                Customer.objects.filter(tenant_id=request.user.id, id=customer_id).update(
                    contact=customer_contact,
                    email=customer_email,
                    morning=customer_morning,
                    evening=customer_evening,
                    m_quantity=m_quantity,
                    e_quantity=e_quantity,
                    status=1)
                messages.add_message(request, messages.SUCCESS,
                                     f'Customer details updated successfully for {customer_name.name}')
        else:
            form = CustomerForm(request.POST)
            name = form['name'].value()
            contact = form['contact'].value()
            email = form['email'].value()
            morning = form['morning'].value() or False
            evening = form['evening'].value() or False
            m_quantity = form['m_quantity'].value() or None
            e_quantity = form['e_quantity'].value() or None
            if not morning and not evening:
                customer = Customer(tenant_id=request.user.id, name=name, contact=contact,
                                    email=email, morning=morning,
                                    evening=evening, m_quantity=m_quantity, e_quantity=e_quantity,
                                    status=0)
                messages.add_message(request, messages.WARNING,
                                     f'New Customer {name} added successfully, but is inactive at the moment')
            else:
                customer = Customer(tenant_id=request.user.id, name=name, contact=contact,
                                    email=email, morning=morning,
                                    evening=evening, m_quantity=m_quantity, e_quantity=e_quantity,
                                    status=1)
                messages.add_message(request, messages.SUCCESS,
                                     f'New Customer {name} added successfully')

            try:
                customer.save()
            except Exception as E:
                list(messages.get_messages(request))
                messages.add_message(request, messages.ERROR,
                                     f'Something went wrong, we could not add customer')
        if no_redirect:
            m_quantity_text = f'{m_quantity} ML (Morning).' if m_quantity else ''
            e_quantity_text = f'{e_quantity} ML (Evening).' if e_quantity else ''
            return JsonResponse({'status': 'success',
                                 'contact': customer_contact,
                                 'email': customer_email,
                                 'schedule_morning': customer_morning,
                                 'schedule_evening': customer_evening,
                                 'm_quantity': m_quantity,
                                 'e_quantity': e_quantity,
                                 'quantity': m_quantity_text + e_quantity_text,
                                 })
        else:
            return redirect('view_customers')
    else:
        return render(request, template, context)


@login_required
def addentry(request, year=None, month=None):
    # Get Tenant Preference
    tenant = get_tenant_perf(request)
    if tenant is None:
        return redirect('setting')
    if request.method == "POST":

        yes_or_no = ''
        reload_status = False
        extended_data = None
        schedule = None
        if request.POST.get("add-new-entry", None):
            customer = request.POST.get("customer", None)
            customer_info = Customer.objects.filter(tenant_id=request.user.id, id=customer,
                                                    status=1).first()
            log_date = request.POST.get("log_date", None)
            full_log_date = datetime.strptime(log_date, '%Y-%m-%d')
            current_price = tenant.milk_price
            # check if entry exists for give day and schedule
            entry = None
            if customer_info.morning:
                check_record = Register.objects.filter(tenant_id=request.user.id,
                                                       customer_id=customer,
                                                       log_date=full_log_date,
                                                       schedule__startswith='morning-yes').first()
                if not check_record:
                    entry = Register(tenant_id=request.user.id, customer_id=customer_info.id,
                                     log_date=full_log_date,
                                     schedule='morning-yes',
                                     quantity=customer_info.m_quantity,
                                     current_price=current_price)
                    entry.save()
            if customer_info.evening:
                check_record = Register.objects.filter(tenant_id=request.user.id,
                                                       customer_id=customer,
                                                       log_date=full_log_date,
                                                       schedule__startswith='evening-yes').first()
                if not check_record:
                    entry = Register(tenant_id=request.user.id, customer_id=customer_info.id,
                                     log_date=full_log_date,
                                     schedule='evening-yes',
                                     quantity=customer_info.e_quantity,
                                     current_price=current_price)
                    entry.save()
            entry_status = True if entry is not None else False
            reload_status = True
        else:
            form = RegisterForm(request.POST)
            customer = request.POST.get("id", None)
            log_date = request.POST.get("log_date", None)
            full_log_date = datetime.strptime(log_date, '%d %B, %Y')
            attendance = request.POST.get("attendance", 0)
            yes_or_no = 'yes' if int(attendance) else 'no'
            schedule = request.POST.get("schedule", 'morning').lower()
            full_schedule = f'{schedule.lower()}-{yes_or_no}'
            quantity = form['quantity'].value() or False
            current_price = tenant.milk_price

            # check if entry exists for give day and schedule

            check_record = Register.objects.filter(tenant_id=request.user.id, customer_id=customer,
                                                   log_date=full_log_date,
                                                   schedule__startswith=schedule).first()
            cust = Customer.objects.get(id=customer)
            extended_data = {'customer_name': cust.name}
            if not check_record:
                entry = Register(tenant_id=request.user.id, customer_id=customer,
                                 log_date=full_log_date,
                                 schedule=full_schedule,
                                 quantity=quantity, current_price=current_price)
                entry.save()
                entry_status = True if entry.id else False
            else:
                check_record.schedule = full_schedule
                check_record.quantity = quantity
                check_record.save()
                entry_status = True if check_record.id else False

            if full_schedule.endswith("-yes"):
                extended_data.update({'quantity': f'{quantity} ML'})
            else:
                extended_data.update({'quantity': 'Absent'})

        data = {
            'return': entry_status,
            'cell': f'{schedule}_{customer}_{full_log_date.day}',
            'classname': 'cal-yes' if 'yes' in yes_or_no else 'cal-no',
            'classnameRemove': 'cal-no' if 'yes' in yes_or_no else 'cal-yes',
            'logDate': full_log_date.strftime('%d %b'),
            'reload': reload_status,
        }
        if extended_data:
            data.update(extended_data)

        return JsonResponse(data)

    if year and month:
        month = month if len(str(month)) > 1 else f'0{month}'
        return redirect(f'/milkbasket/{year}/{month}/')
    else:
        return redirect('index')


@login_required
@transaction.atomic()
def autopilot(request, year=None, month=None):
    # Get Tenant Preference
    tenant = get_tenant_perf(request)
    if tenant is None:
        return redirect('setting')
    if request.method == "POST":
        current_price = tenant.milk_price
        autopilot_data = []
        # Get autopilot form data
        for key in request.POST:
            value = request.POST[key]
            if value == 'on':
                auto = {
                    'id': key.split('-')[0],
                    'schedule': key.split('-')[1],
                }
                autopilot_data.append(auto)
        log_month = request.POST.get("log_month", None)
        start_date = request.POST['start']
        start = datetime.strptime(f'{start_date}-{log_month}', '%d-%B, %Y')
        end_date = request.POST['end']
        end = datetime.strptime(f'{end_date}-{log_month}', '%d-%B, %Y')

        if int(end_date) < int(start_date):
            response = {
                'showmessage': True,
                'message': f'You have selected {start_date} start and {end_date} end date. End date can not be before start date.',
                'status': False,
            }
            return JsonResponse(response)
        delta = end - start  # as timedelta
        for i in range(delta.days + 1):
            day = start + timedelta(days=i)
            print(day)
            for cust in autopilot_data:
                customer = Customer.objects.filter(tenant_id=request.user.id,
                                                   id=cust['id']).first()
                full_log_date = datetime.strptime(str(day), '%Y-%m-%d %H:%M:%S')
                check_record = Register.objects.filter(tenant_id=request.user.id,
                                                       customer_id=customer.id,
                                                       log_date=full_log_date,
                                                       schedule__startswith=cust[
                                                           'schedule']).first()
                add_quantity = customer.m_quantity if cust[
                                                          "schedule"] == 'morning' else customer.e_quantity
                if not check_record and add_quantity:
                    full_schedule = f'{cust["schedule"]}-yes'
                    entry = Register(tenant_id=request.user.id, customer_id=customer.id,
                                     log_date=full_log_date,
                                     schedule=full_schedule,
                                     quantity=add_quantity,
                                     current_price=current_price)
                    entry.save()
                else:
                    print('Skipping: ', customer.name, 'Day: ', day)

        response = {
            'showmessage': False,
            'message': f'Success',
            'return': True,
            'reload': True,
        }
        messages.add_message(request, messages.SUCCESS,
                             f'Autopilot completed from {start_date} to {end_date} {log_month}')
        return JsonResponse(response)
    # return invalid response if already not returned data
    response = {
        'showmessage': True,
        'message': 'Invalid Request',
        'return': False,
    }
    return JsonResponse(response)


@login_required
def customers(request):
    # Get Tenant Preference
    tenant = get_tenant_perf(request)
    if tenant is None:
        return redirect('setting')
    template = 'register/customer.html'
    context = {
        'page_title': 'Milk Basket - View customers',
        'menu_customer': True,
        'is_mobile': is_mobile(request),
    }
    customers = Customer.objects.filter(tenant_id=request.user.id, status=1)
    for customer in customers:

        # TODO: Fix os path issue
        # Creating an instance of qrcode
        # qr = qrcode.QRCode(
        #     version=1,
        #     box_size=10,
        #     border=1)
        # qr.add_data(customer.id)
        # qr.make(fit=True)
        # img = qr.make_image(fill='black', back_color='white')
        # img.save(f'register/static/qrcode{customer.id}.png')
        # customer.img = f'/static/qrcode{customer.id}.png'

        if customer.morning and not customer.evening:
            customer.schedule = 'Morning'
        if not customer.morning and customer.evening:
            customer.schedule = 'Evening'
        if customer.morning and customer.evening:
            customer.schedule = 'Morning and Evening'

        # Add total Milk Quantity
        customer.quantity = (customer.m_quantity or 0) + (customer.e_quantity or 0)

    inactive_customers = Customer.objects.filter(tenant_id=request.user.id, status=0)
    for customer in inactive_customers:
        customer.contact = customer.contact if customer.contact else ''
        if customer.morning and not customer.evening:
            customer.schedule = 'Morning'
        if not customer.morning and customer.evening:
            customer.schedule = 'Evening'
        if customer.morning and customer.evening:
            customer.schedule = 'Morning and Evening'

    context.update({
        'customers': customers,
        'inactive_customers': inactive_customers,
        'tenant': tenant
    })

    return render(request, template, context)


@login_required
def account(request, year=None, month=None):
    tenant = get_tenant_perf(request)
    if tenant is None:
        return redirect('setting')
    template = 'register/account.html'
    custom_month = None
    last_day_of_month = is_last_day_of_month()
    current_date = date.today()
    if year and month:
        date_time_str = f'01/{month}/{year} 01:01:01'
        custom_month = datetime.strptime(date_time_str, '%d/%m/%Y %H:%M:%S')
    register_date = custom_month if custom_month else date.today()

    # Get expenses
    total_expense = 0
    expenses = Expense.objects.filter(tenant_id=request.user.id, log_date__year=register_date.year,
                                      log_date__month=register_date.month)
    for exp in expenses:
        exp.log_date = exp.log_date.strftime("%b %d")
        total_expense += exp.cost
    month_year = register_date.strftime("%B, %Y")

    # Get Payment Due
    total_payment = 0
    due_customer = Register.objects.filter(tenant_id=request.user.id, schedule__endswith='yes',
                                           paid=0).values('customer_id',
                                                          'customer__name',
                                                          'customer__contact',
                                                          'customer__email').distinct()
    for customer in due_customer:
        payment_due = Register.objects.filter(tenant_id=request.user.id,
                                              customer_id=customer['customer_id'],
                                              schedule__endswith='yes', paid=0)
        payment_due_amount = 0
        for due in payment_due:
            payment_due_amount += (due.current_price / 1000 * decimal.Decimal(float(due.quantity)))
        balance_amount = Balance.objects.filter(tenant_id=request.user.id,
                                                customer_id=customer['customer_id']).first()
        customer['adjusted_amount'] = getattr(balance_amount,
                                              'balance_amount') if balance_amount else 0
        customer['payment_due'] = round(payment_due_amount, 2) - abs(customer['adjusted_amount'])
        due_prev_month = Register.objects.filter(tenant_id=request.user.id,
                                                 customer_id=customer['customer_id'],
                                                 schedule__endswith='yes', paid=0).exclude(
            log_date__month=current_date.month, log_date__year=current_date.year)
        due_prev_month_amount = 0
        for due in due_prev_month:
            due_prev_month_amount += (
                due.current_price / 1000 * decimal.Decimal(float(due.quantity)))
        customer['payment_due_prev'] = round(due_prev_month_amount, 2) - abs(
            customer['adjusted_amount'])

        total_payment += payment_due_amount

        # Due sms text
        prev_month_name = (current_date + relativedelta(months=-1)).strftime("%B")
        current_month_name = current_date.strftime("%B")
        month_and_amount = (
            f"{prev_month_name} is Rs {customer['payment_due_prev']}") if customer[
                                                                              'payment_due_prev'] > 0 and not last_day_of_month else (
            f"{current_month_name} is Rs {customer['payment_due']}")
        customer[
            'sms_text'] = f"Dear {customer['customer__name']},\nTotal due amount for the month of {month_and_amount}.\n[Milk Basket]"

    # Get paid customer
    paid_customer = Register.objects.filter(tenant_id=request.user.id, schedule__endswith='yes',
                                            paid=1).values('customer_id',
                                                           'customer__name').distinct()
    for customer in paid_customer:
        payment_done = Register.objects.filter(tenant_id=request.user.id,
                                               customer_id=customer['customer_id'],
                                               schedule__endswith='yes', paid=1)
        accepted_amount = 0
        for due in payment_done:
            accepted_amount += (due.current_price / 1000 * decimal.Decimal(float(due.quantity)))
        balance_amount = Balance.objects.filter(tenant_id=request.user.id,
                                                customer_id=customer['customer_id']).first()
        customer['adjusted_amount'] = getattr(balance_amount,
                                              'balance_amount') if balance_amount else 0
        paid_amount = Payment.objects.filter(tenant_id=request.user.id,
                                             customer_id=customer['customer_id'],
                                             log_date__month=register_date.month,
                                             log_date__year=register_date.year).aggregate(
            Sum('amount'))
        customer['payment_done'] = accepted_amount
        customer['total_paid'] = paid_amount['amount__sum']

    # Get extra income
    income = Income.objects.filter(tenant_id=request.user.id, log_date__year=register_date.year,
                                   log_date__month=register_date.month)
    for inc in income:
        inc.log_date = inc.log_date.strftime("%b %d")

    context = {
        'page_title': 'Milk Basket - Accounts',
        'is_mobile': is_mobile(request),
        'month_year': month_year,
        'menu_account': True,
        'expenses': expenses,
        'entry_expense_total': sum([float(entry.cost) for entry in expenses]),
        'income': income,
        'entry_income_total': sum([float(entry.amount) for entry in income]),
        'total_payment': total_payment,
        'total_expense': total_expense,
        'due_customer': due_customer,
        'due_total': sum([float(entry['payment_due']) for entry in due_customer]),
        'due_total_prev': sum([float(entry['payment_due_prev']) for entry in due_customer]),
        'paid_customer': [cust for cust in paid_customer if cust['total_paid']],
        'reveieved_total': sum(
            [cust['total_paid'] for cust in paid_customer if cust['total_paid']]),
        'previous_month_name': (current_date + relativedelta(months=-1)).strftime("%B"),
        'tenant': tenant,
    }

    return render(request, template, context)


@login_required
def daterange(date1, date2):
    for n in range(int((date2 - date1).days) + 1):
        yield date1 + timedelta(n)


@login_required
def selectrecord(request):
    formatted_url = '#'
    full_register_date = request.POST.get("register_month", None)
    register_month = str(full_register_date).split("-")[1]
    register_year = str(full_register_date).split("-")[0]
    nav_url = request.POST.get("nav-type", None)
    if nav_url == 'register':
        formatted_url = reverse('view_register_month', args=[register_year, register_month])
    elif nav_url == 'account':
        formatted_url = reverse('account_month', args=[register_year, register_month])
    return redirect(formatted_url)


@login_required
def manage_expense(request, year=None, month=None):
    expense_date = datetime.now()
    formatted_url = reverse('view_account')
    if year and month:
        date_time_str = f'25/{month}/{year} 01:01:01'
        expense_date = datetime.strptime(date_time_str, '%d/%m/%Y %H:%M:%S')
        formatted_url = reverse('account_month', args=[year, month])
    delete_id = request.POST.get("id", None)
    if delete_id:
        Expense.objects.filter(tenant_id=request.user.id, id=delete_id).delete()
        messages.add_message(request, messages.WARNING, 'Expense entry has been deleted')
    add_expense = request.POST.get("month_year", None)
    if add_expense:
        cost = request.POST.get("cost_amount", None)
        desc = request.POST.get("exp_desc", None)
        new_expense = Expense(tenant_id=request.user.id, cost=cost, description=desc,
                              log_date=expense_date)
        try:
            new_expense.save()
            messages.add_message(request, messages.SUCCESS,
                                 f'Expense entry of Rs. {cost} for {desc} added successfully')
        except ValidationError as e:
            template = 'register/errors/custom_error_page.html'
            context = {'page_title': 'Error - MilkBasket',
                       'error_code': 'Error!',
                       'error_msg': 'Please fill all the fields before submitting'}
            return render(request, template, context)

    return redirect(formatted_url)


@login_required
def manage_income(request, year=None, month=None):
    income_date = datetime.now()
    formatted_url = reverse('view_account')
    if year and month:
        date_time_str = f'25/{month}/{year} 01:01:01'
        income_date = datetime.strptime(date_time_str, '%d/%m/%Y %H:%M:%S')
        formatted_url = reverse('account_month', args=[year, month])
    delete_id = request.POST.get("id", None)
    if delete_id:
        Income.objects.filter(tenant_id=request.user.id, id=delete_id).delete()
        messages.add_message(request, messages.WARNING, 'Income entry has been deleted')
    add_income = request.POST.get("month_year", None)
    if add_income:
        amount = request.POST.get("income_amount", None)
        desc = request.POST.get("exp_desc", None)
        new_income = Income(tenant_id=request.user.id, amount=amount, description=desc,
                            log_date=income_date)
        try:
            new_income.save()
            messages.add_message(request, messages.SUCCESS,
                                 f'Income entry of Rs. {amount} for {desc} added successfully')
        except ValidationError as e:
            template = 'register/errors/custom_error_page.html'
            context = {'page_title': 'Error - MilkBasket',
                       'error_code': 'Error!',
                       'error_msg': 'Please fill all the fields before submitting'}
            return render(request, template, context)
    return redirect(formatted_url)


@login_required
@transaction.atomic
def accept_payment(request, year=None, month=None, return_url=None):
    # Update Payment Table
    return_url = request.POST.get("return_url", None)
    c_id = request.POST.get("c_id", None)
    formatted_url = reverse('view_account') if not return_url else f'/milkbasket/{return_url}'
    if year and month:
        formatted_url = reverse('account_month', args=[year, month])

    payment_amount = request.POST.get("c_payment", None)
    sms_notification = request.POST.get("sms-notification", None)
    if c_id and payment_amount:
        customer = Customer.objects.filter(tenant_id=request.user.id, id=c_id).first()
        payment_amount = float(payment_amount)
        new_payment = Payment(tenant_id=request.user.id, customer_id=c_id, amount=payment_amount)
        try:
            new_payment.save()
            messages.add_message(request, messages.SUCCESS,
                                 f'Payment of Rs. {payment_amount} received from {customer.name}')
        except:
            messages.add_message(request, messages.ERROR,
                                 'Could not process payment of Rs. {payment_amount} from {customer.name}')
            return redirect(formatted_url)
        balance_amount, _ = Balance.objects.get_or_create(tenant_id=request.user.id,
                                                          customer_id=c_id)
        adjust_amount = float(getattr(balance_amount, 'balance_amount')) if balance_amount else 0
        # Set advance to old bal
        balance_amount.balance_amount = 0
        balance_amount.last_balance_amount = adjust_amount
        balance_amount.save()
        # Get total amount in hand
        payment_amount = payment_amount + abs(adjust_amount)
        # Update Register
        accepting_payment = Register.objects.filter(tenant_id=request.user.id, customer_id=c_id,
                                                    schedule__endswith='yes',
                                                    paid=0).order_by('log_date')
        for entry in accepting_payment:
            if payment_amount > 0:
                entry_cost = float(
                    entry.current_price / 1000 * decimal.Decimal(float(entry.quantity)))
                if payment_amount - entry_cost >= 0:
                    Register.objects.filter(tenant_id=request.user.id, id=entry.id).update(
                        paid=True, transaction_number=new_payment)
                    payment_amount = payment_amount - entry_cost
                elif payment_amount != 0:
                    Balance.objects.update_or_create(tenant_id=request.user.id,
                                                     customer_id=c_id,
                                                     defaults={"balance_amount": payment_amount}
                                                     )
                    payment_amount = 0

        if payment_amount != 0:
            Balance.objects.update_or_create(tenant_id=request.user.id,
                                             customer_id=c_id,
                                             defaults={"balance_amount": -payment_amount}
                                             )
            messages.add_message(request, messages.INFO,
                                 f'Rs. {payment_amount} is added as Balance')

        # Send SMS notification
        if sms_notification:
            transaction_time = datetime.now().strftime('%d-%m-%Y %I:%M:%p')
            sms_text = f'Dear {customer.name},\nPayment of Rs {new_payment.amount} received on {transaction_time}. Transaction #{new_payment.id}.\nThanks,\n[Milk Basket]'
            send_sms_api(customer.contact, sms_text, PAYMENT_TEMPLATE_ID)
            send_wa_payment_notification(customer.contact, customer.name, new_payment.amount,
                                         transaction_time, new_payment.id)

    return redirect(formatted_url)


@login_required
@transaction.atomic
def revert_transaction(request):
    c_id = request.POST.get("c_id")
    customer = Customer.objects.filter(tenant_id=request.user.id, id=c_id).first()
    bal = Balance.objects.filter(customer=customer).exclude(last_balance_amount=None).first()
    status = {'status': 'failed', 'error': 'Transaction is not revertible'}
    if bal:
        try:
            # assign old bal to current bal and set old bal null
            Balance.objects.filter(customer=customer).update(
                balance_amount=bal.last_balance_amount, last_balance_amount=None)
            # get last transaction number
            transaction_number = get_last_transaction(request, customer)
            # Update Register - set transaction null and paid false
            Register.objects.filter(customer=customer,
                                    transaction_number=transaction_number).update(
                transaction_number=None, paid=False)
            # Delete Payment
            Payment.objects.filter(id=transaction_number.id).delete()
            status = {'status': 'success',
                      'error': f'Transaction #{transaction_number.id} was reverted successfully'}
            messages.add_message(request, messages.WARNING,
                                 f'Transaction #{transaction_number.id} was reverted successfully')
        except Exception as e:
            status = {'status': 'failed',
                      'error': f'Error occurred while reverting transactions {e}'}
            messages.add_message(request, messages.ERROR,
                                 f'Error occurred while reverting transactions {e}')

    return JsonResponse(status)


def landing(request):
    template = 'register/landing.html'
    context = {
        'page_title': 'Milk Basket - View customers',
        'is_mobile': is_mobile(request),
    }
    if request.method == "POST":
        username = request.POST.get("username")
        username = username.lower()
        password = request.POST.get("password")
        user = authenticate(username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect('view_register')
        else:
            customer = Customer.objects.filter(contact=username).first()
            if customer.name == password:
                request.session['customer_session'] = True
                request.session['customer'] = customer.id
                request.session.save()
                return redirect('customer_dashboard')
            context.update({
                'message': 'Invalid username or password',
            })
    return render(request, template, context)


@login_required
def report_initial(request):
    template = 'register/report_react_new.html'
    context = {'loading': True,
               'page_title': 'Milk Basket - Report',
               'is_mobile': is_mobile(request),
               'menu_report': True,
               'protocol': 'https' if RUN_ENVIRONMENT == 'production' else 'http'
               }
    return render(request, template, context)


@login_required
def report_data_status(request, poll_id=None):
    retry = 30
    status = None
    while retry:
        status = {'status': request.session.get(poll_id, None),
                  'percent': request.session.get(f'{poll_id}_percent')
                  }
        if status:
            return JsonResponse(status)
        else:
            retry -= 1
    return JsonResponse(status)


@login_required
def report_data(request, poll_id=None):
    chart_data = []
    d1 = date.today()
    percent = 0
    milk_delivered = ['morning-yes', 'evening-yes']
    for i in range(-12, 1):
        percent += 3.75
        graph_month = d1 + relativedelta(months=i)
        request.session[poll_id] = f'Income and Expense ({graph_month.strftime("%B-%Y")})'
        request.session[f'{poll_id}_percent'] = percent
        request.session.save()
        # Fetch Expenses
        month_expense = \
            Expense.objects.filter(tenant_id=request.user.id, log_date__month=graph_month.month,
                                   log_date__year=graph_month.year).aggregate(
                Sum('cost'))['cost__sum'] or 0

        # Fetch Income
        month_income = 0
        month_extra_income = float(
            Income.objects.filter(tenant_id=request.user.id, log_date__month=graph_month.month,
                                  log_date__year=graph_month.year).aggregate(
                Sum('amount'))['amount__sum'] or 0)
        month_income += month_extra_income
        month_income_entry = Register.objects.filter(tenant_id=request.user.id,
                                                     log_date__month=graph_month.month,
                                                     log_date__year=graph_month.year,
                                                     schedule__in=milk_delivered)
        for entry in month_income_entry:
            month_income += float(entry.current_price / 1000) * entry.quantity

        # Fetch due per month
        month_due = 0
        month_due_entry = Register.objects.filter(tenant_id=request.user.id,
                                                  log_date__month=graph_month.month,
                                                  log_date__year=graph_month.year, paid=0,
                                                  schedule__in=milk_delivered)
        for entry in month_due_entry:
            month_due += float(entry.current_price / 1000) * entry.quantity

        # Fetch paid per month
        month_paid = 0
        month_paid += month_extra_income
        month_paid_entry = Register.objects.filter(tenant_id=request.user.id,
                                                   log_date__month=graph_month.month,
                                                   log_date__year=graph_month.year, paid=1)
        for entry in month_paid_entry:
            month_paid += float(entry.current_price / 1000) * entry.quantity

        # Calculate Profit and Loss value
        if month_paid > month_expense:
            profit = float(month_paid) - float(month_expense)
            loss = False
        else:
            loss = float(month_expense) - float(month_paid)
            profit = False

        current_month = {
            "monthName": graph_month.strftime('%B-%Y'),
            "month": graph_month.strftime('%b-%y'),
            "income": round(float(month_income), 2),
            "paid": round(float(month_paid), 2),
            "due": round(float(month_due), 2),
            "expense": round(float(month_expense), 2),
            "profit": profit,
            "loss": loss,
        }
        chart_data.append(current_month)

    #     Get milk production over past 365 days
    chart_data_milk = []
    all_register_entry = Register.objects.filter(tenant_id=request.user.id)
    all_milk_production = [{'quantity': x.quantity, 'schedule': x.schedule, 'log_date': x.log_date}
                           for x in all_register_entry]
    for i in range(-365, 1):
        percent += 0.123
        d1 = date.today()
        graph_day = d1 + relativedelta(days=i)
        request.session[poll_id] = f'Milk Production ({graph_day.strftime("%d-%B-%Y")})'
        request.session[f'{poll_id}_percent'] = percent
        request.session.save()
        milk_production_morning = sum(item['quantity'] for item in all_milk_production if
                                      item['schedule'] == 'morning-yes' and item[
                                          'log_date'].date() == graph_day)
        milk_production_evening = sum(item['quantity'] for item in all_milk_production if
                                      item['schedule'] == 'evening-yes' and item[
                                          'log_date'].date() == graph_day)

        current_day = {
            "dayName": graph_day.strftime('%d-%B-%Y'),
            'milkMorning': round(float(milk_production_morning / 1000), 2),
            'milkEvening': round(float(milk_production_evening / 1000), 2),
            "milkQuantity": round(float(milk_production_morning / 1000), 2) + round(
                float(milk_production_evening / 1000), 2),
        }
        chart_data_milk.append(current_day)

    percent += 5
    request.session[f'{poll_id}_percent'] = percent
    request.session.save()
    # Calculate all time Expenses
    all_time_expense = Expense.objects.filter(tenant_id=request.user.id).aggregate(Sum('cost'))[
                           'cost__sum'] or 0

    # Calculate all time Income
    all_time_milk_income = \
        Payment.objects.filter(tenant_id=request.user.id).aggregate(Sum('amount'))[
            'amount__sum'] or 0
    all_time_extra_income = \
        Income.objects.filter(tenant_id=request.user.id).aggregate(Sum('amount'))[
            'amount__sum'] or 0
    all_time_income = all_time_milk_income + all_time_extra_income

    # Calculate all time profit or loss
    is_profit = True if all_time_expense < all_time_income else False
    all_time_profit_or_loss = abs(all_time_income - all_time_expense)
    percent += 5
    request.session[f'{poll_id}_percent'] = percent
    request.session.save()
    due_list, due_month = get_customer_due_amount_by_month(request)
    context = {
        'graph_data': mark_safe(json.dumps(chart_data)),
        'table_data': chart_data,
        'chart_data_milk': mark_safe(json.dumps(chart_data_milk)),
        'all_time_expense': all_time_expense,
        'all_time_income': all_time_income,
        'is_profit': is_profit,
        'all_time_profit_or_loss': all_time_profit_or_loss,
        'due_customers': mark_safe(json.dumps(due_list)),
        'due_month': mark_safe(json.dumps(due_month)),
    }
    request.session[poll_id] = 'Done'
    request.session.save()
    return JsonResponse(context)


@login_required
def setting(request):
    template = 'register/setting.html'
    if request.method == "POST":
        milk_price = float(request.POST.get("milkprice"))
        sms_pref = True if request.POST.get("sms_pref") else False
        wa_pref = True if request.POST.get("wa_pref") else False
        wa_direct_pref = True if request.POST.get("wa_direct_pref") else False
        email_pref = True if request.POST.get("email_pref") else False
        bill_till_date = True if request.POST.get("bill_till_date") else False
        customers_bill_access = True if request.POST.get("customers_bill_access") else False
        accept_online_payment = True if request.POST.get("accept_online_payment") else False
        download_pdf_pref = True if request.POST.get("download_pdf_pref") else False
        now = datetime.now()
        tenant, created = Tenant.objects.update_or_create(tenant_id=request.user.id,
                                                          defaults={'sms_pref': sms_pref,
                                                                    'whatsapp_pref': wa_pref,
                                                                    'whatsapp_direct_pref': wa_direct_pref,
                                                                    'email_pref': email_pref,
                                                                    'bill_till_date': bill_till_date,
                                                                    'customers_bill_access': customers_bill_access,
                                                                    'accept_online_payment': accept_online_payment,
                                                                    'download_pdf_pref': download_pdf_pref},
                                                          )
        saved_milk_price = tenant.milk_price if tenant.milk_price else None
        if created or saved_milk_price != milk_price:
            Tenant.objects.filter(tenant_id=request.user.id).update(milk_price=milk_price,
                                                                    date_effective=now)

        request.session['alert_class'] = 'success'
        request.session['alert_message'] = 'Settings Saved'
        messages.add_message(request, messages.SUCCESS, 'Settings updated successfully')

    try:
        tenant = Tenant.objects.get(tenant_id=request.user.id)
    except Tenant.DoesNotExist:
        tenant = None
    context = {
        'page_title': 'Milk Basket - Setting',
        'is_mobile': is_mobile(request),
        'menu_setting': True,
        'tenant': tenant,
        'alert_class': request.session.get('alert_class', None),
        'alert_message': request.session.get('alert_message', None),
    }
    try:
        del request.session['alert_class']
        del request.session['alert_message']
    except:
        pass
    return render(request, template, context)


@login_required
def logout_request(request):
    logout(request)
    return redirect('view_register')


@login_required
def customer_profile(request, id=None):
    template = 'register/profile.html'
    context = {
        'is_mobile': is_mobile(request),
        'page_title': 'Milk Basket - Profile',
    }
    current_date = date.today()
    if id:
        customer = Customer.objects.filter(tenant_id=request.user.id, id=id).first()
        if not customer:
            return render(request, template, context={'nocustomer': True})
        transaction = Payment.objects.filter(tenant_id=request.user.id, customer_id=id)

        if customer.morning and not customer.evening:
            customer.schedule = 'Morning'
        if not customer.morning and customer.evening:
            customer.schedule = 'Evening'
        if customer.morning and customer.evening:
            customer.schedule = 'Morning and Evening'
        register = Register.objects.filter(tenant_id=request.user.id, customer_id=id,
                                           schedule__in=['morning-yes', 'evening-yes', 'e-morning',
                                                         'e-evening']).order_by(
            '-log_date').values()

        for entry in register:
            entry['billed_amount'] = float(entry['current_price'] / 1000) * entry['quantity']
            entry['display_paid'] = 'Paid' if entry['paid'] else 'Due'
            entry['display_schedule'] = 'Morning' if entry[
                                                         'schedule'] == 'morning-yes' else 'Evening'
            entry['display_log_date'] = entry['log_date'].strftime('%d-%b-%Y')

        # Get due table
        due_cust = Register.objects.filter(tenant_id=request.user.id, customer_id=id, paid=0,
                                           schedule__in=['morning-yes', 'evening-yes', 'e-morning',
                                                         'e-evening']).order_by('-log_date')
        payment_due_amount_prev_month = 0
        payment_due_amount_till_date = 0
        balance_amount = 0
        if due_cust:
            # Get the balance table
            balance_amount = get_customer_balance_amount(id)
            # Check till last month
            due_cust_prev_month = due_cust.filter(customer_id=id, paid=0).exclude(
                log_date__month=current_date.month, log_date__year=current_date.year)
            for due in due_cust_prev_month:
                payment_due_amount_prev_month += (
                    due.current_price / 1000 * decimal.Decimal(float(due.quantity)))
            # Check till today
            for due in due_cust:
                payment_due_amount_till_date += (
                    due.current_price / 1000 * decimal.Decimal(float(due.quantity)))

        # Extract months which has due for calendar
        active_months = get_active_month(id, all_active=True)
        calendar = [{'month': active_month.strftime('%B'),
                     'year': active_month.strftime('%Y'),
                     'week_start_day': [x for x in range(0, active_month.weekday())],
                     'days_in_month': [{'day': day,
                                        'data': get_register_day_entry(id, day=day,
                                                                       month=active_month.month,
                                                                       year=active_month.year)
                                        } for day in range(1, (
                         monthrange(active_month.year, active_month.month)[1]) + 1)]
                     } for active_month in active_months]

        # Extract only due months for bill
        due_months = get_active_month(id, only_paid=False, only_due=True)
        bill_summary = [{'month_year': f'{due_month.strftime("%B")} {due_month.year}',
                         'desc': get_bill_summary(id, month=due_month.month, year=due_month.year)}
                        for due_month in due_months]
        bill_summary.reverse()
        last_data_entry = customer_register_last_updated(id)
        bill_sum_total = {
            'last_updated': last_data_entry.strftime("%d %B, %Y") if last_data_entry else '',
            'today': datetime.now().strftime("%d %B, %Y, %H:%M %p"),
            'sum_total': (
                sum([bill.get('desc')[-1]['total'] for bill in bill_summary if bill.get('desc')]))}

        # Check for balance / Due amount
        balance_amount = get_customer_balance_amount(id)
        if balance_amount:
            bill_sum_total['balance'] = balance_amount
            bill_sum_total['sub_total'] = bill_sum_total['sum_total']
            bill_sum_total['sum_total'] = bill_sum_total['sum_total'] - balance_amount

        bill_summary.append(bill_sum_total)
        due_till_prev_month = round(payment_due_amount_prev_month, 2) - round(balance_amount)
        due_till_current_month = round(payment_due_amount_till_date, 2) - round(balance_amount)
        prev_month_name = (current_date + relativedelta(months=-1)).strftime("%B")
        current_month_name = current_date.strftime("%B")
        last_day_of_month = is_last_day_of_month()
        month_and_amount = (
            f'{prev_month_name} is Rs {due_till_prev_month}') if due_till_prev_month > 0 and not last_day_of_month else (
            f'{current_month_name} is Rs {due_till_current_month}')
        sms_text = f'Dear {customer.name},\nTotal due amount for the month of {month_and_amount}.\n[Milk Basket]'

        # Check if last transaction is older that 30 days
        last_trans = get_last_transaction(request, customer)
        is_30_days_old = (datetime.now() - last_trans.log_date).days > 30 if last_trans else False
        # Get Tenant Preference
        try:
            tenant = Tenant.objects.get(tenant_id=request.user.id)
        except Tenant.DoesNotExist:
            return redirect('setting')
        context.update({
            'calendar': calendar,
            'milk_price': get_milk_current_price(request.user.id, description=True),
            'bill_summary': bill_summary if bill_summary[-1]['sum_total'] else None,
            'menu_customer': True,
            'customer': customer,
            'sms_text': sms_text,
            'transaction': transaction,
            'is_revertible': is_transaction_revertible(request, customer) and not is_30_days_old,
            'register': register,
            'payment_due_amount_prev_month': due_till_prev_month,
            'payment_due_amount_till_date': due_till_current_month,
            'previous_month_name': prev_month_name,
            'tenant': tenant,
        })
        return render(request, template, context)
    return redirect('view_customers')


class GeneratePdf(View):
    def get(self, request, *args, **kwargs):
        cust_id = self.kwargs['id']
        no_download = True if 'file_download' in kwargs else False
        # messages.add_message(request, messages.SUCCESS, 'PDF Bill has been sucessfully generated')
        if no_download:
            return generate_bill(request, cust_id, no_download=True)
        else:
            data = generate_bill(request, cust_id)
            pdf = render_to_pdf('register/bill_pdf_template.html', data)
            # Force download PDf with file name
            pdf_download = HttpResponse(pdf, content_type='application/pdf')
            pdf_download[
                'Content-Disposition'] = f'attachment; filename="{data["bill_number"]}.pdf"'
            # Upload Bill metadata to Mongo
            return pdf_download


@login_required
def send_SMS(request):
    contact = request.POST.get("c_contact")
    smstext = request.POST.get("smstextareabox")
    data = {'status': 'failed'}
    if contact and smstext:
        data = send_sms_api(contact, smstext, DUE_TEMPLATE_ID)
    return HttpResponse(data, content_type='application/json')


@login_required
def send_EMAIL(request, id=None):
    if id:
        customer = Customer.objects.get(id=id)
        data = generate_bill(request, id, raw_data=True)
        subject = f'🛍️🥛 Bill due for ₹ {data["raw_data"]["bill_summary"][-1]["sum_total"]} 🧾'
        status = send_email_api(customer.email, subject, data)
        return JsonResponse(status)
    else:
        return None


@login_required
def bill_views(request):
    """ Fetch all bill views for a given tenent """
    # Fetch all clients belonging to the logged in tenant
    customers_list = list(
        Customer.objects.filter(tenant_id=request.user.id).values_list('id', flat=True))
    # Fetch all bills in list of customer ids
    metadata = get_mongo_client()
    bills = metadata.find({'customer_id': {'$in': customers_list}},
                          {'bill_number': 1, 'customer_id': 1, 'customer_name': 1, 'bill_date': 1,
                           'views': 1, 'transaction_ids': 1, 'bill_summary': 1})
    bill_list = []
    for bill in bills:
        string_date = bill['bill_date']  # 09 January 2021, 09:32 AM
        bill['bill_date_obj'] = datetime.strptime(string_date, '%d %B %Y, %I:%M %p')
        bill['bill_date'] = bill['bill_date_obj'].strftime("%Y/%m/%d %I:%M %p")
        if not 'views' in bill: bill['views'] = 'Not Viewed'
        bill['payment_status'] = False if Register.objects.filter(id__in=bill['transaction_ids'],
                                                                  paid=0) else True
        bill['bill_amount'] = bill['bill_summary'][-1]['sum_total']
        bill_list.append(bill)

    bill_list.sort(key=lambda x: x['bill_date_obj'], reverse=True)
    template = 'register/bill_views.html'
    context = {
        'page_title': 'Milk Basket - Bill Views',
        'is_mobile': is_mobile(request),
        'all_bills': bill_list,
        'menu_bill': True
    }
    return render(request, template, context)


# Compliance Docs
def privacy_policy(request):
    template = 'register/snippet/privacy_policy.html'
    context = {'page_title': 'Privacy Policy - Milk Basket', }
    return render(request, template, context)


def about_us(request):
    template = 'register/snippet/about_us.html'
    context = {'page_title': 'About Us - Milk Basket', }
    return render(request, template, context)


def return_refund(request):
    template = 'register/snippet/return_refund.html'
    context = {'page_title': 'Return, Refund, & Cancellation Policy - Milk Basket', }
    return render(request, template, context)


def terms_conditions(request):
    template = 'register/snippet/terms_conditions.html'
    context = {'page_title': 'Terms & Conditions - Milk Basket', }
    return render(request, template, context)


def product(request):
    template = 'register/snippet/product.html'
    sellers = Tenant.objects.filter(tenant__is_active=True).values('tenant__first_name',
                                                                   'milk_price', 'tenant__email')
    context = {'page_title': 'Product - Milk Basket', 'sellers': sellers}
    return render(request, template, context)


def broadcast_bulk_bill(request):
    template = 'register/broadcast.html'
    context = {'page_title': 'Generate Bills - Milk Basket', 'is_mobile': is_mobile(request)}
    return render(request, template, context)


def broadcast_metadata(request):
    context = {}
    if request.method == "GET":
        due_cust = get_all_due_customer(request)
        context.update({'due_customer': due_cust,
                        })
    return JsonResponse(context)


@login_required
def broadcast_send(request, cust_id=None):
    if cust_id:
        due = get_all_due_customer(request, cust_id)
        bill_byte = generate_bill(request, cust_id, no_download=True)
        bill = ast.literal_eval(bill_byte.content.decode('utf-8'))
        cust_number = get_customer_contact(request, cust_id)
        sms_body = f"""Dear {due[0]['name']},
Total due amount for the month of {due[0]['due_month']} is Rs {due[0]['to_be_paid']}.

[Milk Basket]"""
        wa_body = {
            "messaging_product": "whatsapp",
            "to": f"91{DEV_NUMBER}" if RUN_ENVIRONMENT == 'dev' else f"91{cust_number}",
            "type": "template",
            "template": {
                "name": "bill_generated",
                "language": {
                    "code": "en",
                    "policy": "deterministic"
                },
                "components": [
                    {
                        "type": "header",
                        "parameters": [
                            {
                                "type": "text",
                                "text": due[0]['to_be_paid']

                            }
                        ]
                    },

                    {
                        "type": "body",
                        "parameters": [
                            {
                                "type": "text",
                                "text": due[0]['name']
                            },
                            {
                                "type": "text",
                                "text": due[0]['to_be_paid']
                            },
                            {
                                "type": "text",
                                "text": due[0]['due_month']
                            },
                            {
                                "type": "text",
                                "text": f"https://milk.cyberboy.in/bill/{bill.get('bill_number')}"
                            }
                        ]
                    }
                ]
            }
        }
        wa_message = '''Dear {0},
Your bill of ₹ {1} for the month of {2} has been generated.

You can view the bill at 🧾👉 {3}

Thanks 🙏🐄🥛🧾'''.format(due[0]['name'], due[0]['to_be_paid'], due[0]['due_month'],
                      f"https://milk.cyberboy.in/bill/{bill.get('bill_number')}")
        sms_res = send_sms_api(DEV_NUMBER if RUN_ENVIRONMENT == 'dev' else cust_number, sms_body,
                               DUE_TEMPLATE_ID)
        wa_res = send_whatsapp_message(wa_body, wa_message)

        return JsonResponse({"sms": 2 if sms_res.text.__contains__('"status":"success"') else 3,
                             "wa": 2 if wa_res else 3})


@login_required()
def whatsapp_chat(request, wa_number=None):
    all_messages = WhatsAppMessage.objects.all().exclude(
        message_type__in=('unsupported', 'reaction'))
    customers = Customer.objects.filter(contact__isnull=False).values('contact', 'name')
    contact_names = {c['contact']: c['name'] for c in customers}
    distinct_users = {
        u.sender_number: contact_names.get(str(u.sender_number)[2:]) or u.sender_display_name for u
        in all_messages}
    for message in all_messages:
        message.sender_display_name = distinct_users.get(message.sender_number)
    if wa_number:
        if wa_number == int(WA_NUMBER_ID):
            all_messages = all_messages.filter(sender_number=WA_NUMBER_ID)
        else:
            all_messages = all_messages.filter(Q(sender_number=wa_number) | Q(to_number=wa_number))

    template = 'register/whatsapp.html'
    context = {
        'page_title': 'Milk Basket - WhatsApp',
        'all_messages': all_messages,
        'distinct_users': distinct_users,
    }
    return render(request, template, context)


@login_required()
def get_whatsapp_media(request, media_id):
    if media_id:
        media, media_type = get_whatsapp_media_by_id(media_id)
        return HttpResponse(media, content_type=media_type)

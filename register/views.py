import ast
import decimal
import logging
import threading
from datetime import date
from datetime import datetime
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth import authenticate
from django.contrib.auth import login
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponse
from django.http import JsonResponse
from django.shortcuts import redirect
from django.shortcuts import render
from django.urls import reverse
from django.views.generic import View
from django_otp.plugins.otp_totp.models import TOTPDevice

from customer.models import WhatsAppMessage, LoginOTP
from milkbasket.secret import RUN_ENVIRONMENT, DEV_NUMBER, WA_NUMBER_ID
from register.constant import DUE_TEMPLATE_ID, WA_DUE_MESSAGE, \
    SMS_DUE_MESSAGE, WA_DUE_MESSAGE_TEMPLATE_V3
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
    get_whatsapp_media_by_id, get_client_ip, is_non_prod, get_protocol, is_valid_email, is_valid_contact
from register.utils import generate_bill
from register.utils import get_customer_all_due
from register.utils import get_customer_due_amount
from register.utils import get_last_autopilot
from register.utils import get_last_transaction
from register.utils import get_mongo_client
from register.utils import get_tenant_perf
from register.utils import is_mobile
from register.utils import render_to_pdf
from register.utils import send_email_api
from register.utils import send_sms_api
from register.utils import send_whatsapp_message

logger = logging.getLogger()


@login_required
def index(request, year=None, month=None):
    # Get Tenant Preference
    tenant = get_tenant_perf(request)
    if tenant is None:
        return redirect('setting')
    template = 'register/react_register.html'

    context = {
        'page_title': 'Milk Basket - Register',
        'menu_register': True,
        'is_mobile': is_mobile(request),
    }
    custom_month = None
    if year and month:
        date_time_str = f'01/{month}/{year} 01:01:01'
        custom_month = datetime.strptime(date_time_str, '%d/%m/%Y %H:%M:%S')
    register_date = custom_month if custom_month else date.today()
    month_year = register_date.strftime("%B, %Y")

    context.update({
        'month_year': month_year,
        'register_date_month': register_date.month,
        'register_date_year': register_date.year,
        'protocol': get_protocol(),
        'show_tooltip': str(not is_mobile(request)).lower(),
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
            name = form['name'].value().strip().title()
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
                logger.info(f'New customer created {customer.name}')
            except Exception as E:
                list(messages.get_messages(request))
                messages.add_message(request, messages.ERROR,
                                     f'Something went wrong, we could not add customer')
                logger.critical(
                    f'Something went wrong, we could not add customer {messages.ERROR}')
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
def add_entry(request, year=None, month=None):
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
                entry = Register.objects.filter(tenant_id=request.user.id,
                                                customer_id=customer,
                                                log_date=full_log_date,
                                                schedule__startswith='morning-yes').first()
                if not entry:
                    entry = Register(tenant_id=request.user.id, customer_id=customer_info.id,
                                     log_date=full_log_date,
                                     schedule='morning-yes',
                                     quantity=customer_info.m_quantity,
                                     current_price=current_price)
                    entry.save()
            if customer_info.evening:
                entry = Register.objects.filter(tenant_id=request.user.id,
                                                customer_id=customer,
                                                log_date=full_log_date,
                                                schedule__startswith='evening-yes').first()
                if not entry:
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
            quantity = int(form['quantity'].value()) or 0
            current_price = tenant.milk_price
            if quantity % 250:
                return JsonResponse({
                    'return': False,
                    'message': f'{quantity} ML is not allowed. Quantity should be in multiple of 250 ML',
                })

            # check if entry exists for give day and schedule
            entry = Register.objects.filter(tenant_id=request.user.id, customer_id=customer,
                                            log_date=full_log_date,
                                            schedule__startswith=schedule).first()
            cust = Customer.objects.get(id=customer)
            extended_data = {'customer_name': cust.name}
            if not entry:
                entry = Register(tenant_id=request.user.id, customer_id=customer,
                                 log_date=full_log_date,
                                 schedule=full_schedule,
                                 quantity=quantity, current_price=current_price)
                entry.save()
                entry_status = True if entry.id else False
            else:
                # Check if the entry is already marked paid. if yes, don't allow updating.
                if entry.paid:
                    return JsonResponse({
                        'return': False,
                        'message': f'Paid entry cannot be updated. Please contact Admin to make any changes.',
                    })
                entry.schedule = full_schedule
                entry.quantity = quantity
                entry.save()
                entry_status = True if entry.id else False

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
            'customer_id': int(customer),
            'entry': {
                'id': entry.id,
                'log_date': entry.log_date,
                'schedule': entry.schedule,
                'paid': entry.paid,
                'quantity': entry.quantity,
                'current_price': current_price,
            }
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
        # Get autopilot form data
        autopilot_data = [{
            'id': int(key.split('-')[0]),
            'schedule': key.split('-')[1],
        } for key in request.POST if request.POST[key] == 'on']
        start_date = datetime.strptime(request.POST['start'], '%b %d, %Y')
        end_date = datetime.strptime(request.POST['end'], '%b %d, %Y')
        today = date.today()
        if start_date > end_date or (start_date.year, start_date.month) != (
                today.year, today.month) or (
                end_date.year, end_date.month) != (today.year, today.month):
            message = f'You have selected {start_date} start and {end_date} end date. End date cannot be before start date.' if start_date > end_date else 'Autopilot can only be run for current month.'
            response = {
                'show_message': True,
                'message': message,
                'status': False,
            }
            return JsonResponse(response)

        #  Get all register entry for given date range
        schedule_to_attr = {
            'morning': 'm_quantity',
            'evening': 'e_quantity',
        }
        register_entries = []
        delta = end_date - start_date
        date_list = [start_date + timedelta(days=i) for i in range(delta.days + 1)]
        active_customers = Customer.objects.filter(tenant=tenant,
                                                   id__in=set([u['id'] for u in autopilot_data]),
                                                   status=True)
        all_register_entry = Register.objects.filter(tenant=tenant, customer__in=active_customers,
                                                     log_date__in=date_list)

        # loop over each requested entry
        for current_date in date_list:
            for cust in autopilot_data:
                try:
                    customer = next(c for c in active_customers if c.id == cust['id'] and c.status)
                except StopIteration:
                    continue  # Customer does not exist or is Inactive. Skip over.
                try:
                    _ = next(e for e in all_register_entry if e.customer_id == cust['id'] and
                             e.log_date == current_date and e.schedule.startswith(
                        cust['schedule']))
                except StopIteration:
                    quantity = getattr(customer, schedule_to_attr[cust['schedule']])
                    if quantity is not None:
                        register_entries.append(Register(tenant=tenant,
                                                         customer_id=customer.id,
                                                         log_date=current_date,
                                                         schedule=f'{cust["schedule"]}-yes',
                                                         quantity=quantity,
                                                         current_price=current_price))

        Register.objects.bulk_create(register_entries)  # Create bulk Register entry
        response = {
            'show_message': False,
            'message': f'Success',
            'return': True,
            'reload': True,
        }
        messages.add_message(request, messages.SUCCESS,
                             f'Autopilot completed from {start_date.strftime("%d %b")} to {end_date.strftime("%d %b")}')
        return JsonResponse(response)
    # return invalid response if already not returned data
    response = {
        'show_message': True,
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
    template = 'register/react_account.html'
    custom_month = None
    if year and month:
        date_time_str = f'01/{month}/{year} 01:01:01'
        custom_month = datetime.strptime(date_time_str, '%d/%m/%Y %H:%M:%S')
    register_date = custom_month if custom_month else date.today()
    month_year = register_date.strftime("%B, %Y")
    context = {
        'page_title': 'Milk Basket - Accounts',
        'is_mobile': is_mobile(request),
        'month_year': month_year,
        'menu_account': True,
        'register_date_month': register_date.month,
        'register_date_year': register_date.year,
        'protocol': get_protocol(),
    }
    return render(request, template, context)


@login_required
def daterange(date1, date2):
    for n in range(int((date2 - date1).days) + 1):
        yield date1 + timedelta(n)


@login_required
def select_record(request):
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
                       'error_msg': f'Please fill all the fields before submitting - {e}'}
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
    sms_notification = int(request.POST.get("sms-notification", 0))
    if c_id and payment_amount:
        customer = Customer.objects.filter(tenant_id=request.user.id, id=c_id).first()
        payment_amount = float(payment_amount)
        new_payment = Payment(tenant_id=request.user.id, customer_id=c_id, amount=payment_amount)
        try:
            new_payment.save()
            messages.add_message(request, messages.SUCCESS,
                                 f'Payment of Rs. {payment_amount} received from {customer.name}')
            logger.info('Payment Received: {0} from {1}'.format(payment_amount, customer.name))
        except:
            messages.add_message(request, messages.ERROR,
                                 'Could not process payment of Rs. {payment_amount} from {customer.name}')
            logger.critical('Payment Failed: {0} from {1}'.format(payment_amount, customer.name))
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
        if sms_notification and customer.contact:
            transaction_time = datetime.now().strftime('%d-%m-%Y %I:%M:%p')
            # --------------------------------------------------------
            # Temporarily disable Payment received SMS notification
            # --------------------------------------------------------
            # sms_text = SMS_PAYMENT_MESSAGE.format(customer.name, new_payment.amount,
            #                                       transaction_time, new_payment.id)
            # send_sms_api(customer.contact, sms_text, PAYMENT_TEMPLATE_ID)
            # --------------------------------------------------------
            send_wa_payment_notification(customer.contact, customer.name, new_payment.amount,
                                         transaction_time, new_payment.id)

    return redirect(formatted_url)


@login_required
@transaction.atomic
def revert_transaction(request):
    """ This function is used to revert the last transaction within 30 days. """
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
            logger.info(f'Transaction #{transaction_number.id} was reverted successfully')
        except Exception as e:
            status = {'status': 'failed',
                      'error': f'Error occurred while reverting transactions {e}'}
            messages.add_message(request, messages.ERROR,
                                 f'Error occurred while reverting transactions {e}')
            logger.critical(f'Error occurred while reverting transactions {e}')

    return JsonResponse(status)


def landing(request):
    template = 'register/landing.html'
    context = {
        'page_title': 'Milk Basket - View customers',
        'is_mobile': is_mobile(request),
    }
    if request.method == "POST":
        tenant = None
        username = request.POST.get("username")
        password = request.POST.get("password")
        if username and password:
            username = username.lower()
            auth_user = authenticate(username=username, password=password)
            if auth_user:
                request.session['seller_id'] = auth_user.id
                if auth_user.is_superuser:
                    # Redirect to TOTO page for Admin users
                    request.session['is_verified_superuser'] = auth_user.id
                    context.update({'request_otp': 1,
                                    'remaining_attempt': 3,
                                    'current_username': username})
                    return render(request, template, context)

                tenant = Tenant.objects.get(tenant_id=auth_user.id)

        otp_password = request.POST.get("otp_password")
        superuser_id = request.session.get('is_verified_superuser', None)
        if otp_password and superuser_id is not None:
            # Verify TOTP for Supper user
            auth_user = User.objects.get(id=superuser_id)
            try:  # Check if the TOTP is configured
                totp_device = TOTPDevice.objects.get(user=auth_user)
            except TOTPDevice.DoesNotExist:
                context.update({
                    'message': 'TOTP has not been set up yet. Please configure it and try again.',
                })
                return render(request, template, context)
            # Verify the passed TOTP
            if totp_device.verify_token(otp_password):
                login(request, auth_user)
                logger.info(
                    'Admin Login Accepted. IP:{2}'.format(username, password,
                                                          get_client_ip(request)))
                del request.session['is_verified_superuser']
                return redirect('setting')
            else:  # Update the remaining attempt and request TOTP again
                remaining_attempt = request.session.get('remaining_attempt', 3) - 1
                request.session['remaining_attempt'] = remaining_attempt
                logger.warning(
                    'Failed Admin Login OTP Attempt - IP:{0}'.format(get_client_ip(request)))
                context.update({
                    'message': 'Invalid OTP',
                    'request_otp': remaining_attempt > 0,
                    'remaining_attempt': remaining_attempt,
                    'current_username': username
                })
                return render(request, template, context)

        if otp_password:
            user_id = request.session.get('seller_id')
            tenant = Tenant.objects.get(tenant_id=user_id)

        if tenant is not None:
            tenant.name = tenant.tenant.first_name
            otp = LoginOTP.get_otp(tenant, 'seller')
            context.update({'request_otp': otp.login_attempt < 3,
                            'remaining_attempt': otp.login_attempt < 3,
                            'current_username': username})
            if otp and otp_password:
                if otp_password == otp.otp_password and otp.login_attempt < 3:
                    login(request, tenant.tenant)
                    logger.info(
                        'Seller Login Accepted. IP:{2}'.format(username, password,
                                                               get_client_ip(request)))
                    otp.delete()
                    return redirect('view_register')
                else:
                    otp.login_attempt += 1
                    otp.save()
                    logger.warning(
                        'Failed Seller Login Attempt - UserName:{0} Password:{1} IP:{2}'.format(
                            username, password, get_client_ip(request)))
                    context.update({'message': 'Login Failed, {0}'.format(
                        f'{3 - otp.login_attempt} attempt remaining' if otp.login_attempt < 3 else 'please try again later')})
        else:
            logger.warning(
                'Failed Seller Login Attempt - UserName:{0} Password:{1} IP:{2}'.format(username,
                                                                                        password,
                                                                                        get_client_ip(
                                                                                            request)))
            context.update({
                'message': 'Invalid username or password',
            })
    return render(request, template, context)


@login_required
def report_initial(request):
    template = 'register/react_report.html'
    context = {'loading': True,
               'page_title': 'Milk Basket - Report',
               'is_mobile': is_mobile(request),
               'menu_report': True,
               'protocol': get_protocol()
               }
    return render(request, template, context)


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
        logger.info('Settings updated successfully')
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
        'run_env': RUN_ENVIRONMENT,
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
def customer_profile(request, cust_id=None):
    template = 'register/react_profile.html'
    context = {
        'is_mobile': is_mobile(request),
        'page_title': 'Milk Basket - Profile',
    }
    if cust_id:
        context.update({
            'menu_customer': True,
            'customer_id': cust_id,
            'protocol': get_protocol(),
        })
        return render(request, template, context)
    return redirect('view_customers')


class GeneratePdf(View):
    def get(self, request, *args, **kwargs):
        cust_id = self.kwargs['id']
        no_download = True if 'file_download' in kwargs else False
        # messages.add_message(request, messages.SUCCESS, 'PDF Bill has been successfully generated')
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
    sms_text = request.POST.get("smstextareabox")
    data = {'status': 'failed'}
    if contact and sms_text:
        data = send_sms_api(contact, sms_text, DUE_TEMPLATE_ID)
    return HttpResponse(data, content_type='application/json')


@login_required
def send_EMAIL(request, cust_id=None):
    if cust_id:
        customer = Customer.objects.get(id=cust_id)
        data = generate_bill(request, cust_id, raw_data=True)
        subject = f'🛍️🥛 Milk Bill due for ₹{data["raw_data"]["bill_summary"][-1]["sum_total"]} 🧾'
        bill_email_template = 'register/email_bill_template.html'
        status = send_email_api(customer.email, subject, data, bill_email_template)
        return JsonResponse(status)
    else:
        return None


@login_required
def bill_views(request):
    """ Fetch all bill views for a given tenant """
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


@login_required()
def broadcast_bulk_bill(request):
    tenant = get_tenant_perf(request)
    if tenant is None:
        return redirect('setting')
    template = 'register/broadcast.html'
    context = {'page_title': 'Generate Bills - Milk Basket', 'is_mobile': is_mobile(request), 'tenant': tenant}
    return render(request, template, context)


@login_required()
def broadcast_metadata(request):
    context = {}
    if request.method == "GET":
        due_cust = get_customer_all_due(request)
        context.update({'due_customer': due_cust,
                        })
    return JsonResponse(context)


@login_required
def broadcast_send(request, cust_id=None):
    tenant = get_tenant_perf(request)
    if tenant is None:
        return redirect('setting')
    if cust_id:
        due = get_customer_all_due(request, cust_id)
        bill = generate_bill(request, cust_id, raw_data=True)
        cust = Customer.objects.filter(tenant_id=request.user.id, id=cust_id).first()
        cust_number = cust.contact
        sms_body = SMS_DUE_MESSAGE.format(due[0]['name'], due[0]['due_month'],
                                          due[0]['to_be_paid'])
        wa_body = WA_DUE_MESSAGE_TEMPLATE_V3
        wa_body['to'] = f"91{DEV_NUMBER}" if is_non_prod() else f"91{cust_number}"
        wa_body['template']['components'][1]['parameters'][0]['text'] = due[0]['name']
        wa_body['template']['components'][1]['parameters'][1]['text'] = due[0]['to_be_paid']
        wa_body['template']['components'][1]['parameters'][2]['text'] = due[0]['due_month']
        wa_body['template']['components'][2]['parameters'][0]['text'] = bill.get('bill_number')

        wa_message = WA_DUE_MESSAGE.format(due[0]['name'], due[0]['to_be_paid'],
                                           due[0]['due_month'],
                                           f"https://milk.cyberboy.in/bill/{bill.get('bill_number')}")

        res = {'sms': False, 'whatsapp': False, 'email': False}

        def proxy_send_sms_api():
            res['sms'] = send_sms_api(cust_number,
                                      sms_body,
                                      DUE_TEMPLATE_ID)

        def proxy_send_whatsapp_message():
            res['whatsapp'] = send_whatsapp_message(wa_body, wa_message, cust_id=cust_id,
                                                    cust_number=cust_number)

        def proxy_send_email_message():
            subject = f'🛍️🥛 Milk Bill due for ₹{bill["raw_data"]["bill_summary"][-1]["sum_total"]} 🧾'
            bill_email_template = 'register/email_bill_template.html'
            res['email'] = send_email_api(cust.email, subject, bill, bill_email_template)

        threads = []

        if tenant.sms_pref and is_valid_contact(cust.contact):
            threads.append(threading.Thread(target=proxy_send_sms_api))

        if tenant.whatsapp_pref and is_valid_contact(cust.contact):
            threads.append(threading.Thread(target=proxy_send_whatsapp_message))

        if tenant.email_pref and is_valid_email(cust.email):
            threads.append(threading.Thread(target=proxy_send_email_message))

        # Start Threads
        for thread in threads:
            thread.start()

        # Join Threads
        for thread in threads:
            thread.join()

        if not isinstance(res['sms'], bool):
            res['sms'] = res['sms'].text.__contains__('"status":"success"')
        if not isinstance(res['email'], bool):
            res['email'] = res['email']['status'] == "success"

        return JsonResponse({"sms": 2 if res['sms'] else 3,
                             "wa": 2 if res['whatsapp'] else 3,
                             "email": 2 if res['email'] else 3})


@login_required()
def whatsapp_chat(request, wa_number=None):
    show_message_date = datetime.now() - timedelta(45)  # Show 45 days old messages only
    all_known_contact = Customer.objects.filter(contact__gt=0)
    customer_contacts = [910000000000 + int(c.contact) for c in
                         all_known_contact.filter(tenant_id=request.user.id)]
    all_messages = WhatsAppMessage.objects.filter(
        Q(sender_number__in=customer_contacts) | Q(to_number__in=customer_contacts),
        received_at__gt=show_message_date).exclude(
        Q(message_type__in=('unsupported', 'reaction')) | Q(route__in=('API_INFO', 'API_OTP')))
    if request.user.id == 2:
        # Add All Unknown Messages to Primary Seller
        unknown_messages = WhatsAppMessage.objects.filter(
            received_at__gt=show_message_date).exclude(
            Q(sender_number__in=[910000000000 + int(c.contact) for c in all_known_contact]) |
            Q(message_type__in=('unsupported', 'reaction')) | Q(
                route__in=('API_INFO', 'API_OTP', 'API')))
        all_messages = all_messages | unknown_messages
    customers_with_contact = Customer.objects.filter(contact__isnull=False).values('contact',
                                                                                   'name')
    contact_names = {c['contact']: c['name'] for c in customers_with_contact}
    distinct_users = {
        u.sender_number: contact_names.get(str(u.sender_number)[2:]) or u.sender_display_name for u
        in all_messages}
    chat_display_name = 'Milk Basket'
    if wa_number:
        if wa_number == int(WA_NUMBER_ID):
            all_messages = all_messages.filter(sender_number=WA_NUMBER_ID)
        else:
            all_messages = all_messages.filter(Q(sender_number=wa_number) | Q(to_number=wa_number))
            chat_display_name = contact_names.get(str(wa_number)[2:], 'Unknown User')
    # Get sender display name from saved customer details
    for message in all_messages:
        message.sender_display_name = distinct_users.get(message.sender_number)

    # Add messages to date chunks
    chat_dates = sorted(set([m.received_at.date() for m in all_messages]))
    sorted_all_chat = {chat_date: [m for m in all_messages if m.received_at.date() == chat_date]
                       for chat_date in chat_dates}

    template = 'register/whatsapp.html'
    context = {
        'page_title': 'Milk Basket - WhatsApp',
        'sorted_all_chat': sorted_all_chat,
        'distinct_users': distinct_users,
        'chat_display_name': chat_display_name,
    }
    return render(request, template, context)


@login_required()
def get_whatsapp_media(request, media_id):
    if media_id:
        try:
            media, media_type = get_whatsapp_media_by_id(media_id)
            return HttpResponse(media, content_type=media_type)
        except TypeError:
            logger.warning(f'Media Not Available {media_id}')
            # Show Not Available Image
            return redirect(
                'https://upload.wikimedia.org/wikipedia/commons/thumb/6/65/No-Image-Placeholder.svg/330px-No-Image-Placeholder.svg.png')


@login_required()
@transaction.atomic()
def customer_settle_up(request):
    c_id = request.POST.get("c_id", None)
    customer = Customer.objects.filter(tenant_id=request.user.id, id=c_id).first()
    if customer:
        # Check Advance Balance
        balance = Balance.objects.filter(customer=customer).first()
        if abs(balance.balance_amount) > 0:
            # Get last transaction number
            last_transaction = Payment.objects.filter(customer=customer).latest('log_date')
            # Get due register and update
            due_register = Register.objects.filter(customer=customer, paid=False,
                                                   schedule__endswith='-yes').order_by('log_date')
            for entry in due_register:
                due_amount = (entry.current_price / 1000) * decimal.Decimal(float(entry.quantity))
                if abs(balance.balance_amount) >= due_amount:
                    # Sufficient Balance Available, adjust current day
                    entry.paid = True
                    entry.transaction_number = last_transaction
                    entry.save()
                    balance.balance_amount = abs(balance.balance_amount) - due_amount
                    balance.save()

    profile_url = reverse('customer_profile', args=[customer.id])
    return redirect(profile_url)


@login_required()
@transaction.atomic()
def customer_refund(request):
    """ This function is used to refund the balance amount if the customer has paid advance """
    c_id = request.POST.get("c_id", None)
    customer = Customer.objects.filter(tenant_id=request.user.id, id=c_id).first()
    if customer:
        # Check Advance Balance
        balance = Balance.objects.filter(customer=customer).first()
        if abs(balance.balance_amount) > 0:
            # Get last transaction number / Add Note about Refund
            last_transaction = Payment.objects.filter(customer=customer).latest('log_date')
            last_transaction.refund_notes = f'₹{abs(balance.balance_amount)} Refunded on {datetime.now().strftime("%d-%b-%Y %I:%M %p")}'
            last_transaction.save()
            # Update Balance with 0 remaining amount
            balance.balance_amount = 0
            balance.save()
            logger.info(
                f'Refund {abs(balance.balance_amount)} completed for Customer:{customer.name}')

    profile_url = reverse('customer_profile', args=[customer.id])
    return redirect(profile_url)

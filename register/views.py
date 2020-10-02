from calendar import monthrange
from datetime import datetime, date, timedelta

import qrcode

from django.shortcuts import render, redirect

# Create your views here.
from register.forms import CustomerForm, RegisterForm
from register.models import Customer, Register, Milk


def index(request, year=None, month=None):
    template = 'register/register.html'
    context = {
        'page_title': 'Milk Basket - Register',
        'menu_register': True,
    }
    custom_month = None
    milk = Milk.objects.last()
    active_customers = Customer.objects.filter(status=1)
    if year and month:
        date_time_str = f'01/{month}/{year} 01:01:01'
        custom_month = datetime.strptime(date_time_str, '%d/%m/%Y %H:%M:%S')
    register_date = custom_month if custom_month else date.today()
    m_register = []
    e_register = []
    # Get morning register for given month
    register = Register.objects.filter(log_date__month=register_date.month,
                                       schedule__in=['morning-yes', 'morning-no',
                                                     'e-morning']).values('customer_id',
                                                                          'customer__name',
                                                                          'customer__quantity').distinct()

    for customer in register:
        register_entry = Register.objects.filter(log_date__month=register_date.month,
                                                 customer=customer['customer_id'],
                                                 schedule__in=['morning-yes', 'morning-no',
                                                               'e-morning'])
        m_register.append({
            'customer_name': customer['customer__name'],
            'customer_id': customer['customer_id'],
            'register_entry': register_entry,
            'customer_quantity': customer['customer__quantity'],
            'default_price': milk.price,
        })
    # Get evening register for given month
    register = Register.objects.filter(log_date__month=register_date.month,
                                       schedule__in=['evening-yes', 'evening-no',
                                                     'e-evening']).values('customer_id',
                                                                          'customer__name',
                                                                          'customer__quantity').distinct()

    for customer in register:
        register_entry = Register.objects.filter(log_date__month=register_date.month,
                                                 customer=customer['customer_id'],
                                                 schedule__in=['evening-yes', 'evening-no',
                                                               'e-evening'])
        e_register.append({
            'customer_name': customer['customer__name'],
            'customer_id': customer['customer_id'],
            'register_entry': register_entry,
            'customer_quantity': customer['customer__quantity'],
            'default_price': milk.price,
        })

    # plot calendar days
    days = monthrange(register_date.year, register_date.month)
    month_year = register_date.strftime("%B, %Y")
    cal_days = range(1, days[1] + 1)

    context.update({
        'month_year': month_year,
        'm_register': m_register,
        'e_register': e_register,
        'days': cal_days,
        'active_customers': active_customers,
        'default_price': milk.price,
    })
    return render(request, template, context)


def addcustomer(request):
    template = 'register/add-customer.html'
    context = {
        'page_title': 'Milk Basket - Add new customer',
        'menu_customer': True,
    }
    if request.method == "POST":
        form = CustomerForm(request.POST)
        name = form['name'].value()
        contact = form['contact'].value() or None
        email = form['email'].value() or None
        morning = form['morning'].value() or False
        evening = form['evening'].value() or False
        quantity = form['quantity'].value()
        customer = Customer(name=name, contact=contact, email=email, morning=morning,
                            evening=evening, quantity=quantity)
        customer.save()
        return redirect('view_customers')
    else:
        return render(request, template, context)


def addentry(request, year=None, month=None):
    if request.method == "POST":
        milk = Milk.objects.last()
        if request.POST.get("add-new-entry", None):
            customer = request.POST.get("customer", None)
            customer_info = Customer.objects.filter(id=customer, status=1).first()
            schedule = request.POST.get("schedule", None)
            log_date = request.POST.get("log_date", None)
            full_log_date = datetime.strptime(log_date, '%Y-%m-%d')
            current_price = milk.price
            # check if entry exists for give day and schedule
            check_record = Register.objects.filter(customer_id=customer, log_date=full_log_date,
                                                   schedule__startswith=schedule).first()
            if not check_record:
                entry = Register(customer_id=customer_info.id, log_date=full_log_date, schedule=schedule,
                                 quantity=customer_info.quantity, current_price=current_price)
                entry.save()
        else:
            form = RegisterForm(request.POST)
            customer = request.POST.get("id", None)
            log_date = request.POST.get("log_date", None)
            full_log_date = datetime.strptime(log_date, '%d %B, %Y')
            yes = request.POST.get("yes", None)
            yes_or_no = 'yes' if yes else 'no'
            schedule = request.POST.get("schedule", 'morning').lower()
            full_schedule = f'{schedule.lower()}-{yes_or_no}'
            quantity = form['quantity'].value() or False
            current_price = milk.price

            # check if entry exists for give day and schedule
            check_record = Register.objects.filter(customer_id=customer, log_date=full_log_date,
                                                   schedule__startswith=schedule).first()
            if not check_record:
                entry = Register(customer_id=customer, log_date=full_log_date, schedule=full_schedule,
                                 quantity=quantity, current_price=current_price)
                entry.save()
            else:
                check_record.schedule = full_schedule
                check_record.quantity = quantity
                check_record.save()

    if year and month:
        month = month if len(str(month)) > 1 else f'0{month}'
        return redirect(f'/register/{year}/{month}/')
    else:
        return redirect('index')


def customers(request):
    template = 'register/view-customer.html'
    context = {
        'page_title': 'Milk Basket - View customers',
        'menu_customer': True,
    }
    customers = Customer.objects.filter(status=1)
    for customer in customers:
        # Creating an instance of qrcode
        qr = qrcode.QRCode(
            version=1,
            box_size=10,
            border=1)
        qr.add_data(customer.id)
        qr.make(fit=True)
        img = qr.make_image(fill='black', back_color='white')
        img.save(f'register/static/qrcode{customer.id}.png')
        customer.img = f'/static/qrcode{customer.id}.png'

        if customer.morning and not customer.evening:
            customer.schedule = 'Morning'
        if not customer.morning and customer.evening:
            customer.schedule = 'Evening'
        if customer.morning and customer.evening:
            customer.schedule = 'Morning and Evening'
    context.update({'customers': customers})

    return render(request, template, context)


def account(request):
    template = 'register/account.html'
    today = date.today()
    month_year = today.strftime("%B, %Y")
    context = {
        'page_title': 'Milk Basket - Accounts',
        'month_year': month_year,
        'menu_account': True,
    }
    return render(request, template, context)


def daterange(date1, date2):
    for n in range(int((date2 - date1).days) + 1):
        yield date1 + timedelta(n)

import base64
from calendar import monthrange
from datetime import datetime, date, timedelta
from io import BytesIO

import date_range as date_range
import image
import qrcode
from PIL.Image import Image
from django.http import HttpResponse
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
    # start_dt = date(register_date.year, register_date.month, 1)
    # end_dt = date(register_date.year, register_date.month, days[1])
    # cal_days = daterange(start_dt, end_dt)

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
        qr = qrcode.make(customer.id)

        # img = Image.fromarray(qr, 'RGB')  # Crée une image à partir de la matrice
        # buffer = BytesIO()
        # img.save(buffer, format="JPEG")  # Enregistre l'image dans le buffer
        # myimage = buffer.getvalue()
        # # print
        # # "data:image/jpeg;base64," + base64.b64encode(myimage)
        # print(base64.b64encode(myimage))

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

import decimal
from calendar import monthrange
from datetime import datetime, date, timedelta, time

import qrcode
from django.db.models import Sum

from django.shortcuts import render, redirect

# Create your views here.
from register.forms import CustomerForm, RegisterForm
from register.models import Customer, Register, Milk, Expense


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
        'max_date': f'{date.today().year}-{date.today().month}-{days[1]}',
        'active_customers': active_customers,
        'default_price': milk.price,
    })
    return render(request, template, context)


def addcustomer(request):
    template = 'register/customer.html'
    context = {
        'page_title': 'Milk Basket - Add new customer',
        'menu_customer': True,
    }
    if request.method == "POST":
        customer_id = request.POST.get("id", None)
        if customer_id:
            customer = Customer(id=customer_id)
            customer.name = customer.name
            customer_contact = request.POST.get("contact")
            customer_email = request.POST.get("email")
            customer_morning = True if request.POST.get("morning", False) else False
            customer_evening = True if request.POST.get("evening", False) else False
            customer_quantity = request.POST.get("quantity", None)
            Customer.objects.filter(id=customer_id).update(contact=customer_contact, email=customer_email, morning=customer_morning, evening=customer_evening, quantity=customer_quantity)
        else:
            form = CustomerForm(request.POST)
            name = form['name'].value()
            contact = form['contact'].value()
            email = form['email'].value()
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
            attendance = request.POST.get("attendance", 0)
            yes_or_no = 'yes' if int(attendance) else 'no'
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
    template = 'register/customer.html'
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

    inactive_customers = Customer.objects.filter(status=0)
    for customer in inactive_customers:
        if customer.morning and not customer.evening:
            customer.schedule = 'Morning'
        if not customer.morning and customer.evening:
            customer.schedule = 'Evening'
        if customer.morning and customer.evening:
            customer.schedule = 'Morning and Evening'
    context.update({
        'customers': customers,
        'inactive_customers': inactive_customers,
    })

    return render(request, template, context)


def account(request, year=None, month=None):
    template = 'register/account.html'
    custom_month = None
    if year and month:
        date_time_str = f'01/{month}/{year} 01:01:01'
        custom_month = datetime.strptime(date_time_str, '%d/%m/%Y %H:%M:%S')
    register_date = custom_month if custom_month else date.today()

    # Get expenses
    total_expense = 0
    expenses = Expense.objects.filter(log_date__month=register_date.month)
    for exp in expenses:
        total_expense += exp.cost
    month_year = register_date.strftime("%B, %Y")

    # Get Payment Due
    total_payment = 0
    due_customer = Register.objects.filter(log_date__month=register_date.month, schedule__endswith='yes', paid=0).values('customer_id', 'customer__name').distinct()
    for customer in due_customer:
        payment_due = Register.objects.filter(customer_id=customer['customer_id'], log_date__month=register_date.month, schedule__endswith='yes', paid=0)
        payment_due_amount = 0
        for due in payment_due:
            payment_due_amount += (due.current_price / 1000 * decimal.Decimal(float(due.quantity)))
        customer['payment_due'] = payment_due_amount
        total_payment += payment_due_amount

    # Get paid customer
    total_payment_received = 0
    paid_customer = Register.objects.filter(log_date__month=register_date.month, schedule__endswith='yes', paid=1).values('customer_id', 'customer__name').distinct()
    for customer in paid_customer:
        payment_done = Register.objects.filter(customer_id=customer['customer_id'], log_date__month=register_date.month, schedule__endswith='yes', paid=1)
        payment_due_amount = 0
        for due in payment_done:
            payment_due_amount += (due.current_price / 1000 * decimal.Decimal(float(due.quantity)))
        customer['payment_done'] = payment_due_amount
        total_payment_received += payment_due_amount

    context = {
        'page_title': 'Milk Basket - Accounts',
        'month_year': month_year,
        'menu_account': True,
        'expenses': expenses,
        'total_payment': total_payment,
        'total_expense': total_expense,
        'due_customer': due_customer,
        'paid_customer': paid_customer,
    }

    return render(request, template, context)


def daterange(date1, date2):
    for n in range(int((date2 - date1).days) + 1):
        yield date1 + timedelta(n)


def selectrecord(request):
    formated_url = ''
    full_register_date = request.POST.get("register_month", None)
    register_month = str(full_register_date).split("-")[1]
    register_year = str(full_register_date).split("-")[0]
    nav_url = request.POST.get("nav-type", None)
    if nav_url == 'register':
        formated_url = f'/register/{register_year}/{register_month}/'
    elif nav_url == 'account':
        formated_url = f'/register/account/{register_year}/{register_month}/'
    return redirect(formated_url)


def manage_expense(request, year=None, month=None):
    expense_date = datetime.now()
    formated_url = '/register/account'
    if year and month:
        date_time_str = f'25/{month}/{year} 01:01:01'
        expense_date = datetime.strptime(date_time_str, '%d/%m/%Y %H:%M:%S')
        formated_url = f'/register/account/{year}/{month}/'
    delete_id = request.POST.get("id", None)
    if delete_id:
        Expense.objects.filter(id=delete_id).delete()
    add_expense = request.POST.get("month_year", None)
    if add_expense:
        cost = request.POST.get("cost_amount", None)
        desc = request.POST.get("exp_desc", None)
        new_expense = Expense(cost=cost, description=desc, log_date=expense_date)
        new_expense.save()

    return redirect(formated_url)

import decimal
import json
import time as t
import os
from calendar import monthrange
from datetime import datetime, date, timedelta, time
from dateutil.relativedelta import relativedelta

import qrcode
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required

from django.db import transaction
from django.db.models import Sum
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render, redirect

# Create your views here.
from django.utils.safestring import mark_safe

from register.forms import CustomerForm, RegisterForm
from register.models import Customer, Register, Milk, Expense, Payment, Balance, Income


@login_required
def index(request, year=None, month=None):
    template = 'register/register.html'
    context = {
        'page_title': 'Milk Basket - Register',
        'menu_register': True,
    }
    custom_month = None
    milk = Milk.objects.last()
    if not milk:
        return redirect('setting')
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

    # Get All customers if no entry is added - will be used in autopilot mode
    autopilot_register = []
    if not e_register or not m_register:
        all_customers = Customer.objects.filter(status=1)
        for customer in all_customers:
            autopilot_register.append({
                'customer_name': customer.name,
                'customer_id': customer.id,
                'customer_quantity': customer.quantity,
            })

    # plot calendar days
    days = monthrange(register_date.year, register_date.month)
    month_year = register_date.strftime("%B, %Y")
    cal_days = range(1, days[1] + 1)

    context.update({
        'month_year': month_year,
        'm_register': m_register,
        'e_register': e_register,
        'today_day': date.today().day,
        'days': cal_days,
        'max_date': f'{date.today().year}-{date.today().month}-{days[1]}',
        'active_customers': active_customers,
        'default_price': milk.price,
        'autopilot_register': autopilot_register,
    })
    return render(request, template, context)


@login_required
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


@login_required
def addentry(request, year=None, month=None):
    if request.method == "POST":
        milk = Milk.objects.last()
        yes_or_no = ''
        entry_status = False
        reload_status = False
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
                entry_status = True if entry.id else False
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
            current_price = milk.price

            # check if entry exists for give day and schedule
            check_record = Register.objects.filter(customer_id=customer, log_date=full_log_date,
                                                   schedule__startswith=schedule).first()
            if not check_record:
                entry = Register(customer_id=customer, log_date=full_log_date, schedule=full_schedule,
                                 quantity=quantity, current_price=current_price)
                entry.save()
                entry_status = True if entry.id else False
            else:
                check_record.schedule = full_schedule
                check_record.quantity = quantity
                check_record.save()
                entry_status = True if check_record.id else False

        data = {
            'return': entry_status,
            'cell': f'{customer}_{full_log_date.day}',
            'classname': 'cal-yes' if 'yes' in yes_or_no else 'cal-no',
            'reload': reload_status,
        }
        t.sleep(2)
        return JsonResponse(data)

    if year and month:
        month = month if len(str(month)) > 1 else f'0{month}'
        return redirect(f'/register/{year}/{month}/')
    else:
        return redirect('index')


@login_required
@transaction.atomic()
def autopilot(request, year=None, month=None):
    if request.method == "POST":
        milk = Milk.objects.last()
        current_price = milk.price
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
                'message': f'you have selected {start_date} start and {end_date} end date. End date can not be before start date.',
                'status': False,
            }
            return JsonResponse(response)
        delta = end - start  # as timedelta
        for i in range(delta.days + 1):
            day = start + timedelta(days=i)
            print(day)
            for cust in autopilot_data:
                customer = Customer.objects.filter(id=cust['id']).first()
                full_log_date = datetime.strptime(str(day), '%Y-%m-%d %H:%M:%S')
                check_record = Register.objects.filter(customer_id=customer.id, log_date=full_log_date,
                                                   schedule__startswith=cust['schedule']).first()
                if not check_record:
                    full_schedule = f'{cust["schedule"]}-yes'
                    entry = Register(customer_id=customer.id, log_date=full_log_date,
                                     schedule=full_schedule,
                                     quantity=customer.quantity, current_price=current_price)
                    entry.save()
                else:
                    print('Skipping: ', customer.name, 'Day: ', day)
        t.sleep(10)
        response = {
            'showmessage': False,
            'message': f'Success',
            'return': True,
            'reload': True,
        }
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
    template = 'register/customer.html'
    context = {
        'page_title': 'Milk Basket - View customers',
        'menu_customer': True,
    }
    customers = Customer.objects.filter(status=1)
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


@login_required
def account(request, year=None, month=None):
    template = 'register/account.html'
    custom_month = None
    current_date = date.today()
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
    due_customer = Register.objects.filter(schedule__endswith='yes', paid=0).values('customer_id', 'customer__name').distinct()
    for customer in due_customer:
        payment_due = Register.objects.filter(customer_id=customer['customer_id'], schedule__endswith='yes', paid=0)
        payment_due_amount = 0
        for due in payment_due:
            payment_due_amount += (due.current_price / 1000 * decimal.Decimal(float(due.quantity)))
        balance_amount = Balance.objects.filter(customer_id=customer['customer_id']).first()
        customer['adjusted_amount'] = getattr(balance_amount,
                                              'balance_amount') if balance_amount else 0
        customer['payment_due'] = round(payment_due_amount, 2) - abs(customer['adjusted_amount'])
        due_prev_month = Register.objects.filter(customer_id=customer['customer_id'],
                                              schedule__endswith='yes', paid=0).exclude(log_date__month=current_date.month)
        due_prev_month_amount = 0
        for due in due_prev_month:
            due_prev_month_amount += (due.current_price / 1000 * decimal.Decimal(float(due.quantity)))
        customer['payment_due_prev'] = round(due_prev_month_amount, 2) - abs(customer['adjusted_amount'])

        total_payment += payment_due_amount

    # Get paid customer
    total_payment_received = 0
    paid_customer = Register.objects.filter( schedule__endswith='yes', paid=1).values('customer_id', 'customer__name').distinct()
    for customer in paid_customer:
        payment_done = Register.objects.filter(customer_id=customer['customer_id'], schedule__endswith='yes', paid=1)
        payment_due_amount = 0
        for due in payment_done:
            payment_due_amount += (due.current_price / 1000 * decimal.Decimal(float(due.quantity)))
        balance_amount = Balance.objects.filter(customer_id=customer['customer_id']).first()
        customer['adjusted_amount'] = getattr(balance_amount,
                                              'balance_amount') if balance_amount else 0
        customer['payment_done'] = round(payment_due_amount, 2)
        paid_amount = Payment.objects.filter(customer_id=customer['customer_id'], log_date__month=register_date.month).aggregate(Sum('amount'))
        customer['total_paid'] = paid_amount['amount__sum']
        total_payment_received += payment_due_amount

    # Get extra income
    income = Income.objects.filter(log_date__month=register_date.month)

    context = {
        'page_title': 'Milk Basket - Accounts',
        'month_year': month_year,
        'menu_account': True,
        'expenses': expenses,
        'income': income,
        'total_payment': total_payment,
        'total_expense': total_expense,
        'due_customer': due_customer,
        'paid_customer': paid_customer,
        'previous_month_name': (current_date + relativedelta(months=-1)).strftime("%B")
    }

    return render(request, template, context)


@login_required
def daterange(date1, date2):
    for n in range(int((date2 - date1).days) + 1):
        yield date1 + timedelta(n)


@login_required
def selectrecord(request):
    formatted_url = ''
    full_register_date = request.POST.get("register_month", None)
    register_month = str(full_register_date).split("-")[1]
    register_year = str(full_register_date).split("-")[0]
    nav_url = request.POST.get("nav-type", None)
    if nav_url == 'register':
        formatted_url = f'/register/{register_year}/{register_month}/'
    elif nav_url == 'account':
        formatted_url = f'/register/account/{register_year}/{register_month}/'
    return redirect(formatted_url)


@login_required
def manage_expense(request, year=None, month=None):
    expense_date = datetime.now()
    formatted_url = '/register/account'
    if year and month:
        date_time_str = f'25/{month}/{year} 01:01:01'
        expense_date = datetime.strptime(date_time_str, '%d/%m/%Y %H:%M:%S')
        formatted_url = f'/register/account/{year}/{month}/'
    delete_id = request.POST.get("id", None)
    if delete_id:
        Expense.objects.filter(id=delete_id).delete()
    add_expense = request.POST.get("month_year", None)
    if add_expense:
        cost = request.POST.get("cost_amount", None)
        desc = request.POST.get("exp_desc", None)
        new_expense = Expense(cost=cost, description=desc, log_date=expense_date)
        new_expense.save()

    return redirect(formatted_url)


@login_required
def manage_income(request, year=None, month=None):
    income_date = datetime.now()
    formatted_url = '/register/account'
    if year and month:
        date_time_str = f'25/{month}/{year} 01:01:01'
        income_date = datetime.strptime(date_time_str, '%d/%m/%Y %H:%M:%S')
        formatted_url = f'/register/account/{year}/{month}/'
    delete_id = request.POST.get("id", None)
    if delete_id:
        Income.objects.filter(id=delete_id).delete()
    add_income = request.POST.get("month_year", None)
    if add_income:
        amount = request.POST.get("income_amount", None)
        desc = request.POST.get("exp_desc", None)
        new_income = Income(amount=amount, description=desc, log_date=income_date)
        new_income.save()

    return redirect(formatted_url)


@login_required
@transaction.atomic
def accept_payment(request, year=None, month=None, return_url=None):
    # Update Payment Table
    payment_date = date.today()
    return_url = request.POST.get("return_url", None)
    formatted_url = '/register/account' if not return_url else f'/register/{return_url}'
    if year and month:
        formatted_url = f'/register/account/{year}/{month}/'
        date_time_str = f'25/{month}/{year} 01:01:01'
        payment_date = datetime.strptime(date_time_str, '%d/%m/%Y %H:%M:%S')
    c_id = request.POST.get("c_id", None)
    payment_amount = request.POST.get("c_payment", None)
    if c_id and payment_amount:
        payment_amount = int(float(payment_amount))
        new_payment = Payment(customer_id=c_id, amount=payment_amount)
        new_payment.save()

        # Update Register
        balance_amount = Balance.objects.filter(customer_id=c_id).first()
        adjust_amount = float(getattr(balance_amount, 'balance_amount')) if balance_amount else 0
        Balance.objects.update_or_create(
            customer_id=c_id, defaults={"balance_amount": 0}
        )
        payment_amount = payment_amount + abs(adjust_amount)
        accepting_payment = Register.objects.filter(customer_id=c_id, schedule__endswith='yes', paid=0).order_by('log_date')
        for entry in accepting_payment:
            if payment_amount > 0:
                entry_cost = float(entry.current_price / 1000 * decimal.Decimal(float(entry.quantity)))
                if payment_amount - entry_cost >= 0:
                    Register.objects.filter(id=entry.id).update(paid=True)
                    payment_amount = payment_amount - entry_cost
                elif payment_amount != 0:
                    Balance.objects.update_or_create(
                        customer_id=c_id, defaults={"balance_amount": payment_amount}
                    )
                    payment_amount = 0

        if payment_amount != 0:
            Balance.objects.update_or_create(
                customer_id=c_id, defaults={"balance_amount": -payment_amount}
            )

    return redirect(formatted_url)


def landing(request):
    template = 'register/landing.html'
    context = {
        'page_title': 'Milk Basket - View customers',
    }
    if request.method == "POST":
        username = request.POST.get("username")
        username = username.lower()
        password = request.POST.get("password")
        user = authenticate(username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect('index')
        else:
            context.update({
                'message': 'Invalid username or password',
            })
    return render(request, template, context)


@login_required
def report(request, months=None):
    template = 'register/report.html'
    chart_data = []
    now = datetime.now()
    for i in range(-12, 1):
        d1 = date.today()
        graph_month = d1 + relativedelta(months=i)

        # Fetch Expenses
        month_expense = Expense.objects.filter(log_date__month=graph_month.month,
                                               log_date__year=graph_month.year).aggregate(Sum('cost'))['cost__sum'] or 0

        # Fetch Income
        month_income = 0
        month_income_entry = Register.objects.filter(log_date__month=graph_month.month,
                                               log_date__year=graph_month.year,)
        for entry in month_income_entry:
            month_income += float(entry.current_price / 1000) * entry.quantity

        # Fetch due per month
        month_due = 0
        month_due_entry = Register.objects.filter(log_date__month=graph_month.month,
                                                     log_date__year=graph_month.year, paid=0)
        for entry in month_due_entry:
            month_due += float(entry.current_price / 1000) * entry.quantity

        # Fetch paid per month
        month_paid = 0
        month_paid_entry = Register.objects.filter(log_date__month=graph_month.month,
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

    #     Get mil k production over past 365 days
    chart_data_milk = []
    for i in range(-365, 1):
        d1 = date.today()
        graph_day = d1 + relativedelta(days=i)
        mp = Register.objects.filter(log_date__year=graph_day.year, log_date__month=graph_day.month, log_date__day=graph_day.day)
        milk_production = mp.aggregate(Sum('quantity'))['quantity__sum'] or 0
        milk_production_morning = mp.filter(schedule='morning-yes').aggregate(Sum('quantity'))['quantity__sum'] or 0
        milk_production_evening = mp.filter(schedule='evening-yes').aggregate(Sum('quantity'))['quantity__sum'] or 0
        current_day = {
            "dayName": graph_day.strftime('%d-%B-%Y'),
            'milkMorning': round(float(milk_production_morning/1000), 2),
            'milkEvening': round(float(milk_production_evening/1000), 2),
            "milkQuantity": round(float(milk_production/1000), 2),
        }
        chart_data_milk.append(current_day)

    # Calculate all time Expenses
    all_time_expense = Expense.objects.all().aggregate(Sum('cost'))['cost__sum'] or 0

    # Calculate all time Income
    all_time_income = Payment.objects.all().aggregate(Sum('amount'))['amount__sum'] or 0

    # Calculate all time profit or loss
    is_profit = True if all_time_expense < all_time_income else False
    all_time_profit_or_loss = abs(all_time_income - all_time_expense)

    context = {
        'page_title': 'Milk Basket - Register',
        'menu_report': True,
        'graph_data': mark_safe(json.dumps(chart_data)),
        'table_data': chart_data,
        'chart_data_milk': mark_safe(json.dumps(chart_data_milk)),
        'all_time_expense': all_time_expense,
        'all_time_income': all_time_income,
        'is_profit': is_profit,
        'all_time_profit_or_loss': all_time_profit_or_loss,
    }
    return render(request, template, context)


@login_required
def setting(request):
    template = 'register/setting.html'
    if request.method == "POST":
        milk_price = request.POST.get("milkprice")
        now = datetime.now()
        if milk_price:
            new_milk_price = Milk(price=milk_price, date_effective=now)
            new_milk_price.save()
    try:
        milk = Milk.objects.latest('id')
    except:
        milk = None
    context = {
        'page_title': 'Milk Basket - Setting',
        'menu_setting': True,
        'milk': milk,
    }
    return render(request, template, context)


@login_required
def logout_request(request):
    logout(request)
    return redirect('index')


@login_required
def customer_profile(request, id=None):
    template = 'register/profile.html'
    current_date = date.today()
    if id:
        customer = Customer.objects.filter(id=id).first()
        transaction = Payment.objects.filter(customer_id=id)

        if customer.morning and not customer.evening:
            customer.schedule = 'Morning'
        if not customer.morning and customer.evening:
            customer.schedule = 'Evening'
        if customer.morning and customer.evening:
            customer.schedule = 'Morning and Evening'
        register = Register.objects.filter(customer_id=id, schedule__in=['morning-yes', 'evening-yes', 'e-morning', 'e-evening']).order_by('-log_date').values()

        for entry in register:
            entry['billed_amount'] = float(entry['current_price'] / 1000) * entry['quantity']
            entry['display_paid'] = 'Paid' if entry['paid'] else 'Due'
            entry['display_schedule'] = 'Morning' if entry['schedule'] == 'morning-yes' else 'Evening'
            entry['display_log_date'] = entry['log_date'].strftime('%d-%B-%Y')

        # Get due table
        due_cust = Register.objects.filter(customer_id=id, paid=0, schedule__in=['morning-yes', 'evening-yes', 'e-morning', 'e-evening']).order_by('-log_date')
        payment_due_amount_prev_month = 0
        payment_due_amount_till_date = 0
        adjusted_amount = 0
        if due_cust:
            # Get the balance table
            balance_amount = Balance.objects.filter(customer_id=id).first()
            adjusted_amount = getattr(balance_amount, 'balance_amount') if balance_amount else 0
            # Check till last month
            due_cust_prev_month = due_cust.filter(customer_id=id, paid=0).exclude(log_date__month=current_date.month)
            for due in due_cust_prev_month:
                payment_due_amount_prev_month += (due.current_price / 1000 * decimal.Decimal(float(due.quantity)))
            # Check till today
            for due in due_cust:
                payment_due_amount_till_date += (due.current_price / 1000 * decimal.Decimal(float(due.quantity)))
        context = {
            'page_title': 'Milk Basket - Profile',
            'menu_customer': True,
            'customer': customer,
            'transaction': transaction,
            'register': register,
            'payment_due_amount_prev_month': round(payment_due_amount_prev_month, 2) - abs(adjusted_amount),
            'payment_due_amount_till_date': round(payment_due_amount_till_date, 2) - abs(adjusted_amount),
            'previous_month_name': (current_date + relativedelta(months=-1)).strftime("%B")
        }
        return render(request, template, context)
    return redirect('view_customers')

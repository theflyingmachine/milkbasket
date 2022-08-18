import calendar
import datetime

import numpy as np
from django.shortcuts import render, redirect
# Create your views here.
from django.utils.safestring import mark_safe

from register.models import Customer, Payment, Register, Tenant
from register.utils import get_customer_due_amount, get_mongo_client


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
                                                                        'tenant__email').first()

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
        morning_entry.append(m_e.quantity if m_e and 'yes' in m_e.schedule else 0)
        e_e = register.filter(log_date__day=day, schedule__contains='evening').first()
        evening_entry.append(e_e.quantity if e_e and 'yes' in e_e.schedule else 0)

    context = {
        'customer': customer,
        'seller': seller,
        'summary': f'You have taken {",".join(today_summary)} today. Have a great day ahead!' if today_summary else 'You have not taken milk today.',
        'bills': bill_list,
        'bill_stats': {'count_due_bill': count_due_bill, 'count_paid_bill': count_paid_bill,
                       'percent': round((count_due_bill / len(bill_list) * 100),
                                        1) if count_due_bill else 100},
        'register_stats': {'days': days, 'morning_entry': morning_entry,
                           'evening_entry': evening_entry},
        'transactions': transactions,
        'order_statistics': {
            'labels': mark_safe([f"{v} ML" for v in values]),
            'series': list(counts),
            'orders': dict(zip(list(values), list(counts))),
            'total': sum(values * counts),
            'total_orders': sum(counts),
            'attendance': round((sum(counts) / register.count()) * 100, 1),
        },
        'date': {'today': today, 'last_month': last_month},
        'payment': {'total_due': total_due, 'prev_month_due': prev_month_due, 'advance': advance},
        'days_in_month': {'days': days_in_month,
                          'percent': round((today.day / days_in_month) * 100, 1),
                          'remaining': days_in_month - today.day},
        'page_title': 'Milk Basket - Register',

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

        if customer and customer.name == password:
            request.session['customer_session'] = True
            request.session['customer'] = customer.id
            request.session.save()
            return redirect('customer_dashboard')
        else:
            context.update({'message': 'Login Failed, please try again'})
    if request.session.get('customer_session'):
        return redirect('customer_dashboard')

    return render(request, template, context)

import calendar
import logging
from calendar import monthrange
from collections import defaultdict
from datetime import date
from datetime import datetime

from dateutil.relativedelta import relativedelta
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Q, Prefetch, F, FloatField, Func
from django.db.models.functions import Coalesce
from django.http import JsonResponse
from django.urls import reverse

from register.models import Customer, Payment, Tenant
from register.models import Expense
from register.models import Income
from register.models import Register
from register.serializer import CustomerRegisterSerializer, CustomerSerializer, \
    DueCustomerSerializer, ExpenseSerializer, \
    IncomeSerializer, PaidCustomerSerializer, CustomerProfileSerializer, TenantSerializer
from register.utils import get_tenant_perf, is_last_day_of_month, get_milk_current_price, \
    is_transaction_revertible, customer_register_last_updated, get_active_month, \
    get_customer_balance_amount, get_bill_summary

logger = logging.getLogger()


class RegisterAPI():

    @login_required()
    def get_register_api(request, year, month):
        """
        This function returns JSON data for the register entry in a month.
        """

        # Get Tenant Preference
        tenant = get_tenant_perf(request)
        custom_month = None
        if year and month:
            date_time_str = f'01/{month}/{year} 01:01:01'
            custom_month = datetime.strptime(date_time_str, '%d/%m/%Y %H:%M:%S')
        register_date = custom_month if custom_month else date.today()
        month_year = register_date.strftime("%B, %Y")

        register_filter = {
            'tenant_id': request.user.id,
            'log_date__month': register_date.month,
            'log_date__year': register_date.year
        }
        m_schedule = Q(schedule__in=['morning-yes', 'morning-no'])
        e_schedule = Q(schedule__in=['evening-yes', 'evening-no'])

        cust_register_filter = {
            'tenant_id': request.user.id,
            'register__log_date__month': register_date.month,
            'register__log_date__year': register_date.year
        }
        cust_m_schedule = Q(register__schedule__in=['morning-yes', 'morning-no'])
        cust_e_schedule = Q(register__schedule__in=['evening-yes', 'evening-no'])

        # Get morning register for given month
        m_cust = Customer.objects.prefetch_related(
            Prefetch('register_set',
                     queryset=Register.objects.filter(
                         m_schedule, **register_filter).order_by('log_date'))
        ).filter(cust_m_schedule, **cust_register_filter).distinct()

        e_cust = Customer.objects.prefetch_related(
            Prefetch('register_set',
                     queryset=Register.objects.filter(
                         e_schedule, **register_filter).order_by('log_date'))
        ).filter(cust_e_schedule, **cust_register_filter).distinct()

        # plot calendar days
        import datetime as dt
        # Get the number of days in the month
        days_in_month = calendar.monthrange(register_date.year, register_date.month)[1]
        # Create a list of date objects in the month
        date_list = [dt.date(register_date.year, register_date.month, day) for day in
                     range(1, days_in_month + 1)]

        # Get All customers if no entry is added - will be used in autopilot mode
        autopilot_morning_register, autopilot_evening_register = m_cust, e_cust
        active_customers = Customer.objects.filter(tenant_id=request.user.id, status=1)
        if not m_cust or not e_cust:
            autopilot_morning_register = active_customers.filter(m_quantity__gt=0)
            autopilot_evening_register = active_customers.filter(e_quantity__gt=0)

        # Get only active customers not added on register
        all_register = m_cust.union(e_cust)
        active_customers_not_in_register = active_customers.exclude(
            id__in=all_register.values('id'))

        # Get last entry date
        try:
            last_entry_date = Register.objects.filter(tenant_id=request.user.id,
                                                      log_date__month=register_date.month,
                                                      log_date__year=register_date.year).latest(
                'log_date__day')
            last_entry_date = int(last_entry_date.log_date.strftime("%d")) + 1
        except Register.DoesNotExist:
            last_entry_date = 1

        return JsonResponse({'status': 'success',
                             'default_price': tenant.milk_price,
                             'dates': date_list,
                             'm_register': CustomerRegisterSerializer(instance=m_cust,
                                                                      many=True).data,
                             'e_register': CustomerRegisterSerializer(instance=e_cust,
                                                                      many=True).data,
                             'register_date_month': register_date.month,
                             'register_date_year': register_date.year,
                             'month_year': month_year,
                             'today_day': date.today(),
                             'last_entry_day': date.today().replace(day=last_entry_date),
                             'autopilot_morning_register': CustomerSerializer(
                                 instance=autopilot_morning_register, many=True).data,
                             'autopilot_evening_register': CustomerSerializer(
                                 instance=autopilot_evening_register, many=True).data,
                             'active_customers_not_in_register': CustomerSerializer(
                                 instance=active_customers_not_in_register, many=True).data,
                             'active_customers': CustomerSerializer(instance=active_customers,
                                                                    many=True).data,
                             })

    @login_required()
    def get_account_api(request, year, month):
        """
        This function returns JSON data for the accounts.
        """
        custom_month = None
        current_date = date.today()
        if year and month:
            date_time_str = f'01/{month}/{year} 01:01:01'
            custom_month = datetime.strptime(date_time_str, '%d/%m/%Y %H:%M:%S')
        register_date = custom_month if custom_month else date.today()
        month_year = register_date.strftime("%B, %Y")

        # Get extra income and expenses
        income = Income.objects.filter(tenant_id=request.user.id,
                                       log_date__year=register_date.year,
                                       log_date__month=register_date.month).order_by('log_date')
        expenses = Expense.objects.filter(tenant_id=request.user.id,
                                          log_date__year=register_date.year,
                                          log_date__month=register_date.month).order_by('log_date')

        # Get Paid Customers
        paid_customers = Customer.objects.filter(
            payment__tenant=request.user.id,
            payment__log_date__month=register_date.month,
            payment__log_date__year=register_date.year
        ).annotate(
            paid_amount=Sum('payment__amount'),
            balance_amount=F('balance__balance_amount')
        ).order_by('name')

        # Get Due Customers
        first_day_of_month = current_date.replace(day=1)
        due_customers = Customer.objects.filter(
            register__tenant=request.user.id,
            register__paid=0,
            register__schedule__endswith='yes',
        ).annotate(
            due_amount=Sum(F('register__current_price') * F('register__quantity'),
                           output_field=FloatField()),
            due_prev_amount=Coalesce(
                Sum(F('register__current_price') * F('register__quantity'),
                    filter=Q(register__log_date__lt=first_day_of_month),
                    output_field=FloatField()), 0),
            balance_amount=Coalesce(F('balance__balance_amount'), 0),
        ).order_by('name')
        due_customers = due_customers.annotate(
            abs_balance_amount=Func(F('balance_amount'), function='ABS')
        ).exclude(abs_balance_amount__gt=F('due_amount') / 1000)

        return JsonResponse({
            'month_year': month_year,
            'previous_month_name': (current_date + relativedelta(months=-1)).strftime("%B"),
            'is_last_day_of_month': is_last_day_of_month(),
            'due_customers': DueCustomerSerializer(instance=due_customers, many=True).data,
            'paid_customers': PaidCustomerSerializer(instance=paid_customers, many=True).data,
            'income': IncomeSerializer(instance=income, many=True).data,
            'expenses': ExpenseSerializer(instance=expenses, many=True).data,
        })

    @login_required()
    def get_profile_api(request, customer_id):
        """
        This function returns JSON data for the customer profile.
        """
        due_customers_default = {}
        current_date = date.today()
        prev_month_name = (current_date + relativedelta(months=-1)).strftime("%B")
        current_month_name = current_date.strftime("%B")
        customer = Customer.objects.prefetch_related(
            Prefetch('payment_set',
                     queryset=Payment.objects.filter(customer_id=customer_id).order_by(
                         'log_date')),
            Prefetch('register_set',
                     queryset=Register.objects.filter(customer_id=customer_id,
                                                      schedule__endswith='yes').order_by(
                         '-log_date')),
        ).filter(tenant_id=request.user.id, id=customer_id).first()

        # Get bill summary
        due_months = get_active_month(customer_id, only_paid=False, only_due=True)
        bill_summary = [{'month_year': f'{due_month.strftime("%B")} {due_month.year}',
                         'desc': get_bill_summary(customer_id, month=due_month.month,
                                                  year=due_month.year)}
                        for due_month in due_months]
        bill_summary.reverse()
        last_data_entry = customer_register_last_updated(customer_id)
        bill_sum_total = {
            'last_updated': last_data_entry.strftime("%d %B, %Y") if last_data_entry else '',
            'today': datetime.now().strftime("%d %B, %Y, %H:%M %p"),
            'sum_total': (
                sum([bill.get('desc')[-1]['total'] for bill in bill_summary if bill.get('desc')]))}

        # Check for balance / Due amount
        balance_amount = get_customer_balance_amount(customer_id)
        if balance_amount:
            bill_sum_total['balance'] = balance_amount
            bill_sum_total['sub_total'] = bill_sum_total['sum_total']
            bill_sum_total['sum_total'] = bill_sum_total['sum_total'] - balance_amount

        bill_summary.append(bill_sum_total)

        # Get Due Amount
        due_customers = Customer.objects.filter(
            id=customer_id,
            register__tenant=request.user.id,
            register__paid=0,
            register__schedule__endswith='yes',
        ).annotate(
            due_amount=Sum(F('register__current_price') * F('register__quantity'),
                           output_field=FloatField()),
            due_prev_amount=Coalesce(
                Sum(F('register__current_price') * F('register__quantity'),
                    filter=Q(register__log_date__lt=date.today().replace(day=1)),
                    output_field=FloatField()), 0),
            balance_amount=Coalesce(F('balance__balance_amount'), 0),
        )
        if not due_customers:
            due_customers_default = {
                "id": customer.id,
                "name": customer.name,
                "contact": customer.contact,
                "due_amount": 0,
                "balance_amount": abs(balance_amount),
                "due_prev_amount": 0,
                "final_due_amount": 0 - abs(balance_amount),
                "final_due_prev_amount": 0
            }

        #  Extract months which has due for calendar
        active_months = get_active_month(customer_id, all_active=True)
        register = Register.objects.filter(tenant_id=request.user.id,
                                           customer_id=customer_id)
        entries_by_date = defaultdict(list)
        for entry in register:
            entries_by_date[entry.log_date.date()].append({
                'schedule': entry.schedule,
                'quantity': entry.quantity,
                'paid': entry.paid,
                'attendance': entry.schedule.endswith('yes'),
                'schedule_display': entry.schedule.split('-')[0].capitalize(),
            })
        calendar = [{'month': active_month.strftime('%B'),
                     'year': active_month.strftime('%Y'),
                     'week_start_day': [x for x in range(0, active_month.weekday())],
                     'days_in_month': [{'day': day,
                                        'data': entries_by_date[active_month.replace(day=day)]
                                        } for day in range(1, (
                         monthrange(active_month.year, active_month.month)[1]) + 1)]
                     } for active_month in active_months]
        tenant = Tenant.objects.get(tenant_id=request.user.id)

        return JsonResponse({
            'calendar': calendar,
            'milk_price': get_milk_current_price(request.user.id, description=True),
            'bill_summary': bill_summary if bill_summary[-1]['sum_total'] else None,
            'due_summary': DueCustomerSerializer(instance=due_customers, many=True).data[
                0] if due_customers else due_customers_default,
            'customer': CustomerProfileSerializer(instance=customer, many=False).data,
            'can_revert_transaction': is_transaction_revertible(request, customer),
            'previous_month_name': prev_month_name,
            'is_last_day_of_month': is_last_day_of_month(),
            'tenant': TenantSerializer(instance=tenant).data,
            'current_month_name': current_month_name,
            'month_year': date.today().strftime("%B, %Y"),
            'print_bill_url': reverse('print_bill', args=[customer.id]),
        })

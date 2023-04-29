import calendar
import decimal
import logging
from datetime import date
from datetime import datetime

from dateutil.relativedelta import relativedelta
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Q, Prefetch
from django.http import JsonResponse

from register.constant import SMS_DUE_MESSAGE
from register.models import Balance
from register.models import Customer
from register.models import Expense
from register.models import Income
from register.models import Payment
from register.models import Register
from register.serializer import CustomerSerializer, ExpenseSerializer, IncomeSerializer
from register.utils import calculate_milk_price
from register.utils import get_tenant_perf
from register.utils import is_last_day_of_month

logger = logging.getLogger()

from django.shortcuts import redirect


class BaseRegister:
    """
    Custom initializer that checks a condition and redirects if it's false
    """

    def __init__(self, *args, **kwargs):
        # Get Tenant Preference
        self.tenant = get_tenant_perf(self.request)
        if self.tenant is None:
            return redirect('setting')
        custom_month = None
        print('init')
        self.year = kwargs.pop('year',
                               None)  # Get the year parameter and store as instance variable
        self.month = kwargs.pop('month',
                                None)  # Get the month parameter and store as instance variable

        if self.year and self.month:
            date_time_str = f'01/{self.month}/{self.year} 01:01:01'
            custom_month = datetime.strptime(date_time_str, '%d/%m/%Y %H:%M:%S')
        self.register_date = custom_month if custom_month else date.today()


class RegisterAPI(BaseRegister):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    @login_required()
    def get_register_api(request, year, month):

        """ This function returns JSON data for the register entry in a month."""
        # Get Tenant Preference
        tenant = get_tenant_perf(request)
        if tenant is None:
            return redirect('setting')
        custom_month = None
        if year and month:
            date_time_str = f'01/{month}/{year} 01:01:01'
            custom_month = datetime.strptime(date_time_str, '%d/%m/%Y %H:%M:%S')
        register_date = custom_month if custom_month else date.today()

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

        return JsonResponse({'status': 'success',
                             'default_price': tenant.milk_price,
                             'dates': date_list,
                             'm_register': CustomerSerializer(instance=m_cust, many=True).data,
                             'e_register': CustomerSerializer(instance=e_cust, many=True).data,
                             })

    @login_required()
    def get_account_api(request, year, month):
        tenant = get_tenant_perf(request)
        if tenant is None:
            return redirect('setting')
        custom_month = None
        last_day_of_month = is_last_day_of_month()
        current_date = date.today()
        if year and month:
            date_time_str = f'01/{month}/{year} 01:01:01'
            custom_month = datetime.strptime(date_time_str, '%d/%m/%Y %H:%M:%S')
        register_date = custom_month if custom_month else date.today()

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
            payment_due_amount = calculate_milk_price(payment_due)
            balance_amount = Balance.objects.filter(tenant_id=request.user.id,
                                                    customer_id=customer['customer_id']).first()
            customer['adjusted_amount'] = getattr(balance_amount,
                                                  'balance_amount') if balance_amount else 0
            customer['payment_due'] = decimal.Decimal(payment_due_amount) - abs(
                customer['adjusted_amount'])
            due_prev_month = Register.objects.filter(tenant_id=request.user.id,
                                                     customer_id=customer['customer_id'],
                                                     schedule__endswith='yes', paid=0).exclude(
                log_date__month=current_date.month, log_date__year=current_date.year)
            due_prev_month_amount = calculate_milk_price(due_prev_month)
            customer['payment_due_prev'] = decimal.Decimal(due_prev_month_amount) - abs(
                customer['adjusted_amount'])

            total_payment += payment_due_amount

            # Due sms text
            prev_month_name = (current_date + relativedelta(months=-1)).strftime("%B")
            current_month_name = current_date.strftime("%B")
            if last_day_of_month or tenant.bill_till_date or not customer['payment_due_prev'] > 0:
                customer['sms_text'] = SMS_DUE_MESSAGE.format(customer['customer__name'],
                                                              current_month_name,
                                                              customer['payment_due'])
            else:
                customer['sms_text'] = SMS_DUE_MESSAGE.format(customer['customer__name'],
                                                              prev_month_name,
                                                              customer['payment_due_prev'])

        month_year = register_date.strftime("%B, %Y")

        # Get extra income and expenses
        income = Income.objects.filter(tenant_id=request.user.id,
                                       log_date__year=register_date.year,
                                       log_date__month=register_date.month)
        expenses = Expense.objects.filter(tenant_id=request.user.id,
                                          log_date__year=register_date.year,
                                          log_date__month=register_date.month)

        # Get Paid Customers
        # Get paid customer
        paid_customer = Register.objects.filter(tenant_id=request.user.id,
                                                schedule__endswith='yes',
                                                paid=1).values('customer_id',
                                                               'customer__name').distinct()
        for customer in paid_customer:
            payment_done = Register.objects.filter(tenant_id=request.user.id,
                                                   customer_id=customer['customer_id'],
                                                   schedule__endswith='yes', paid=1)
            accepted_amount = calculate_milk_price(payment_done)
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

        return JsonResponse({
            'month_year': month_year,
            'expenses': ExpenseSerializer(instance=expenses, many=True).data,
            'income': IncomeSerializer(instance=income, many=True).data,
            'paid_customer': CustomerSerializer(instance=paid_customer, many=True).data,
            # 'due_customer': CustomerSerializer(instance=due_customer, many=True).data,
            'due_total': sum([float(entry['payment_due']) for entry in due_customer]),
            'due_total_prev': sum([float(entry['payment_due_prev']) for entry in due_customer]),
            # 'paid_customer': [cust for cust in paid_customer if cust['total_paid']],
            # 'received_total': sum(
            #     [cust['total_paid'] for cust in paid_customer if cust['total_paid']]),
            'previous_month_name': (current_date + relativedelta(months=-1)).strftime("%B"),
            # 'tenant': tenant,
            'is_last_day_of_month': is_last_day_of_month()
        })

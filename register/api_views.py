import calendar
import logging
from datetime import date
from datetime import datetime

from dateutil.relativedelta import relativedelta
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Q, Prefetch, F, FloatField
from django.db.models.functions import Coalesce
from django.http import JsonResponse

from register.models import Customer
from register.models import Expense
from register.models import Income
from register.models import Register
from register.serializer import CustomerSerializer, DueCustomerSerializer, ExpenseSerializer, \
    IncomeSerializer, PaidCustomerSerializer
from register.utils import get_tenant_perf

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
            balance_amount=F('balance__balance_amount'),
        ).order_by('name')

        return JsonResponse({
            'month_year': month_year,
            'previous_month_name': (current_date + relativedelta(months=-1)).strftime("%B"),
            'due_customers': DueCustomerSerializer(instance=due_customers, many=True).data,
            'paid_customers': PaidCustomerSerializer(instance=paid_customers, many=True).data,
            'income': IncomeSerializer(instance=income, many=True).data,
            'expenses': ExpenseSerializer(instance=expenses, many=True).data,
        })

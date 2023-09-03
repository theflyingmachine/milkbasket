import calendar
import decimal
import json
import logging
from calendar import monthrange
from collections import defaultdict
from datetime import date
from datetime import datetime

from dateutil.relativedelta import relativedelta
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Q, Prefetch, F, Func, Value, DecimalField
from django.db.models.functions import Coalesce
from django.http import JsonResponse
from django.urls import reverse
from django.utils.safestring import mark_safe

from register.models import Customer, Payment, Tenant
from register.models import Expense
from register.models import Income
from register.models import Register
from register.serializer import CustomerRegisterSerializer, CustomerSerializer, \
    DueCustomerSerializer, ExpenseSerializer, \
    IncomeSerializer, PaidCustomerSerializer, CustomerProfileSerializer, TenantSerializer
from register.utils import get_tenant_perf, is_last_day_of_month, get_milk_current_price, \
    is_transaction_revertible, customer_register_last_updated, get_active_month, \
    get_customer_balance_amount, get_bill_summary, get_customer_due_amount_by_month

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
        autopilot_morning_register, autopilot_evening_register = [], []
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
            last_entry_date = int(last_entry_date.log_date.strftime("%d"))
            if last_entry_date < calendar.monthrange(register_date.year, register_date.month)[1]:
                last_entry_date += 1

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
                             'last_entry_day': register_date.replace(day=last_entry_date),
                             'autopilot_morning_register': CustomerSerializer(
                                 instance=autopilot_morning_register,
                                 many=True).data if not m_cust else [],
                             'autopilot_evening_register': CustomerSerializer(
                                 instance=autopilot_evening_register,
                                 many=True).data if not e_cust else [],
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
                           output_field=DecimalField()),
            due_prev_amount=Coalesce(
                Sum(F('register__current_price') * F('register__quantity'),
                    filter=Q(register__log_date__lt=first_day_of_month),
                    output_field=DecimalField()), Value(0, output_field=DecimalField())),
            balance_amount=Coalesce(F('balance__balance_amount'),
                                    Value(0, output_field=DecimalField())),
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
                           output_field=DecimalField()),
            due_prev_amount=Coalesce(
                Sum(F('register__current_price') * F('register__quantity'),
                    filter=Q(register__log_date__lt=date.today().replace(day=1)),
                    output_field=DecimalField()), Value(0, output_field=DecimalField())),
            balance_amount=Coalesce(F('balance__balance_amount'),
                                    Value(0, output_field=DecimalField())),
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

    @login_required()
    def get_report_data_api(request, poll_id):
        """
        This function returns JSON data for the Report page.
        """
        chart_data = []
        d1 = date.today()
        percent = 0
        milk_delivered = ['morning-yes', 'evening-yes']
        twelve_month_ago = d1.replace(day=1).replace(year=d1.year - 1)
        # Fetch all Expenses and Incomes
        tenant = Q(tenant_id=request.user.id)
        expense_data = Expense.objects.filter(tenant).values('log_date__month',
                                                             'log_date__year').annotate(
            expense=Sum('cost')).values('log_date__month', 'log_date__year', 'expense')

        income_data = Income.objects.filter(tenant).values('log_date__month',
                                                           'log_date__year').annotate(
            income=Sum('amount')).values('log_date__month', 'log_date__year', 'income')

        # Fetch all Registers
        register_query = Q(tenant, schedule__in=milk_delivered, log_date__gte=twelve_month_ago)
        all_register_entry = Register.objects.filter(register_query)

        for i in range(-12, 1):
            percent += 3.75
            graph_month = d1 + relativedelta(months=i)
            month_str = graph_month.strftime("%B-%Y")
            month_abbr = graph_month.strftime("%b-%y")
            request.session[poll_id] = f'Income and Expense ({graph_month.strftime("%B-%Y")})'
            request.session[f'{poll_id}_percent'] = percent
            request.session.save()

            # Retrieve Expense for the current month
            month_expense = next((item['expense'] for item in expense_data if
                                  item['log_date__month'] == graph_month.month and item[
                                      'log_date__year'] == graph_month.year), 0)

            # Retrieve Income for the current month
            month_extra_income = next((item['income'] for item in income_data if
                                       item['log_date__month'] == graph_month.month and item[
                                           'log_date__year'] == graph_month.year), 0)

            month_register_sale = sum(
                [entry.quantity * entry.current_price for entry in all_register_entry if
                 entry.log_date.month == graph_month.month and entry.log_date.year == graph_month.year]) / 1000

            month_register_sale += month_extra_income

            month_paid = sum(
                [entry.quantity * entry.current_price for entry in all_register_entry if
                 entry.log_date.month == graph_month.month and entry.log_date.year == graph_month.year and entry.paid]) / 1000

            month_paid += month_extra_income
            month_paid = decimal.Decimal(month_paid)
            month_due = decimal.Decimal(month_register_sale) - month_paid

            profit = float(
                max(month_paid - month_expense, 0)) if month_paid > month_expense else False
            loss = float(
                max(month_expense - month_paid, 0)) if month_paid <= month_expense else False

            current_month = {
                "monthName": month_str,
                "month": month_abbr,
                "income": float(month_register_sale),
                "paid": float(month_paid),
                "due": float(month_due),
                "expense": float(month_expense),
                "profit": profit,
                "loss": loss,
            }
            chart_data.append(current_month)

        #     Get milk production over past 365 days
        chart_data_milk = []
        all_milk_production = defaultdict(
            int)  # Using defaultdict to automatically initialize values to 0
        for entry in all_register_entry:
            all_milk_production[(entry.schedule, entry.log_date.date())] += entry.quantity

        for i in range(-365, 1):
            percent += 0.123
            d1 = date.today()
            graph_day = d1 + relativedelta(days=i)
            request.session[poll_id] = f'Milk Production ({graph_day.strftime("%d-%B-%Y")})'
            request.session[f'{poll_id}_percent'] = percent
            request.session.save()
            milk_production_morning = all_milk_production[('morning-yes', graph_day)]
            milk_production_evening = all_milk_production[('evening-yes', graph_day)]

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
        all_time_expense = \
            Expense.objects.filter(tenant_id=request.user.id).aggregate(Sum('cost'))[
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

    @login_required()
    def get_report_data_status_api(request, poll_id):
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

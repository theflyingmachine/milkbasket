from calendar import monthrange

from django.http import JsonResponse
from django.shortcuts import render

from register.models import Register
from register.utils import get_milk_current_price
from register.utils import get_mongo_client
from register.utils import get_register_day_entry


def index(request, bill_number=None):
    """Render customer view of bill"""
    if bill_number:
        template = 'bill/bill_template_simple.html'
        # template = 'bill/bill_template.html'
        context = {
            'page_title': 'Milk Basket - Bill',
        }
        logged_in = False if request.user.id else True
        bill_metadata = fetch_bill(bill_number, full_data=True, update_count=logged_in)
        if bill_metadata:
            # Fetch Tenant ID
            tenant = Register.objects.get(id=bill_metadata['transaction_ids'][0])
            tenant_id = tenant.tenant_id
            context.update(bill_metadata)
            due_transactions = Register.objects.filter(id__in=bill_metadata['transaction_ids'])
            payment_status = False if due_transactions.filter(paid=0) else True
            context.update({'payment_status': payment_status})

            # Extract months which has due for calendar
            active_months = due_transactions.dates('log_date', 'month', order='DESC')
            calendar = [{'month': active_month.strftime('%B'),
                         'year': active_month.strftime('%Y'),
                         'week_start_day': [x for x in range(0, active_month.weekday())],
                         'days_in_month': [{'day': day,
                                            'data': get_register_day_entry(
                                                bill_metadata['customer_id'], day=day,
                                                month=active_month.month,
                                                year=active_month.year,
                                                transaction_list=due_transactions)
                                            } for day in range(1, (
                             monthrange(active_month.year, active_month.month)[1]) + 1)]
                         } for active_month in active_months]
            for entry in due_transactions:
                entry.billed_amount = float(entry.current_price / 1000) * entry.quantity
                entry.display_paid = 'Paid' if entry.paid else 'Due'
                entry.display_schedule = 'Morning' if entry.schedule == 'morning-yes' else 'Evening'
                entry.display_log_date = entry.log_date.strftime('%d-%b-%y')
            context.update({'calendar': calendar,
                            'due_transactions': due_transactions,
                            'milk_price': get_milk_current_price(tenant_id, description=True)})

        return render(request, template, context)
    else:
        template = 'bill/index.html'
        context = {
            'page_title': 'Milk Basket - Search Bill',
        }
        return render(request, template, context)


def validate_bill(request, full_data=False):
    """ Check if the bill is valid on search bill page"""
    response = {
        'status': 'failed',
    }
    bill_number = request.POST.get("bill-number", None)
    if request.method == "POST" and bill_number:
        bill_metadata = fetch_bill(bill_number)
        if bill_metadata:
            response.update({'metadata': str(bill_metadata['_id']), 'bill_number': bill_number})
            response['status'] = 'success' if bool(dict(bill_metadata)) else 'failed'
    return JsonResponse(response)


def fetch_bill(bill_number, full_data=False, update_count=False):
    """ Fetch bill metadata from cloud Mongo DB """
    # Fetch Bill Metadata
    metadata = get_mongo_client()
    if full_data:
        bill_metadata = metadata.find_one({'bill_number': bill_number})
    else:
        bill_metadata = metadata.find_one({'bill_number': bill_number}, {'_id': 1})
    if update_count:
        metadata.update({'bill_number': bill_metadata['bill_number']}, {'$inc': {'views': 1, }})
    return bill_metadata

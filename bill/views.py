from django.http import HttpResponse
from django.http import JsonResponse
from django.shortcuts import render

from pymongo import MongoClient

from milkbasket.secret import MONGO_COLLECTION
from milkbasket.secret import MONGO_DATABASE
from milkbasket.secret import MONGO_KEY
from register.models import Register


def index(request, bill_number=None):
    if bill_number:
        template = 'bill/bill_template.html'
        context = {
            'page_title': 'Milk Basket - Bill',
        }
        bill_metadata = fetch_bill(bill_number, full_data=True)
        if bill_metadata:
            context.update(bill_metadata)
            due_transactions = Register.objects.filter(pk__in=bill_metadata['transaction_ids'])
            payment_status = True if due_transactions.filter(paid=1) else False
            context.update({'payment_status': payment_status})
        return render(request, template, context)
    else:
        template = 'bill/index.html'
        context = {
            'page_title': 'Milk Basket - Search Bill',
        }
        return render(request, template, context)


def validate_bill(request, full_data=False):
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


def fetch_bill(bill_number, full_data=False):
    client = MongoClient(
        f'mongodb+srv://milkbasket:{MONGO_KEY}@cluster0.4wgsn.mongodb.net/{MONGO_DATABASE}?retryWrites=true&w=majority')
    db = client[MONGO_DATABASE]
    # Fetch Bill Metadata
    metadata = db[MONGO_COLLECTION]
    if full_data:
        bill_metadata = metadata.find_one({'bill_number': bill_number})
    else:
        bill_metadata = metadata.find_one({'bill_number': bill_number}, {'_id': 1})
    return bill_metadata

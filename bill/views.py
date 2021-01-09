from django.http import HttpResponse
from django.http import JsonResponse
from django.shortcuts import render

from pymongo import MongoClient

from milkbasket.secret import MONGO_COLLECTION
from milkbasket.secret import MONGO_DATABASE
from milkbasket.secret import MONGO_KEY


def index(request, bill_number=None):
    if bill_number:
        return HttpResponse("Here's the text of the Web page with Bill Number.")
    else:
        template = 'bill/index.html'
        context = {
            'page_title': 'Milk Basket - Search Bill',
        }
        return render(request, template, context)


def validate_bill(request):
    response = {
        'status': 'failed',
    }
    bill_number = request.POST.get("bill-number", None)
    if request.method == "POST" and bill_number:
        client = MongoClient(
            f'mongodb+srv://milkbasket:{MONGO_KEY}@cluster0.4wgsn.mongodb.net/{MONGO_DATABASE}?retryWrites=true&w=majority')
        db = client[MONGO_DATABASE]
        # Fetch Bill Metadata
        metadata = db[MONGO_COLLECTION]
        bill_metadata = metadata.find_one({'bill_number': bill_number}, {'_id': 1})
        if bill_metadata:
            response.update({'metadata': str(bill_metadata['_id']), 'bill_number': bill_number})
            response['status'] = 'success' if bool(dict(bill_metadata)) else 'failed'
    return JsonResponse(response)

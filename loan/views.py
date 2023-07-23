import json
from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.db.models import Prefetch
from django.http import JsonResponse
from django.shortcuts import render

from loan.forms import LoanForm, TransactionForm
from loan.models import Loan, Transaction
from loan.serializer import LoanSerializer, TransactionSerializer
from register.utils import is_mobile


class DecimalEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, Decimal):
            return str(o)
        return super().default(o)


def loan_dashboard(request):
    template = 'loan/react_loan.html'
    context = {
        'page_title': 'Milk Basket - Loan',
        'is_mobile': is_mobile(request),
        'menu_loan': True,
    }
    return render(request, template, context)


class LoanAPI():
    @login_required()
    def add_loan_api(request):
        """
        This function records new loan entry
        """
        if request.method == 'POST':
            form = LoanForm(request.POST)
            if form.is_valid():
                new_loan = Loan(
                    tenant_id=request.user.id,
                    name=form.data['name'],
                    amount=form.data['amount'],
                    interest_rate=form.data['interest_rate'],
                    lending_date=form.data['lending_date'],
                    notes=form.data['notes'],
                )
                new_loan.save()
                return JsonResponse({'status': 'success',
                                     'saved_loan': LoanSerializer(instance=new_loan,
                                                                  many=False).data,
                                     })
            return JsonResponse({'status': 'false',
                                 'error': str(form.errors),
                                 })

    @login_required()
    def add_loan_transaction_api(request):
        """
        This function records new transaction entry
        """
        if request.method == 'POST':
            form = TransactionForm(request.POST)
            if form.is_valid():
                saved_transaction = form.save()
                # todo; Update Loan Status to 0, when all the added transactions add up to loan_amount
                return JsonResponse({'status': 'success',
                                     'saved_transaction': TransactionSerializer(
                                         instance=saved_transaction,
                                         many=False).data,
                                     })
            return JsonResponse({'status': 'false',
                                 'error': str(form.errors),
                                 })

    @login_required()
    def get_loan_api(request):
        """
        This function returns JSON data for the loan entry
        """
        all_loan = Loan.objects.prefetch_related(
            Prefetch('transaction_set',
                     queryset=Transaction.objects.all().order_by('transaction_date'))
        ).filter(tenant_id=request.user.id, status=True).distinct().order_by('-lending_date')
        return JsonResponse({'status': 'success',
                             'all_loans': LoanSerializer(instance=all_loan, many=True).data,
                             })

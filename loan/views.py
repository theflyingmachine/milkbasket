import json
from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.db.models import Prefetch, Sum, Q, DecimalField
from django.db.models.functions import Coalesce
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


@login_required()
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
    def list_loan(request):
        """
        This function returns JSON data for the loan entry
        """
        all_loan = Loan.objects.prefetch_related(
            Prefetch('transaction_set',
                     queryset=Transaction.objects.all().order_by('transaction_date'))
        ).filter(tenant_id=request.user.id).distinct().order_by('-lending_date')
        return JsonResponse({'status': 'success',
                             'all_loans': LoanSerializer(instance=all_loan, many=True).data,
                             })

    @login_required()
    def add_loan(request):
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
    def add_transaction(request):
        """
        This function records new transaction entry
        """
        if request.method == 'POST':
            form = TransactionForm(request.POST)
            if form.is_valid():
                # Fetch loan data with principal sum using annotations
                loan_data = Loan.objects.filter(tenant_id=request.user.id,
                                                id=form.data['loan_id']).annotate(
                    principal_sum=Coalesce(Sum('transaction__transaction_amount',
                                               filter=Q(transaction__type='PRINCIPAL')), 0,
                                           output_field=DecimalField())
                ).values('amount', 'principal_sum').first()
                if not loan_data:
                    return JsonResponse({'status': 'false', 'error': 'Loan not found.'})

                transaction_amount = Decimal(form.data['transaction_amount'])
                if form.data['type'] == 'PRINCIPAL':
                    total_principal = loan_data['principal_sum'] + transaction_amount
                    if total_principal > loan_data['amount']:
                        return JsonResponse({
                            'status': 'false',
                            'error': f'Cannot accept ₹{transaction_amount} principal transaction. '
                                     f'It will exceed the principal amount of ₹{loan_data["amount"]}',
                        })

                    if total_principal == loan_data['amount']:
                        Loan.objects.filter(id=form.data['loan_id']).update(status=False)

                # Save the transaction
                saved_transaction = form.save()
                return JsonResponse({'status': 'success',
                                     'saved_transaction': TransactionSerializer(
                                         instance=saved_transaction,
                                         many=False).data,
                                     })
            return JsonResponse({'status': 'false',
                                 'error': str(form.errors),
                                 })

    @login_required()
    def delete_transaction(request, transaction_id):
        """
        This functions used to delete transaction
        """
        try:
            Transaction.objects.get(id=transaction_id,
                                    loan_id__tenant_id=request.user.id).delete()
            return JsonResponse({'status': 'success',
                                 'deleted': transaction_id,
                                 })
        except Transaction.DoesNotExist:
            return JsonResponse({'status': 'false',
                                 'error': 'Transaction does not exist',
                                 })

# forms.py
from django import forms

from .models import Loan, Transaction


class LoanForm(forms.ModelForm):
    class Meta:
        model = Loan
        fields = ['name', 'amount', 'interest_rate', 'lending_date', 'notes']


class TransactionForm(forms.ModelForm):
    class Meta:
        model = Transaction
        fields = ['loan_id', 'transaction_amount', 'type', 'notes']

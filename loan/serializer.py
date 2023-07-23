from rest_framework import serializers

from .models import Loan, Transaction


class TransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Transaction
        fields = '__all__'


class LoanSerializer(serializers.ModelSerializer):
    transaction_entry = TransactionSerializer(many=True, source='transaction_set')

    class Meta:
        model = Loan
        fields = ['id', 'name', 'amount', 'interest_rate', 'lending_date', 'status', 'notes',
                  'transaction_entry']

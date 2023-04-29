from rest_framework import serializers

from .models import Customer, Register, Expense, Income


class RegisterSerializer(serializers.ModelSerializer):
    class Meta:
        model = Register
        fields = ['id', 'log_date', 'schedule', 'quantity', 'current_price', 'paid',
                  'transaction_number']


class CustomerSerializer(serializers.ModelSerializer):
    register_entry = RegisterSerializer(many=True, source='register_set')

    class Meta:
        model = Customer
        fields = ['id', 'name', 'm_quantity', 'e_quantity', 'status', 'register_entry']


class ExpenseSerializer(serializers.ModelSerializer):
    amount = serializers.CharField(source='cost')

    class Meta:
        model = Expense
        fields = ['id', 'description', 'amount', 'log_date', 'tenant']


class IncomeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Income
        fields = '__all__'


class PaidCustomerSerializer(serializers.ModelSerializer):
    paid_amount = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    balance_amount = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)

    class Meta:
        model = Customer
        fields = ('id', 'name', 'paid_amount', 'balance_amount')


class DueCustomerSerializer(serializers.ModelSerializer):
    due_amount = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    due_prev_amount = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    balance_amount = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)

    class Meta:
        model = Customer
        fields = ('id', 'name', 'due_amount', 'balance_amount', 'due_prev_amount')

import decimal

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
    due_amount = serializers.SerializerMethodField()
    due_prev_amount = serializers.SerializerMethodField()
    final_due_amount = serializers.SerializerMethodField()
    final_due_prev_amount = serializers.SerializerMethodField()
    balance_amount = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)

    @staticmethod
    def get_due_amount(obj):
        return decimal.Decimal(obj.due_amount) / 1000

    @staticmethod
    def get_due_prev_amount(obj):
        return decimal.Decimal(obj.due_prev_amount) / 1000

    @staticmethod
    def get_final_due_amount(obj):
        return decimal.Decimal(obj.due_amount / 1000) - abs(obj.balance_amount or 0)

    @staticmethod
    def get_final_due_prev_amount(obj):
        return decimal.Decimal(obj.due_prev_amount / 1000) - abs(obj.balance_amount or 0)

    class Meta:
        model = Customer
        fields = (
        'id', 'name', 'due_amount', 'balance_amount', 'due_prev_amount', 'final_due_amount',
        'final_due_prev_amount')

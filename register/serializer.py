import decimal
from datetime import datetime, timedelta

from rest_framework import serializers

from .models import Customer, Register, Expense, Income, Payment, Tenant


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
            'id', 'name', 'contact', 'due_amount', 'balance_amount', 'due_prev_amount',
            'final_due_amount',
            'final_due_prev_amount')


class TransactionSerializer(serializers.ModelSerializer):
    is_revertible = serializers.SerializerMethodField()

    class Meta:
        model = Payment
        fields = (
            'id', 'amount', 'log_date', 'payment_mode', 'transaction_id', 'refund_notes', 'tenant',
            'customer', 'is_revertible')

    def get_is_revertible(self, obj):
        if not obj.log_date:
            return False
        log_date = obj.log_date
        thirty_days_ago = datetime.today() - timedelta(days=30)

        return log_date > thirty_days_ago


class CustomerProfileSerializer(serializers.ModelSerializer):
    transaction_entry = TransactionSerializer(many=True, source='payment_set')
    register_entry = RegisterSerializer(many=True, source='register_set')

    class Meta:
        model = Customer
        fields = (
            'id', 'name', 'contact', 'email', 'morning', 'evening', 'm_quantity', 'e_quantity',
            'status', 'member_since', 'tenant', 'transaction_entry', 'register_entry')


class TenantSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tenant
        fields = '__all__'

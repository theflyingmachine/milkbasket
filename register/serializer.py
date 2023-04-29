from django.db.models import Sum
from rest_framework import serializers

from .models import Customer, Register, Expense, Income, Payment
from .utils import calculate_milk_price


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
    adjusted_amount = serializers.SerializerMethodField()
    payment_done = serializers.SerializerMethodField()
    total_paid = serializers.SerializerMethodField()

    class Meta:
        model = Customer
        fields = ('id', 'name', 'adjusted_amount', 'payment_done', 'total_paid')

    def get_adjusted_amount(self, obj):
        balance_amount = obj.balance_set.filter(
            tenant_id=self.context['request'].user.id
        ).first()
        return balance_amount.balance_amount if balance_amount else 0

    def get_payment_done(self, obj):
        payment_done = Register.objects.filter(
            tenant_id=self.context['request'].user.id,
            customer_id=obj.id,
            schedule__endswith='yes',
            paid=1
        )
        return calculate_milk_price(payment_done)

    def get_total_paid(self, obj):
        paid_amount = Payment.objects.filter(
            tenant_id=self.context['request'].user.id,
            customer_id=obj.id,
            log_date__month=self.context['register_date'].month,
            log_date__year=self.context['register_date'].year
        ).aggregate(Sum('amount'))
        return paid_amount['amount__sum'] if paid_amount['amount__sum'] else 0

from rest_framework import serializers

from .models import Customer, Register


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

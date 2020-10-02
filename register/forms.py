from django import forms
from register.models import Customer, Register


class CustomerForm(forms.ModelForm):
    class Meta:
        model = Customer
        fields = "__all__"


class RegisterForm(forms.ModelForm):
    class Meta:
        model = Register
        fields = "__all__"

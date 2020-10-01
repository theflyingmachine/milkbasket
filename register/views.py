from datetime import datetime

from django.http import HttpResponse
from django.shortcuts import render

# Create your views here.
from register.forms import CustomerForm
from register.models import Customer


def index(request):
    template = 'register/add-customer.html'
    context = {
        'page_title': 'Milk Basket - Add new customer',
       }

    return render(request, template, context)


def addcustomer(request):
    template = 'register/add-customer.html'
    if request.method == "POST":
        form = CustomerForm(request.POST)
        name = form['name'].value()
        contact = form['contact'].value() or None
        email = form['email'].value() or None
        morning = form['morning'].value() or False
        evening = form['evening'].value() or False
        quantity = form['quantity'].value()
        customer = Customer(name=name, contact=contact, email=email, morning=morning, evening=evening, quantity=quantity)
        customer.save()

    context = {
        'page_title': 'Milk Basket - Add new customer',
    }

    return render(request, template, context)

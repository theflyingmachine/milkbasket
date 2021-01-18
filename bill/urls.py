from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('check-bill', views.validate_bill, name='validate_bill'),
    path('<str:bill_number>/', views.index, name='view_bill'),
    ]

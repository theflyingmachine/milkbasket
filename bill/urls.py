from django.urls import path

from . import views

urlpatterns = [
    path('', views.index, name='bill_search'),
    path('check-bill', views.validate_bill, name='validate_bill'),
    path('<str:bill_number>/', views.index, name='view_bill'),
]

handler403 = 'register.utils.error_403_view'
handler404 = 'register.utils.error_404_view'
handler500 = 'register.utils.error_500_view'

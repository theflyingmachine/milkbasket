from django.urls import path

from . import views

urlpatterns = [
    path('', views.index, name='bill_search'),
    path('check-bill', views.validate_bill, name='validate_bill'),
    path('<str:bill_number>/', views.index, name='view_bill'),

    # Online PayTm Payment
    path('callback', views.payment_callback, name='app_callback'),
    path('check-txn-status/<int:transaction_id>/', views.check_txn_status,
         name='check_txn_status'),
]

handler403 = 'register.utils.error_403_view'
handler404 = 'register.utils.error_404_view'
handler500 = 'register.utils.error_500_view'

from django.urls import path

from . import views

urlpatterns = [
    path('', views.loan_dashboard, name='loan_dashboard'),

    # V1 API
    path('api/v1/add', views.LoanAPI.add_loan_api, name='add_loan_api'),
    path('api/v1/transaction', views.LoanAPI.add_loan_transaction_api,
         name='add_loan_transaction_api'),
    path('api/v1/list', views.LoanAPI.get_loan_api, name='list_loan_api'),
]

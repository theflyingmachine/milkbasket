from django.urls import path

from . import views

urlpatterns = [
    path('', views.loan_dashboard, name='loan_dashboard'),

    # V1 API
    path('api/v1/list', views.LoanAPI.list_loan, name='list_loan_api'),
    path('api/v1/add', views.LoanAPI.add_loan, name='add_loan_api'),
    path('api/v1/transaction', views.LoanAPI.add_transaction, name='add_transaction_api'),
    path('api/v1/delete/<int:trans_id>', views.LoanAPI.delete_transaction,
         name='delete_transaction_api'),
]

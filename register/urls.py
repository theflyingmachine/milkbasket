from django.urls import path

from . import views

urlpatterns = [
    path('', views.index, name='view_register'),
    path('register', views.index, name='view_register'),
    path('login', views.landing, name='landing'),
    path('logout', views.logout_request, name='logout'),
    path('setting', views.setting, name='setting'),
    path('bill-views', views.bill_views, name='bill_views'),
    path('<int:year>/<int:month>/', views.index, name='view_register_month'),
    path('profile/<int:id>/', views.customer_profile, name='customer_profile'),
    path('print-bill/<int:id>/', views.GeneratePdf.as_view(), name='print_bill'),
    path('print-bill/<int:id>/<str:file_download>/', views.GeneratePdf.as_view(),
         name='share_bill'),
    path('<int:year>/<int:month>/addentry', views.addentry, name='view_addentry_month'),
    path('add-customer', views.addcustomer, name='add_customer'),
    path('customers', views.customers, name='view_customers'),
    path('account', views.account, name='view_account'),
    path('account/<int:year>/<int:month>/', views.account, name='account_month'),
    path('add-new-entry', views.addentry, name='view_add_entry'),
    path('<int:year>/<int:month>/autopilot', views.autopilot, name='view_autopilot'),
    path('autopilot', views.autopilot, name='view_autopilot'),
    path('select-record', views.selectrecord, name='view_selectrecord'),
    path('manage-expenses', views.manage_expense, name='manage_expense'),
    path('account/<int:year>/<int:month>/manage-expenses', views.manage_expense,
         name='manage_expense'),
    path('manage-incomes', views.manage_income, name='manage_income'),
    path('account/<int:year>/<int:month>/manage-incomes', views.manage_income,
         name='manage_income'),
    # path('report', views.report, name='view_report'),  # Old Report Page
    path('report', views.report_initial, name='view_report'),  # Report initial page load
    # Report AJAX call endpoint
    path('report-data/<str:poll_id>', views.report_data, name='view_report'),
    # Report AJAX call status endpoint
    path('report-data-status/<str:poll_id>', views.report_data_status, name='view_report'),

    path('accept-payment', views.accept_payment, name='accept_payment'),
    path('account/<int:year>/<int:month>/accept-payment', views.accept_payment,
         name='accept_payment'),
    path('revert-transaction', views.revert_transaction, name='revert_transaction'),
    path('send-sms', views.send_SMS, name='send_sms'),
    path('send-email/<int:id>', views.send_EMAIL, name='send_email'),
]

# handler403 = 'register.utils.error_403_view'
# handler404 = 'register.utils.error_404_view'
# handler500 = 'register.utils.error_500_view'

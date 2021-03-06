from django.urls import path

from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('login', views.landing, name='landing'),
    path('logout', views.logout_request, name='logout'),
    path('setting', views.setting, name='setting'),
    path('bill-views', views.bill_views, name='bill_views'),
    path('<int:year>/<int:month>/', views.index, name='index_month'),
    path('profile/<int:id>/', views.customer_profile, name='customer_profile'),
    path('print_bill/<int:id>/', views.GeneratePdf.as_view(), name='print_bill'),
    path('print_bill/<int:id>/<str:file_download>/', views.GeneratePdf.as_view(),
         name='share_bill'),
    path('<int:year>/<int:month>/addentry', views.addentry, name='view_addentry_month'),
    path('addcustomer', views.addcustomer, name='add_customer'),
    path('customers', views.customers, name='view_customers'),
    path('account', views.account, name='view_account'),
    path('account/<int:year>/<int:month>/', views.account, name='account_month'),
    path('addentry', views.addentry, name='view_addentry'),
    path('<int:year>/<int:month>/autopilot', views.autopilot, name='view_autopilot'),
    path('autopilot', views.autopilot, name='view_autopilot'),
    path('selectrecord', views.selectrecord, name='view_selectrecord'),
    path('manageexpenses', views.manage_expense, name='manage_expense'),
    path('account/<int:year>/<int:month>/manageexpenses', views.manage_expense,
         name='manage_expense'),
    path('manageincomes', views.manage_income, name='manage_income'),
    path('account/<int:year>/<int:month>/manageincomes', views.manage_income,
         name='manage_expense'),
    # path('report', views.report, name='view_report'),  # Old Report Page
    path('report', views.report_initial, name='view_report'),  # Report initial page load
    # Report AJAX call endpoint
    path('report_data/<str:poll_id>', views.report_data, name='view_report'),
    # Report AJAX call status endpoint
    path('report_data_status/<str:poll_id>', views.report_data_status, name='view_report'),

    path('acceptpayment', views.accept_payment, name='accept_payment'),
    path('account/<int:year>/<int:month>/acceptpayment', views.accept_payment,
         name='accept_payment'),
    path('sendsms', views.send_SMS, name='send_sms'),
    path('sendemail/<int:id>', views.send_EMAIL, name='send_email'),
]

# handler403 = 'register.utils.error_403_view'
# handler404 = 'register.utils.error_404_view'
# handler500 = 'register.utils.error_500_view'

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
    path('profile/<int:cust_id>/', views.customer_profile, name='customer_profile'),
    path('print-bill/<int:id>/', views.GeneratePdf.as_view(), name='print_bill'),
    path('print-bill/<int:id>/<str:file_download>/', views.GeneratePdf.as_view(),
         name='share_bill'),
    path('<int:year>/<int:month>/addentry', views.addentry, name='view_addentry_month'),
    path('add-customer', views.add_customer, name='add_customer'),
    path('customers', views.customers, name='view_customers'),
    path('account', views.account, name='view_account'),
    path('account/<int:year>/<int:month>/', views.account, name='account_month'),
    path('add-new-entry', views.addentry, name='view_add_entry'),
    path('<int:year>/<int:month>/autopilot', views.autopilot, name='view_autopilot'),
    path('autopilot', views.autopilot, name='view_autopilot'),
    path('select-record', views.select_record, name='view_select_record'),
    path('manage-expenses', views.manage_expense, name='manage_expense'),
    path('account/<int:year>/<int:month>/manage-expenses', views.manage_expense,
         name='manage_expense'),
    path('manage-incomes', views.manage_income, name='manage_income'),
    path('account/<int:year>/<int:month>/manage-incomes', views.manage_income,
         name='manage_income'),
    # path('report', views.report, name='view_report'),  # Old Report Page
    path('report', views.report_initial, name='view_report'),  # Report initial page load
    # Report AJAX call endpoint
    path('report-data/<str:poll_id>', views.report_data, name='view_report_data'),
    # Report AJAX call status endpoint
    path('report-data-status/<str:poll_id>', views.report_data_status, name='view_report_data'),

    path('accept-payment', views.accept_payment, name='accept_payment'),
    path('settle-up-payment', views.customer_settle_up, name='customer_settle_up'),
    path('refund-payment', views.customer_refund, name='customer_refund'),
    path('account/<int:year>/<int:month>/accept-payment', views.accept_payment,
         name='accept_payment'),
    path('revert-transaction', views.revert_transaction, name='revert_transaction'),
    path('send-sms', views.send_SMS, name='send_sms'),
    path('send-email/<int:cust_id>', views.send_EMAIL, name='send_email'),

    #     API Alexa
    path('api/v1/register/last-entry', views.alexa_get_last_autopilot, name='get_last_autopilot'),
    path('api/v1/register/run-autopilot', views.alexa_run_autopilot, name='alexa_run_autopilot'),
    path('api/v1/customers', views.alexa_customer_list, name='alexa_customer_list'),
    path('api/v1/customers/due-amount', views.alexa_customer_due, name='alexa_customer_due'),

    # Compliance Docs
    path('about-us', views.about_us, name='about_us'),
    path('product', views.product, name='product'),
    path('privacy', views.privacy_policy, name='privacy_policy'),
    path('return-refund', views.return_refund, name='return_refund'),
    path('terms-conditions', views.terms_conditions, name='terms_conditions'),

    # Broadcast Bills
    path('broadcast-bills', views.broadcast_bulk_bill, name='broadcast_bulk_bill'),
    path('broadcast-metadata', views.broadcast_metadata, name='broadcast_metadata'),
    path('broadcast-send/<int:cust_id>/', views.broadcast_send, name='broadcast_send'),

    # Whatsapp chat
    path('whatsapp', views.whatsapp_chat, name='whatsapp_chat'),
    path('whatsapp/<int:wa_number>', views.whatsapp_chat, name='whatsapp_number_chat'),
    path('whatsapp/media/<int:media_id>', views.get_whatsapp_media, name='whatsapp_media'),

    # V1 API
    path('api/v1/register/<int:year>/<int:month>/', views.get_register_api,
         name='get_register_api'),

]

# handler403 = 'register.utils.error_403_view'
# handler404 = 'register.utils.error_404_view'
# handler500 = 'register.utils.error_500_view'

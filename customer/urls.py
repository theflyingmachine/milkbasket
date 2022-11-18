from django.urls import path

from . import views

urlpatterns = [
    path('', views.customer_dashboard, name='customer_dashboard'),
    path('logout', views.customer_dashboard_logout, name='customer_dashboard_logout'),
    path('login', views.customer_dashboard_login, name='customer_dashboard_login'),

    path('webhooks/whatsapp/message', views.whatsapp_webhook, name='whatsapp_webhook'),

]

# handler403 = 'register.utils.error_403_view'
# handler404 = 'register.utils.error_404_view'
# handler500 = 'register.utils.error_500_view'

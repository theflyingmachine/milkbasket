"""milkbasket URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/3.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import include
from django.urls import re_path

from django_otp.admin import OTPAdminSite

# Enforce TOTP login for Site Admin Panel
admin.site.__class__ = OTPAdminSite

urlpatterns = [
    re_path('admin/', admin.site.urls),
    re_path(r'', include('register.urls')),
    re_path(r'^bill/', include('bill.urls')),
    re_path(r'^milkbasket/', include('register.urls')),
    re_path(r'^customer/', include('customer.urls')),
    re_path(r'^loan/', include('loan.urls')),
    re_path(r'^maintenance-mode/', include('maintenance_mode.urls')),

]
# Custom Error Handlers
handler403 = 'register.utils.error_403_view'
handler404 = 'register.utils.error_404_view'
handler500 = 'register.utils.error_500_view'

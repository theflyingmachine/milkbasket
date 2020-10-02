from django.urls import path

from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('<int:year>/<int:month>/', views.index, name='index_month'),
    path('<int:year>/<int:month>/addentry', views.addentry, name='view_addentry_month'),
    path('addcustomer', views.addcustomer, name='add_customer'),
    path('customers', views.customers, name='view_customers'),
    path('account', views.account, name='view_account'),
    path('account/<int:year>/<int:month>/', views.account, name='account_month'),
    path('addentry', views.addentry, name='view_addentry'),
    path('selectrecord', views.selectrecord, name='view_selectrecord'),
    # ex: /polls/5/
    # path('<int:question_id>/', views.detail, name='detail'),
    # # ex: /polls/5/results/
    # path('<int:question_id>/results/', views.results, name='results'),
    # # ex: /polls/5/vote/
    # path('<int:question_id>/vote/', views.vote, name='vote'),
]

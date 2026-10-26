from django.urls import path
from . import views

app_name = 'blockchain'

urlpatterns = [
    path('', views.BlockchainExplorerView.as_view(), name='explorer'),
]
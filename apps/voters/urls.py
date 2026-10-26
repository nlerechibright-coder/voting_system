from django.urls import path
from . import views

app_name = 'voters'

urlpatterns = [
    path('', views.VoterListView.as_view(), name='list'),
]
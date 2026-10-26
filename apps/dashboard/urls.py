from django.urls import path
from . import views

app_name = 'dashboard'

urlpatterns = [
    path('', views.DashboardView.as_view(), name='home'),
    path('election-wizard/', views.ElectionSetupWizardView.as_view(), name='election_wizard'),
    path('election-wizard/<int:pk>/', views.ElectionSetupWizardView.as_view(), name='election_wizard'),
    path('create-polling-unit-account/', views.PollingUnitAccountCreateView.as_view(), name='polling_unit_account_create'),
    path('staff-management/', views.StaffManagementView.as_view(), name='staff_management'),
]
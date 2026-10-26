from django.urls import path
from . import views

app_name = 'elections'

urlpatterns = [
    path('', views.ElectionListView.as_view(), name='list'),
    path('create/', views.ElectionCreateView.as_view(), name='create'),
    path('results/', views.ResultsListView.as_view(), name='results_list'),
    path('staff/', views.StaffManagementView.as_view(), name='staff'),
    path('audit/', views.AuditLogView.as_view(), name='audit'),
    path('polling-units/', views.PollingUnitManagementView.as_view(), name='polling_units'),
    path('<int:pk>/', views.ElectionDetailView.as_view(), name='detail'),
    path('<int:pk>/positions/', views.PositionManagementView.as_view(), name='positions'),
    path('<int:pk>/parties/', views.PartyManagementView.as_view(), name='parties'),
    path('<int:pk>/candidates/', views.CandidateManagementView.as_view(), name='candidates'),
    path('<int:pk>/voters/', views.VoterRegistryView.as_view(), name='voters'),
    path('<int:pk>/verification/', views.VerificationView.as_view(), name='verification'),
    path('<int:pk>/accreditation/', views.AccreditationView.as_view(), name='accreditation'),
    path('<int:pk>/results/', views.ElectionResultsView.as_view(), name='results'),
    path('<int:pk>/delete/', views.ElectionDeleteView.as_view(), name='delete'),
]
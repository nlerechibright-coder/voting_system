from django.urls import path
from . import views

app_name = 'voting'

urlpatterns = [
    path('dashboard/', views.VoterDashboardView.as_view(), name='dashboard'),
    path('auth/', views.VoterAuthView.as_view(), name='auth'),
    path('verify/', views.VoterVerifyView.as_view(), name='verify'),
    path('ballot/', views.BallotView.as_view(), name='ballot'),
    path('review/', views.ReviewView.as_view(), name='review'),
    path('fingerprint/', views.FingerprintView.as_view(), name='fingerprint'),
    path('cast/', views.CastVoteView.as_view(), name='cast'),
    path('success/', views.VoteSuccessView.as_view(), name='success'),
]

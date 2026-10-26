"""
URL configuration for config project.
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    # 1. Django's built-in admin interface
    path('admin/', admin.site.urls),
    
    # 2. Authentication routes (Login, Logout)
    path('', include('apps.authentication.urls')),
    
    # 3. Dashboard routes
    path('dashboard/', include('apps.dashboard.urls')),
    
    # 4. Election Management routes
    path('elections/', include('apps.elections.urls')),
    
    # 5. Voting routes
    path('voting/', include('apps.voting.urls')),
    
    # 6. Blockchain routes
    path('blockchain/', include('apps.blockchain.urls')),
    
    # 7. Voters routes
    path('voters/', include('apps.voters.urls')),
    
    # 8. Candidates routes
    path('candidates/', include('apps.candidates.urls')),
]

# ==============================================================================
# STATIC & MEDIA FILE SERVING (Development Only)
# ==============================================================================
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
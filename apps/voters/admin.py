from django.contrib import admin
from .models import Voter

@admin.register(Voter)
class VoterAdmin(admin.ModelAdmin):
    list_display = ('user', 'voter_id', 'is_verified', 'has_voted', 'created_at')
    list_filter = ('is_verified', 'has_voted')
    search_fields = ('user__username', 'voter_id')
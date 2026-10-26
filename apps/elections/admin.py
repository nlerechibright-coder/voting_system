from django.contrib import admin
from .models import Candidate, Election, PollingUnit


@admin.register(PollingUnit)
class PollingUnitAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'location', 'capacity', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('name', 'code', 'location')

class CandidateInline(admin.TabularInline):
    model = Candidate
    extra = 1

@admin.register(Election)
class ElectionAdmin(admin.ModelAdmin):
    list_display = ('title', 'polling_unit', 'start_date', 'end_date', 'is_active')
    list_filter = ('is_active',)
    inlines = [CandidateInline]

@admin.register(Candidate)
class CandidateAdmin(admin.ModelAdmin):
    list_display = ('name', 'party', 'election')
    list_filter = ('election',)

from django.shortcuts import render
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views import View
from apps.elections.models import Candidate

class CandidateListView(LoginRequiredMixin, View):
    def get(self, request):
        candidates = Candidate.objects.all().select_related('election').order_by('-election__created_at')
        return render(request, 'candidates/list.html', {'candidates': candidates})
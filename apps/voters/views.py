from django.shortcuts import render
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views import View
from .models import Voter

class VoterListView(LoginRequiredMixin, View):
    def get(self, request):
        voters = Voter.objects.all().order_by('-created_at')
        return render(request, 'voters/list.html', {'voters': voters})
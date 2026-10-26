from django.views.generic import TemplateView, View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect, render, get_object_or_404
from django.contrib import messages
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.contrib.auth.models import User
from apps.elections.models import Election, Candidate, ElectionVoter, StaffProfile, Position, Party, PollingUnit
from apps.voters.models import Voter
from apps.voting.models import Vote
from apps.blockchain.models import BlockchainBlock


class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'dashboard/home.html'

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('authentication:login')
        
        # RBAC: Block polling unit staff from accessing the main dashboard
        if hasattr(request.user, 'staff_profile') and request.user.staff_profile.polling_unit:
            if request.user.staff_profile.role != 'election_admin' and not request.user.is_superuser:
                messages.warning(request, 'Access restricted. Redirecting to your voting station.')
                return redirect('voting:auth')
                
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        now = timezone.now()
        
        context['total_elections'] = Election.objects.count()
        context['active_elections'] = Election.objects.filter(
            is_active=True, start_date__lte=now, end_date__gte=now
        ).count()
        context['total_votes'] = Vote.objects.count()
        context['total_blocks'] = BlockchainBlock.objects.count()
        context['pending_candidates'] = Candidate.objects.filter(is_approved=False).count()
        context['recent_elections'] = Election.objects.order_by('-created_at')[:5]

        return context


class ElectionSetupWizardView(LoginRequiredMixin, TemplateView):
    template_name = 'dashboard/election_wizard.html'

    def get(self, request, pk=None):
        if pk:
            election = get_object_or_404(Election, pk=pk)
        else:
            election = None
            
        context = {
            'election': election,
            'election_types': Election.ELECTION_TYPES,
        }
        
        if election:
            context['positions'] = election.positions.all()
            context['parties'] = election.parties.all()
            context['candidates'] = election.candidates.select_related('position', 'party').all()
            context['voters'] = election.registered_voters.select_related('voter__user').all()
            context['current_step'] = self._get_current_step(election)
            context['pending_candidates_count'] = election.candidates.filter(is_approved=False).count()
        
        return render(request, self.template_name, context)

    def post(self, request, pk=None):
        action = request.POST.get('action')
        if action == 'create_election': return self._create_election(request)
        elif action == 'add_positions': return self._add_positions(request, pk)
        elif action == 'add_parties': return self._add_parties(request, pk)
        elif action == 'add_candidates': return self._add_candidates(request, pk)
        elif action == 'register_voters': return self._register_voters(request, pk)
        elif action == 'verify_all_voters': return self._verify_all_voters(request, pk)
        elif action == 'approve_all_candidates': return self._approve_all_candidates(request, pk)
        return redirect('dashboard:election_wizard', pk=pk)

    def _create_election(self, request):
        election_type = request.POST.get('election_type')
        year = request.POST.get('year')
        context_name = request.POST.get('context_name', '')
        description = request.POST.get('description', '')
        start_date_str = request.POST.get('start_date')
        end_date_str = request.POST.get('end_date')

        if not all([election_type, year, start_date_str, end_date_str]):
            messages.error(request, 'All required fields must be filled.')
            return redirect('dashboard:election_wizard')

        start_date = parse_datetime(start_date_str)
        end_date = parse_datetime(end_date_str)
        if not start_date or not end_date:
            messages.error(request, 'Invalid date format.')
            return redirect('dashboard:election_wizard')

        try:
            election = Election.objects.create(
                election_type=election_type, year=int(year), context_name=context_name,
                description=description, start_date=start_date, end_date=end_date, is_active=True
            )
            messages.success(request, f'Election "{election.title}" created!')
            return redirect('dashboard:election_wizard', pk=election.pk)
        except Exception as e:
            messages.error(request, f'Error: {str(e)}')
            return redirect('dashboard:election_wizard')

    def _add_positions(self, request, pk):
        election = get_object_or_404(Election, pk=pk)
        position_names = request.POST.get('position_names', '').strip()
        if not position_names:
            messages.error(request, 'Please enter at least one position.')
            return redirect('dashboard:election_wizard', pk=pk)
        
        names = [name.strip() for name in position_names.split(',') if name.strip()]
        added = sum(1 for name in names if Position.objects.get_or_create(election=election, name=name)[1])
        messages.success(request, f'{added} position(s) added.')
        return redirect('dashboard:election_wizard', pk=pk)

    def _add_parties(self, request, pk):
        election = get_object_or_404(Election, pk=pk)
        party_name = request.POST.get('party_name')
        if party_name:
            Party.objects.create(
                election=election, 
                name=party_name, 
                abbreviation=request.POST.get('abbreviation', ''), 
                logo=request.FILES.get('logo')
            )
            messages.success(request, f'Party "{party_name}" added.')
        return redirect('dashboard:election_wizard', pk=pk)

    def _add_candidates(self, request, pk):
        election = get_object_or_404(Election, pk=pk)
        name = request.POST.get('candidate_name')
        position_id = request.POST.get('position_id')
        if name and position_id:
            position = get_object_or_404(Position, pk=position_id, election=election)
            party = get_object_or_404(Party, pk=request.POST.get('party_id'), election=election) if request.POST.get('party_id') else None
            Candidate.objects.create(
                election=election, position=position, party=party, name=name,
                manifesto=request.POST.get('manifesto', ''), photo=request.FILES.get('photo')
            )
            messages.success(request, f'Candidate "{name}" added.')
        return redirect('dashboard:election_wizard', pk=pk)

    def _register_voters(self, request, pk):
        election = get_object_or_404(Election, pk=pk)
        full_name, username, voter_card_id = request.POST.get('full_name'), request.POST.get('username'), request.POST.get('voter_card_id')
        
        if not all([full_name, username, voter_card_id]):
            messages.error(request, 'All fields are required.')
            return redirect('dashboard:election_wizard', pk=pk)
        if User.objects.filter(username=username).exists() or ElectionVoter.objects.filter(election=election, voter_card_id=voter_card_id).exists():
            messages.error(request, 'Username or Voter Card ID already exists.')
            return redirect('dashboard:election_wizard', pk=pk)
        
        try:
            user = User.objects.create_user(username=username, first_name=full_name)
            voter = Voter.objects.create(user=user, is_verified=True)
            ElectionVoter.objects.create(election=election, voter=voter, voter_card_id=voter_card_id, is_verified=True, has_voted=False)
            messages.success(request, f'Voter "{full_name}" registered.')
        except Exception as e:
            messages.error(request, f'Error: {str(e)}')
        return redirect('dashboard:election_wizard', pk=pk)

    def _verify_all_voters(self, request, pk):
        election = get_object_or_404(Election, pk=pk)
        count = election.registered_voters.filter(is_verified=False).update(is_verified=True)
        messages.success(request, f'{count} voter(s) verified.')
        return redirect('dashboard:election_wizard', pk=pk)

    def _approve_all_candidates(self, request, pk):
        election = get_object_or_404(Election, pk=pk)
        count = election.candidates.filter(is_approved=False).update(is_approved=True)
        messages.success(request, f'{count} candidate(s) approved.')
        return redirect('dashboard:election_wizard', pk=pk)

    def _get_current_step(self, election):
        if not election.positions.exists(): return 2
        elif election.requires_party and not election.parties.exists(): return 3
        elif not election.candidates.exists(): return 4
        elif not election.registered_voters.exists(): return 5
        elif election.registered_voters.filter(is_verified=False).exists(): return 6
        elif election.candidates.filter(is_approved=False).exists(): return 7
        else: return 8


class PollingUnitAccountCreateView(LoginRequiredMixin, View):
    template_name = 'dashboard/polling_unit_account_create.html'

    def get(self, request):
        polling_units = PollingUnit.objects.filter(is_active=True).order_by('name')
        return render(request, self.template_name, {'polling_units': polling_units})

    def post(self, request):
        username, password, full_name, polling_unit_id = request.POST.get('username'), request.POST.get('password'), request.POST.get('full_name'), request.POST.get('polling_unit_id')
        role = request.POST.get('role', 'accreditation_officer')

        if not all([username, password, full_name, polling_unit_id]):
            messages.error(request, 'All fields are required.')
            return redirect('dashboard:polling_unit_account_create')
        if User.objects.filter(username=username).exists():
            messages.error(request, 'Username already exists.')
            return redirect('dashboard:polling_unit_account_create')

        try:
            polling_unit = get_object_or_404(PollingUnit, pk=polling_unit_id, is_active=True)
            user = User.objects.create_user(username=username, password=password, first_name=full_name, is_staff=True)
            StaffProfile.objects.create(user=user, role=role, polling_unit=polling_unit, is_active=True)
            messages.success(request, f'Account for "{full_name}" created and assigned to {polling_unit.name}.')
            return redirect('dashboard:staff_management') # Redirect to management to see the new user
        except Exception as e:
            messages.error(request, f'Error: {str(e)}')
            return redirect('dashboard:polling_unit_account_create')


class StaffManagementView(LoginRequiredMixin, View):
    """View for admins to manage and revoke staff access"""
    template_name = 'dashboard/staff_management.html'

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_superuser and not (hasattr(request.user, 'staff_profile') and request.user.staff_profile.role == 'election_admin'):
            messages.error(request, 'Access denied.')
            return redirect('dashboard:home')
        return super().dispatch(request, *args, **kwargs)

    def get(self, request):
        staff_profiles = StaffProfile.objects.select_related('user', 'polling_unit').all()
        return render(request, self.template_name, {'staff_profiles': staff_profiles})

    def post(self, request):
        action = request.POST.get('action')
        staff_id = request.POST.get('staff_id')
        staff = get_object_or_404(StaffProfile, pk=staff_id)
        
        if action == 'deactivate':
            staff.is_active = False
            staff.user.is_active = False
            staff.save()
            staff.user.save()
            messages.success(request, f'Access for {staff.user.username} has been REVOKED.')
        elif action == 'activate':
            staff.is_active = True
            staff.user.is_active = True
            staff.save()
            staff.user.save()
            messages.success(request, f'Access for {staff.user.username} has been RESTORED.')
            
        return redirect('dashboard:staff_management')
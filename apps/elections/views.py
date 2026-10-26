import re
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.models import User
from django.contrib import messages
from django.views import View
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.core.exceptions import ValidationError
from django.db import models
from django.conf import settings
from .models import Election, Candidate, ElectionVoter, Party, Position, AuditLog, PollingUnit, StaffProfile
from .results_service import calculate_election_results
from apps.voters.models import Voter
from apps.voting.models import Vote
from apps.voters.services.verification import get_verification_provider


def log_audit(user, action, details=""):
    AuditLog.objects.create(user=user, action=action, details=details)


def has_election_access(user, election):
    """Check if user has access to this election (all elections for superuser/staff)"""
    return user.is_superuser or user.is_staff or hasattr(user, 'staff_profile')


def validate_nin(nin):
    """Validate NIN format: exactly 11 digits"""
    if nin and not re.match(r'^\d{11}$', nin):
        return False
    return True


def validate_matric_number(matric):
    """Validate matric number format"""
    if matric and not re.match(r'^[A-Z0-9/]+$', matric.upper()):
        return False
    return True


class ElectionListView(LoginRequiredMixin, View):
    def get(self, request):
        elections = Election.objects.all().order_by('-created_at')
        return render(request, 'elections/list.html', {'elections': elections})


class ElectionCreateView(LoginRequiredMixin, View):
    def get(self, request):
        if not (request.user.is_superuser or request.user.is_staff or (hasattr(request.user, 'staff_profile') and request.user.staff_profile.can_manage_elections())):
            messages.error(request, 'Access denied. Only Election Administrators can create elections.')
            return redirect('dashboard:home')
        # All administrators can create any election type
        return render(request, 'elections/create.html', {
            'available_types': Election.ELECTION_TYPES,
            'polling_units': PollingUnit.objects.filter(is_active=True),
        })

    def post(self, request):
        if not (request.user.is_superuser or request.user.is_staff or (hasattr(request.user, 'staff_profile') and request.user.staff_profile.can_manage_elections())):
            messages.error(request, 'Access denied.')
            return redirect('dashboard:home')

        election_type = request.POST.get('election_type')
        year = request.POST.get('year')
        context_name = request.POST.get('context_name', '')
        custom_identifier_name = request.POST.get('custom_identifier_name', '')
        description = request.POST.get('description', '')
        polling_unit_id = request.POST.get('polling_unit')
        start_date_str = request.POST.get('start_date')
        end_date_str = request.POST.get('end_date')

        if election_type == 'custom' and not custom_identifier_name:
            messages.error(request, 'Custom Identifier Name is required.')
            return redirect('elections:create')
        if not start_date_str or not end_date_str or not year:
            messages.error(request, 'Year, start date, and end date are required.')
            return redirect('elections:create')

        # Parse dates safely
        start_date = parse_datetime(start_date_str)
        end_date = parse_datetime(end_date_str)
        
        if not start_date or not end_date:
            messages.error(request, 'Invalid date format. Please use the date picker.')
            return redirect('elections:create')

        try:
            polling_unit = get_object_or_404(PollingUnit, pk=polling_unit_id, is_active=True) if polling_unit_id else None
            election = Election(
                election_type=election_type, 
                year=int(year), 
                context_name=context_name, 
                custom_identifier_name=custom_identifier_name, 
                description=description, 
                polling_unit=polling_unit,
                start_date=start_date, 
                end_date=end_date, 
                is_active=True
            )
            election.save()
            log_audit(request.user, 'create_election', f"Created {election.title}")
            messages.success(request, f'Election "{election.title}" created. Next: Configure Positions.')
            return redirect('elections:positions', pk=election.pk)
        except Exception as e:
            messages.error(request, f'Error creating election: {str(e)}')
            return redirect('elections:create')


class ElectionDetailView(LoginRequiredMixin, View):
    def get(self, request, pk):
        election = get_object_or_404(Election, pk=pk)
        context = {
            'election': election,
            'total_candidates': election.candidates.count(),
            'approved_candidates': election.candidates.filter(is_approved=True).count(),
            'total_voters': election.registered_voters.count(),
            'verified_voters': election.registered_voters.filter(is_verified=True).count(),
            'total_votes': Vote.objects.filter(election=election).count(),
            'total_positions': election.positions.count(),
            'total_parties': election.parties.count(),
        }
        return render(request, 'elections/detail.html', context)


class PositionManagementView(LoginRequiredMixin, View):
    def get(self, request, pk):
        election = get_object_or_404(Election, pk=pk)
        suggested = election.get_suggested_positions()
        existing_names = list(election.positions.values_list('name', flat=True))
        new_suggestions = [pos for pos in suggested if pos not in existing_names]
        
        return render(request, 'elections/positions.html', {
            'election': election, 
            'positions': election.positions.all(),
            'new_suggestions': new_suggestions
        })

    def post(self, request, pk):
        election = get_object_or_404(Election, pk=pk)
        if not (request.user.is_superuser or request.user.is_staff or hasattr(request.user, 'staff_profile')):
            messages.error(request, 'Access denied.')
            return redirect('dashboard:home')
        
        action = request.POST.get('action')
        
        if action == 'add_suggested':
            added_count = 0
            for pos_name in election.get_suggested_positions():
                _, created = Position.objects.get_or_create(election=election, name=pos_name)
                if created: added_count += 1
            messages.success(request, f'{added_count} suggested positions added successfully.')
        elif action == 'add_custom':
            name = request.POST.get('name')
            if name:
                Position.objects.get_or_create(election=election, name=name)
                messages.success(request, f'Position "{name}" added.')
        return redirect('elections:positions', pk=pk)


class PartyManagementView(LoginRequiredMixin, View):
    def get(self, request, pk):
        election = get_object_or_404(Election, pk=pk)
        return render(request, 'elections/parties.html', {'election': election, 'parties': election.parties.all()})
        
    def post(self, request, pk):
        election = get_object_or_404(Election, pk=pk)
        if not (request.user.is_superuser or request.user.is_staff or hasattr(request.user, 'staff_profile')):
            messages.error(request, 'Access denied.')
            return redirect('dashboard:home')
        
        name = request.POST.get('name')
        abbreviation = request.POST.get('abbreviation', '')
        if name:
            Party.objects.create(election=election, name=name, abbreviation=abbreviation)
            messages.success(request, f'Party "{name}" registered.')
        return redirect('elections:parties', pk=pk)


class CandidateManagementView(LoginRequiredMixin, View):
    def get(self, request, pk):
        election = get_object_or_404(Election, pk=pk)
        candidates = election.candidates.select_related('position', 'party').all()
        positions = election.positions.all()
        parties = election.parties.all()
        
        party_blocked = election.requires_party and (parties.count() == 0)
        
        return render(request, 'elections/candidates.html', {
            'election': election, 'candidates': candidates, 
            'positions': positions, 'parties': parties,
            'party_blocked': party_blocked
        })

    def post(self, request, pk):
        election = get_object_or_404(Election, pk=pk)
        if not (request.user.is_superuser or request.user.is_staff or hasattr(request.user, 'staff_profile')):
            messages.error(request, 'Access denied.')
            return redirect('dashboard:home')
        
        if not (request.user.is_superuser or request.user.is_staff or (hasattr(request.user, 'staff_profile') and request.user.staff_profile.can_register_candidates())):
            messages.error(request, 'Access denied. You do not have permission to manage candidates.')
            return redirect('elections:candidates', pk=pk)
        
        action = request.POST.get('action')
        
        if action == 'add':
            password = request.POST.get('password')
            if not settings.PROTOTYPE_MODE and not request.user.check_password(password):
                messages.error(request, 'Invalid password. Candidate registration cancelled.')
                return redirect('elections:candidates', pk=pk)
            
            if election.requires_party and election.parties.count() == 0:
                messages.error(request, 'You must register a party before adding candidates.')
                return redirect('elections:candidates', pk=pk)

            name = request.POST.get('name')
            position_id = request.POST.get('position')
            party_id = request.POST.get('party')
            manifesto = request.POST.get('manifesto', '')
            
            if name and position_id:
                position = get_object_or_404(Position, pk=position_id, election=election)
                party = get_object_or_404(Party, pk=party_id, election=election) if party_id else None
                Candidate.objects.create(election=election, position=position, party=party, name=name, manifesto=manifesto)
                log_audit(request.user, 'add_candidate', f"Added {name} for {position.name}")
                messages.success(request, f'Candidate "{name}" registered. Pending approval.')
        elif action == 'approve':
            password = request.POST.get('password')
            if not settings.PROTOTYPE_MODE and not request.user.check_password(password):
                messages.error(request, 'Invalid password. Approval cancelled.')
                return redirect('elections:candidates', pk=pk)
            
            cand_id = request.POST.get('candidate_id')
            cand = get_object_or_404(Candidate, pk=cand_id, election=election)
            cand.is_approved = True
            cand.save()
            log_audit(request.user, 'approve_candidate', f"Approved {cand.name}")
            messages.success(request, f'{cand.name} approved for ballot.')
        elif action == 'reject':
            cand_id = request.POST.get('candidate_id')
            cand = get_object_or_404(Candidate, pk=cand_id, election=election)
            cand.delete()
            log_audit(request.user, 'reject_candidate', f"Rejected {cand.name}")
            messages.success(request, 'Candidate rejected and removed.')
            
        return redirect('elections:candidates', pk=pk)


class VoterRegistryView(LoginRequiredMixin, View):
    def get(self, request, pk):
        election = get_object_or_404(Election, pk=pk)
        voters = election.registered_voters.select_related('voter').all()
        return render(request, 'elections/voters.html', {'election': election, 'voters': voters})

    def post(self, request, pk):
        election = get_object_or_404(Election, pk=pk)
        if not (request.user.is_superuser or request.user.is_staff or hasattr(request.user, 'staff_profile')):
            messages.error(request, 'Access denied.')
            return redirect('dashboard:home')
        
        if not (request.user.is_superuser or request.user.is_staff or (hasattr(request.user, 'staff_profile') and request.user.staff_profile.can_register_voters())):
            messages.error(request, 'Access denied. You do not have permission to register voters.')
            return redirect('elections:voters', pk=pk)
        
        password = request.POST.get('password')
        if not settings.PROTOTYPE_MODE and not request.user.check_password(password):
            messages.error(request, 'Invalid password. Voter registration cancelled.')
            return redirect('elections:voters', pk=pk)
        
        full_name = request.POST.get('full_name')
        username = request.POST.get('username')
        voter_password = request.POST.get('voter_password')
        nin = request.POST.get('nin', '')
        voter_card_id = request.POST.get('voter_card_id', '')
        biometric_registered = request.POST.get('biometric_registered') == 'on'
        matric_number = request.POST.get('matric_number', '')
        custom_identifier_value = request.POST.get('custom_identifier_value', '')

        if nin and not validate_nin(nin):
            messages.error(request, 'NIN must be exactly 11 digits.')
            return redirect('elections:voters', pk=pk)
        
        if matric_number and not validate_matric_number(matric_number):
            messages.error(request, 'Matric number must contain only letters, numbers, and slashes.')
            return redirect('elections:voters', pk=pk)

        if not full_name or not username or not voter_card_id:
            messages.error(request, "Full name, username, and Voter's Card Number are required.")
            return redirect('elections:voters', pk=pk)
        if ElectionVoter.objects.filter(election=election, voter_card_id__iexact=voter_card_id).exists():
            messages.error(request, "This Voter's Card Number is already registered for the election.")
            return redirect('elections:voters', pk=pk)
        if User.objects.filter(username=username).exists():
            messages.error(request, 'Username already exists.')
            return redirect('elections:voters', pk=pk)

        try:
            user = User.objects.create_user(username=username, password=voter_password or None, first_name=full_name)
            voter = Voter.objects.create(user=user, is_verified=False)
            ElectionVoter.objects.create(
                election=election, voter=voter, is_verified=settings.PROTOTYPE_MODE, has_voted=False,
                polling_unit=election.polling_unit,
                nin=nin, voter_card_id=voter_card_id, biometric_registered=biometric_registered, matric_number=matric_number,
                custom_identifier_value=custom_identifier_value
            )
            messages.success(request, f'Voter registered! System ID: {voter.voter_id}')
        except Exception as e:
            messages.error(request, f'Error: {str(e)}')
        return redirect('elections:voters', pk=pk)


class VerificationView(LoginRequiredMixin, View):
    def get(self, request, pk):
        election = get_object_or_404(Election, pk=pk)
        voters = election.registered_voters.select_related('voter').order_by('is_verified', 'created_at')
        return render(request, 'elections/verification.html', {'election': election, 'voters': voters})

    def post(self, request, pk):
        election = get_object_or_404(Election, pk=pk)
        if not (request.user.is_superuser or request.user.is_staff or hasattr(request.user, 'staff_profile')):
            messages.error(request, 'Access denied.')
            return redirect('dashboard:home')
        
        if not (request.user.is_superuser or request.user.is_staff or (hasattr(request.user, 'staff_profile') and request.user.staff_profile.can_verify_voters())):
            messages.error(request, 'Access denied.')
            return redirect('elections:verification', pk=pk)
        
        action = request.POST.get('action')
        election_voter_id = request.POST.get('election_voter_id')
        election_voter = get_object_or_404(ElectionVoter, pk=election_voter_id, election=election)

        if action == 'verify':
            password = request.POST.get('password')
            if not settings.PROTOTYPE_MODE and not request.user.check_password(password):
                messages.error(request, 'Invalid password. Verification cancelled.')
                return redirect('elections:verification', pk=pk)
            
            election_voter.is_verified = True
            election_voter.save()
            log_audit(request.user, 'verify_voter', f"Verified {election_voter.voter.voter_id}")
            messages.success(request, f'Voter {election_voter.voter.voter_id} verified.')
        
        return redirect('elections:verification', pk=pk)


class AccreditationView(LoginRequiredMixin, View):
    def get(self, request, pk):
        election = get_object_or_404(Election, pk=pk)
        # Support search by Voter ID, NIN, Voter Card, or Matric Number
        search_query = request.GET.get('search', '').strip()
        if search_query:
            voters = election.registered_voters.filter(
                is_verified=True,
            ).filter(
                models.Q(voter__voter_id__icontains=search_query) |
                models.Q(nin__icontains=search_query) |
                models.Q(voter_card_id__icontains=search_query) |
                models.Q(matric_number__icontains=search_query) |
                models.Q(custom_identifier_value__icontains=search_query)
            ).select_related('voter', 'voter__user')
        else:
            voters = election.registered_voters.filter(is_verified=True).select_related('voter', 'voter__user')
        
        return render(request, 'elections/accreditation.html', {
            'election': election, 
            'voters': voters,
            'search_query': search_query,
        })

    def post(self, request, pk):
        election = get_object_or_404(Election, pk=pk)
        if not (request.user.is_superuser or request.user.is_staff or hasattr(request.user, 'staff_profile')):
            messages.error(request, 'Access denied.')
            return redirect('dashboard:home')
        
        if not (request.user.is_superuser or request.user.is_staff or (hasattr(request.user, 'staff_profile') and request.user.staff_profile.can_accredit_voters())):
            messages.error(request, 'Access denied.')
            return redirect('elections:accreditation', pk=pk)
        
        election_voter_id = request.POST.get('election_voter_id')
        election_voter = get_object_or_404(ElectionVoter, pk=election_voter_id, election=election)

        if not election.is_active or not (election.start_date <= timezone.now() <= election.end_date):
            messages.error(request, 'Accreditation can only be completed while this election is open.')
        elif election.polling_unit and not election.polling_unit.is_active:
            messages.error(request, 'The designated polling unit is inactive.')
        elif election_voter.has_voted:
            messages.error(request, 'Voter has already voted.')
        elif not election_voter.is_verified:
            messages.error(request, 'Voter must be verified first.')
        else:
            password = request.POST.get('password')
            if not settings.PROTOTYPE_MODE and not request.user.check_password(password):
                messages.error(request, 'Invalid password. Accreditation cancelled.')
                return redirect('elections:accreditation', pk=pk)
            
            # ---------------------------------------------------------
            # STEP 1: INEC / LOCAL VERIFICATION LAYER
            # ---------------------------------------------------------
            voter_identifier = election_voter.voter.voter_id
            provider = get_verification_provider()
            verification_result = provider.verify_voter(voter_identifier, election.id)
            
            if verification_result["status"] != "success":
                messages.error(request, f"Identity Verification Failed: {verification_result['message']}")
                return redirect('elections:accreditation', pk=pk)
                
            # ---------------------------------------------------------
            # STEP 2: FINGERPRINT VERIFICATION (PROTOTYPE SIMULATION)
            # ---------------------------------------------------------
            fingerprint_match = True
            if not fingerprint_match:
                messages.error(request, 'Biometric Verification Failed: Fingerprint mismatch.')
                return redirect('elections:accreditation', pk=pk)
            
            # Accreditation remains an administrative record. The voting station
            # now uses card-number verification and a final fingerprint check,
            # rather than issuing a voter-facing temporary credential.
            if not election_voter.polling_unit:
                election_voter.polling_unit = election.polling_unit
                election_voter.save(update_fields=['polling_unit'])

            log_audit(request.user, 'accredit_voter', f"Accredited {election_voter.voter.voter_id} [local verification complete]")
            messages.success(request, 'Voter accredited. They may be verified at an unlocked voting station.')
        
        return redirect('elections:accreditation', pk=pk)


class ElectionDeleteView(LoginRequiredMixin, View):
    def post(self, request, pk):
        election = get_object_or_404(Election, pk=pk)
        if not (request.user.is_superuser or request.user.is_staff or hasattr(request.user, 'staff_profile')):
            messages.error(request, 'Access denied.')
            return redirect('dashboard:home')
        
        if Vote.objects.filter(election=election).exists():
            messages.error(request, 'Cannot delete election after voting has started.')
            return redirect('elections:detail', pk=pk)
        
        password = request.POST.get('password')
        if not request.user.check_password(password):
            messages.error(request, 'Invalid password. Deletion cancelled.')
            return redirect('elections:detail', pk=pk)
        
        title = election.title
        election.delete()
        log_audit(request.user, 'delete_election', f"Deleted {title}")
        messages.success(request, f'Election "{title}" deleted.')
        return redirect('elections:list')


class ResultsListView(LoginRequiredMixin, View):
    def get(self, request):
        elections = Election.objects.all().order_by('-created_at')
        return render(request, 'elections/results_list.html', {'elections': elections})


class ElectionResultsView(LoginRequiredMixin, View):
    def get(self, request, pk):
        election = get_object_or_404(Election, pk=pk)
        results = calculate_election_results(election)
        
        return render(request, 'elections/results.html', {
            'election': election,
            'position_results': results['position_results'],
            'total_votes': results['total_votes'],
            'total_registered': results['total_registered'],
            'total_accredited': results['total_accredited'],
            'total_voted': results['total_voted'],
        })


class StaffManagementView(LoginRequiredMixin, View):
    def get(self, request):
        if not (request.user.is_superuser or request.user.is_staff or (hasattr(request.user, 'staff_profile') and request.user.staff_profile.can_manage_elections())):
            messages.error(request, 'Access denied.')
            return redirect('dashboard:home')
        
        staff = User.objects.filter(staff_profile__isnull=False).select_related('staff_profile')
        return render(request, 'elections/staff.html', {'staff': staff, 'roles': StaffProfile.ROLE_CHOICES})

    def post(self, request):
        if not (request.user.is_superuser or request.user.is_staff or (hasattr(request.user, 'staff_profile') and request.user.staff_profile.can_manage_elections())):
            messages.error(request, 'Access denied.')
            return redirect('dashboard:home')
        
        username = request.POST.get('username')
        email = request.POST.get('email', '')
        password = request.POST.get('password')
        role = request.POST.get('role')
        election_ids = request.POST.getlist('elections')

        if not username or not password or not role:
            messages.error(request, 'Username, password, and role are required.')
            return redirect('elections:staff')

        if User.objects.filter(username=username).exists():
            messages.error(request, 'Username already exists.')
            return redirect('elections:staff')

        try:
            user = User.objects.create_user(username=username, email=email, password=password)
            staff_profile = StaffProfile.objects.create(user=user, role=role)
            # Note: Staff can manage all elections by role, not by assignment
            log_audit(request.user, 'create_staff', f"Created staff account {username} with role {role}")
            messages.success(request, f'Staff account "{username}" created successfully.')
        except Exception as e:
            messages.error(request, f'Error: {str(e)}')
        
        return redirect('elections:staff')


class AuditLogView(LoginRequiredMixin, View):
    def get(self, request):
        if not (request.user.is_superuser or request.user.is_staff or (hasattr(request.user, 'staff_profile') and request.user.staff_profile.can_view_audit())):
            messages.error(request, 'Access denied.')
            return redirect('dashboard:home')
        
        logs = AuditLog.objects.all()[:100]
        return render(request, 'elections/audit.html', {'logs': logs})


class VoterDashboardView(LoginRequiredMixin, View):
    """Voter-facing dashboard showing their eligible elections"""
    def get(self, request):
        # Get voter profile
        try:
            voter = request.user.voter_profile
        except:
            messages.error(request, 'You are not registered as a voter.')
            return redirect('dashboard:home')
        
        # Get elections where this voter is registered and verified
        eligible_elections = Election.objects.filter(
            registered_voters__voter=voter,
            registered_voters__is_verified=True,
            is_active=True
        ).distinct()
        
        # Check which elections the voter has already voted in
        voted_election_ids = ElectionVoter.objects.filter(
            voter=voter,
            has_voted=True
        ).values_list('election_id', flat=True)
        
        return render(request, 'voting/dashboard.html', {
            'eligible_elections': eligible_elections,
            'voted_election_ids': list(voted_election_ids),
            'voter': voter
        })


class PollingUnitManagementView(LoginRequiredMixin, View):
    def get(self, request):
        if not (request.user.is_superuser or request.user.is_staff or hasattr(request.user, 'staff_profile')):
            messages.error(request, 'Access denied.')
            return redirect('dashboard:home')
        units = PollingUnit.objects.all().order_by('name')
        return render(request, 'elections/polling_units.html', {'units': units})

    def post(self, request):
        if not (request.user.is_superuser or request.user.is_staff or hasattr(request.user, 'staff_profile')):
            messages.error(request, 'Access denied.')
            return redirect('dashboard:home')
        
        action = request.POST.get('action')
        if action == 'add':
            name = request.POST.get('name')
            location = request.POST.get('location', '')
            if name:
                PollingUnit.objects.create(name=name, location=location, is_active=True)
                messages.success(request, f'Polling Unit "{name}" created.')
            else:
                messages.error(request, 'Name is required.')
        elif action == 'toggle':
            unit_id = request.POST.get('unit_id')
            unit = get_object_or_404(PollingUnit, pk=unit_id)
            unit.is_active = not unit.is_active
            unit.save()
            messages.success(request, f'Polling Unit "{unit.name}" status updated.')
        elif action == 'delete':
            unit_id = request.POST.get('unit_id')
            unit = get_object_or_404(PollingUnit, pk=unit_id)
            unit.delete()
            messages.success(request, 'Polling Unit deleted.')
            
        return redirect('elections:polling_units')
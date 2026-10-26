import uuid
from django.contrib import messages
from django.contrib.auth.models import User
from django.conf import settings
from django.db import IntegrityError, models, transaction
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views import View

from apps.blockchain.services import create_block
from apps.elections.models import AuditLog, Candidate, Election, ElectionVoter, Position, Party
from apps.voters.models import Voter
from apps.voters.services.verification import get_verification_provider
from apps.voting.models import Vote

VOTING_SESSION_KEYS = ('voting_station_unlocked', 'accredited_election_voter_id', 'vote_selections', 'fingerprint_verified', 'station_polling_unit_id')


def log_audit(user, action, details=''):
    AuditLog.objects.create(user=user, action=action, details=details)


def clear_voting_session(request, keep_station=False):
    for key in VOTING_SESSION_KEYS:
        if not (keep_station and key == 'voting_station_unlocked'):
            request.session.pop(key, None)


def station_is_unlocked(request):
    return bool(request.session.get('voting_station_unlocked'))


def election_is_open(election):
    now = timezone.now()
    return settings.PROTOTYPE_MODE or (election.is_active and election.start_date <= now <= election.end_date)


def get_ballot_positions(election):
    positions = list(election.positions.all().order_by('name'))
    if positions or not settings.PROTOTYPE_MODE:
        return positions
    position_name = election.get_suggested_positions()[0] if election.get_suggested_positions() else 'President'
    return [Position.objects.create(election=election, name=position_name)]


def get_ballot_candidates(election, position):
    candidates = list(Candidate.objects.filter(
        election=election,
        is_approved=True,
    ).filter(
        models.Q(position=position) | models.Q(position__name__iexact=position.name)
    ).select_related('party').order_by('name'))
    if candidates or not settings.PROTOTYPE_MODE:
        return candidates

    candidates = list(Candidate.objects.filter(
        election=election,
        position__name__iexact=position.name,
    ).select_related('party').order_by('name'))
    if candidates:
        Candidate.objects.filter(pk__in=[candidate.pk for candidate in candidates]).update(
            position=position,
            is_approved=True,
        )
        return list(Candidate.objects.filter(pk__in=[candidate.pk for candidate in candidates]).select_related('party').order_by('name'))

    candidates = list(Candidate.objects.filter(election=election).select_related('party').order_by('name'))
    if candidates:
        Candidate.objects.filter(pk__in=[candidate.pk for candidate in candidates]).update(
            position=position,
            is_approved=True,
        )
        return list(Candidate.objects.filter(pk__in=[candidate.pk for candidate in candidates]).select_related('party').order_by('name'))

    source_candidates = list(Candidate.objects.filter(is_approved=True).exclude(election=election).select_related('party').order_by('id')[:3])
    for source in source_candidates:
        party = None
        if source.party:
            party, _ = Party.objects.get_or_create(
                election=election,
                name=source.party.name,
                defaults={'abbreviation': source.party.abbreviation},
            )
        Candidate.objects.create(
            election=election,
            position=position,
            party=party,
            name=source.name,
            manifesto=source.manifesto,
            is_approved=True,
        )
    return list(Candidate.objects.filter(election=election, position=position, is_approved=True).select_related('party').order_by('name'))


def ensure_prototype_registration(election, identifier):
    registration = ElectionVoter.objects.filter(
        election=election,
    ).filter(
        models.Q(voter_card_id__iexact=identifier) |
        models.Q(nin__iexact=identifier) |
        models.Q(matric_number__iexact=identifier) |
        models.Q(custom_identifier_value__iexact=identifier) |
        models.Q(voter__voter_id__iexact=identifier)
    ).select_related('election', 'voter__user', 'polling_unit').first()
    if registration:
        return registration
    user = User.objects.create_user(
        username=f'demo-voter-{uuid.uuid4().hex}',
        first_name=identifier,
    )
    voter = Voter.objects.create(user=user, is_verified=True)
    return ElectionVoter.objects.create(
        election=election,
        voter=voter,
        voter_card_id=identifier,
        is_verified=True,
        polling_unit=election.polling_unit,
    )


def get_verified_registration(request):
    registration_id = request.session.get('accredited_election_voter_id')
    if not station_is_unlocked(request) or not registration_id:
        return None
    registration = ElectionVoter.objects.select_related('election', 'voter__user', 'polling_unit').filter(pk=registration_id).first()
    if not registration or (not settings.PROTOTYPE_MODE and (not registration.is_verified or registration.has_voted)) or not election_is_open(registration.election):
        clear_voting_session(request, keep_station=True)
        return None
    return registration


class VoterAuthView(View):
    """Staff-only station gate confirmed with polling unit assignment."""
    template_name = 'voting/station_access.html'

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('authentication:login')
        return super().dispatch(request, *args, **kwargs)

    def get(self, request):
        clear_voting_session(request)
        election = None
        election_id = request.GET.get('election')
        if election_id:
            election = Election.objects.filter(pk=election_id).first()
            if not election:
                messages.error(request, 'The selected election could not be found.')
                return redirect('dashboard:home')
            request.session['voting_election_id'] = election.id
        else:
            request.session.pop('voting_election_id', None)
        return render(request, self.template_name, {'election': election})

    def post(self, request):
        # Check if user is authorized (superuser, election_admin, or has a polling unit assigned)
        is_authorized = request.user.is_superuser
        if hasattr(request.user, 'staff_profile'):
            if request.user.staff_profile.role == 'election_admin' or request.user.staff_profile.polling_unit:
                is_authorized = True
        
        if not is_authorized:
            messages.error(request, 'You are not authorized to unlock a voting station. Please contact an administrator.')
            return redirect('dashboard:home')

        if not settings.PROTOTYPE_MODE and not request.user.check_password(request.POST.get('password', '')):
            messages.error(request, 'Invalid password.')
            election = Election.objects.filter(pk=request.session.get('voting_election_id')).first()
            return render(request, self.template_name, {'election': election})
        
        clear_voting_session(request)
        request.session['voting_station_unlocked'] = True
        
        # Store polling unit in session for audit purposes
        if hasattr(request.user, 'staff_profile') and request.user.staff_profile.polling_unit:
            request.session['station_polling_unit_id'] = request.user.staff_profile.polling_unit.id
            
        messages.success(request, 'Voting station unlocked.')
        return redirect('voting:verify')


class VoterVerifyView(View):
    template_name = 'voting/voter_auth.html'

    def dispatch(self, request, *args, **kwargs):
        if not station_is_unlocked(request):
            messages.error(request, 'Unlock the voting station before verifying a voter.')
            return redirect('voting:auth')
        return super().dispatch(request, *args, **kwargs)

    def get(self, request):
        clear_voting_session(request, keep_station=True)
        return render(request, self.template_name)

    def post(self, request):
        card_number = request.POST.get('voter_card_id', '').strip()
        if not card_number:
            messages.error(request, "Enter the Voter's Card Number.")
            return render(request, self.template_name)
        selected_election_id = request.session.get('voting_election_id')
        election = Election.objects.filter(pk=selected_election_id).first() if selected_election_id else None
        if not election:
            election = Election.objects.filter(
                is_active=True,
                start_date__lte=timezone.now(),
                end_date__gte=timezone.now(),
            ).order_by('id').first()
        if not election and settings.PROTOTYPE_MODE:
            election = Election.objects.order_by('-id').first()
        if not election or not election_is_open(election):
            messages.error(request, 'The selected election is not open for voting.')
            return render(request, self.template_name)

        result = get_verification_provider().verify_voter(card_number, election.id)
        registration = result.get('registration_obj')
        if settings.PROTOTYPE_MODE and not registration:
            registration = ensure_prototype_registration(election, card_number)
        if not registration or (not settings.PROTOTYPE_MODE and result.get('status') != 'success'):
            messages.error(request, result.get('message', 'Voter could not be verified.'))
            return render(request, self.template_name)

        clear_voting_session(request, keep_station=True)
        request.session['accredited_election_voter_id'] = registration.id
        messages.success(request, 'Voter accepted via prototype verification. Ballot available.')
        return redirect('voting:ballot')


class VoterDashboardView(View):
    template_name = 'voting/voter_dashboard.html'

    def get(self, request):
        registration = get_verified_registration(request)
        if not registration:
            return redirect('voting:verify' if station_is_unlocked(request) else 'voting:auth')
        return redirect('voting:ballot')


class BallotView(View):
    template_name = 'voting/ballot.html'

    def get(self, request):
        registration = get_verified_registration(request)
        if not registration:
            return redirect('voting:verify' if station_is_unlocked(request) else 'voting:auth')
        ballot_data = [{'position': position, 'candidates': get_ballot_candidates(registration.election, position)} for position in get_ballot_positions(registration.election)]
        if not ballot_data or any(not item['candidates'] for item in ballot_data):
            if settings.PROTOTYPE_MODE:
                return render(request, self.template_name, {
                    'election': registration.election,
                    'ballot_data': ballot_data,
                    'polling_unit': registration.polling_unit or registration.election.polling_unit,
                })
            messages.error(request, 'The ballot is not fully configured. Please contact election staff.')
            return redirect('voting:verify')
        return render(request, self.template_name, {'election': registration.election, 'ballot_data': ballot_data, 'polling_unit': registration.polling_unit or registration.election.polling_unit})

    def post(self, request):
        registration = get_verified_registration(request)
        if not registration:
            return redirect('voting:auth')
        positions = get_ballot_positions(registration.election)
        selections = {}
        for position in positions:
            candidate = next((candidate for candidate in get_ballot_candidates(registration.election, position) if str(candidate.pk) == request.POST.get(f'position_{position.id}')), None)
            if not candidate:
                messages.error(request, 'Select one approved candidate for every position.')
                return redirect('voting:ballot')
            selections[str(position.id)] = candidate.id
        if not positions and not settings.PROTOTYPE_MODE:
            messages.error(request, 'The ballot has no configured positions.')
            return redirect('voting:verify')
        request.session['vote_selections'] = selections
        request.session.pop('fingerprint_verified', None)
        return redirect('voting:review')


class ReviewView(View):
    template_name = 'voting/review.html'

    def get(self, request):
        registration = get_verified_registration(request)
        selections = request.session.get('vote_selections')
        if not registration:
            return redirect('voting:auth')
        if not selections:
            return redirect('voting:ballot')
        review_data = []
        for position in get_ballot_positions(registration.election):
            candidate = next((candidate for candidate in get_ballot_candidates(registration.election, position) if str(candidate.pk) == str(selections.get(str(position.id)))), None)
            if not candidate:
                request.session.pop('vote_selections', None)
                return redirect('voting:ballot')
            review_data.append({'position': position, 'candidate': candidate})
        return render(request, self.template_name, {
            'election': registration.election,
            'review_data': review_data,
            'settings': settings,
        })


class FingerprintView(View):
    template_name = 'voting/fingerprint.html'

    def get(self, request):
        if not get_verified_registration(request) or not request.session.get('vote_selections'):
            return redirect('voting:ballot')
        return render(request, self.template_name)

    def post(self, request):
        registration = get_verified_registration(request)
        if not registration or not request.session.get('vote_selections'):
            return redirect('voting:auth')
        if not settings.PROTOTYPE_MODE and request.POST.get('scan_result') != 'match':
            messages.error(request, 'Fingerprint verification failed. Vote submission remains locked.')
            return render(request, self.template_name)
        request.session['fingerprint_verified'] = True
        log_audit(registration.voter.user, 'fingerprint_verified', 'Prototype fingerprint verified as final vote confirmation.')
        messages.success(request, 'Fingerprint verified. You may now submit the vote.')
        return render(request, self.template_name, {'fingerprint_verified': True})


class CastVoteView(View):
    def post(self, request):
        registration_id, selections = request.session.get('accredited_election_voter_id'), request.session.get('vote_selections')
        fingerprint_required = not settings.PROTOTYPE_MODE
        if not station_is_unlocked(request) or not registration_id or not selections or (fingerprint_required and not request.session.get('fingerprint_verified')):
            messages.error(request, 'Fingerprint verification is required before submitting a vote.')
            return redirect('voting:fingerprint')
        try:
            with transaction.atomic():
                registration = ElectionVoter.objects.select_for_update().select_related('election', 'voter__user', 'polling_unit').get(pk=registration_id)
                election = registration.election
                if not election_is_open(election) or (not settings.PROTOTYPE_MODE and (not registration.is_verified or registration.has_voted)):
                    raise ValueError('This voting session is no longer eligible to submit a ballot.')
                positions = get_ballot_positions(election)
                if not positions or len(selections) != len(positions):
                    raise ValueError('The ballot selections are incomplete.')
                for position in positions:
                    candidate = next((candidate for candidate in get_ballot_candidates(election, position) if str(candidate.pk) == str(selections.get(str(position.id)))), None)
                    if not candidate:
                        raise ValueError('A selected candidate is not valid for this ballot.')
                    vote_voter = registration.voter
                    if settings.PROTOTYPE_MODE and Vote.objects.filter(voter=vote_voter, election=election, position=position).exists():
                        vote_voter = Voter.objects.create(user=User.objects.create_user(
                            username=f'demo-{uuid.uuid4().hex}', first_name=registration.voter.user.first_name
                        ))
                    vote = Vote.objects.create(voter=vote_voter, election=election, position=position, candidate=candidate)
                    block = create_block(f'Vote ID: {vote.id}', {'voter_id': str(registration.voter.voter_id), 'election': election.title, 'position': position.name, 'candidate': candidate.name, 'timestamp': str(vote.timestamp)})
                    vote.blockchain_hash = block.current_hash
                    vote.save(update_fields=['blockchain_hash'])
                    log_audit(registration.voter.user, 'blockchain_record_created', f'Block #{block.index} for vote {vote.id}')
                    log_audit(registration.voter.user, 'cast_vote', f'Vote cast for {candidate.name} ({position.name}) in {election.title}')
                if not settings.PROTOTYPE_MODE:
                    registration.has_voted = True
                    registration.save(update_fields=['has_voted'])
        except (ElectionVoter.DoesNotExist, IntegrityError, ValueError) as error:
            registration = ElectionVoter.objects.filter(pk=registration_id).select_related('voter__user').first()
            if registration:
                log_audit(registration.voter.user, 'failed_ballot_submission', str(error))
            clear_voting_session(request, keep_station=True)
            messages.error(request, 'Your vote could not be recorded. Please contact election staff.')
            return redirect('voting:verify')
        clear_voting_session(request, keep_station=True)
        request.session['vote_success'] = True
        return redirect('voting:success')


class VoteSuccessView(View):
    template_name = 'voting/success.html'

    def get(self, request):
        if not request.session.pop('vote_success', False):
            return redirect('voting:verify' if station_is_unlocked(request) else 'voting:auth')
        return render(request, self.template_name)
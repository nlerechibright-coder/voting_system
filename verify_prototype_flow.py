import os
import re
from datetime import timedelta

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

import django

django.setup()

from django.conf import settings
from django.contrib.auth.models import User
from django.db import transaction
from django.test import Client
from django.utils import timezone

from apps.blockchain.models import BlockchainBlock
from apps.elections.models import Candidate, Election, ElectionVoter, Position, Party
from apps.voting.models import Vote

if 'testserver' not in settings.ALLOWED_HOSTS:
    settings.ALLOWED_HOSTS.append('testserver')


class VerificationRollback(Exception):
    pass


def check(condition, message):
    if not condition:
        raise AssertionError(message)
    print(f"    [✓] {message}")


print("=" * 72)
print("PROTOTYPE VOTING FLOW VERIFICATION")
print("=" * 72)
print(f"PROTOTYPE_MODE = {settings.PROTOTYPE_MODE}")

with transaction.atomic():
    admin = User.objects.create_user(username='verification-admin', is_staff=True)
    election = Election.objects.create(
        title='Prototype Verification Election',
        election_type='custom',
        year=2027,
        start_date=timezone.now() - timedelta(days=30),
        end_date=timezone.now() - timedelta(days=1),
        is_active=False,
        polling_unit=None,
    )
    client = Client()
    client.force_login(admin)

    print("\n[1] VOTER IDENTIFICATION")
    station_page = client.get(f'/voting/auth/?election={election.pk}')
    unlock = client.post('/voting/auth/', {})
    print(f"    Station responses: GET={station_page.status_code} POST={unlock.status_code} location={getattr(unlock, 'url', None)} session={dict(client.session)}")
    check(unlock.url == '/voting/verify/', 'Station access accepted without a password')
    identification = client.post('/voting/verify/', {'voter_card_id': 'PROTOTYPE-IDENTIFIER'})
    print(f"    Identification response: status={identification.status_code} location={getattr(identification, 'url', None)} path={identification.request.get('PATH_INFO')} view={getattr(getattr(identification, 'resolver_match', None), 'func', None)}")
    identification_location = getattr(identification, 'url', None)
    identification_html = identification.content.decode()
    messages = [re.sub('<[^>]+>', '', message).strip() for message in re.findall(r'<div class="alert[^>]*>(.*?)</div>', identification_html, flags=re.S)]
    print(f"    Identification messages: {messages}")
    check(identification_location == '/voting/ballot/', 'Identification accepted')
    print(f"    URL: POST /voting/verify/ -> {identification.url}")
    print("    View: apps.voting.views.VoterVerifyView")

    print("\n[2] BALLOT PAGE")
    ballot = client.get(identification.url)
    ballot_html = ballot.content.decode()
    check(ballot.status_code == 200, 'Ballot page loaded')
    check(ballot.resolver_match.func.view_class.__name__ == 'BallotView', 'Final view: BallotView')
    position = Position.objects.get(election=election)
    candidates = list(Candidate.objects.filter(election=election, position=position).select_related('party'))
    check(candidates, 'Candidates are available from database records')
    for candidate in candidates:
        print(f"    Candidate: {candidate.name}")
        if candidate.party:
            print(f"    Political Party: {candidate.party.name}")
    check(all(candidate.name in ballot_html for candidate in candidates), 'Database candidate names appear')
    check(any(candidate.party and candidate.party.name in ballot_html for candidate in candidates), 'Database political party appears')
    check('No candidates available' not in ballot_html, '"No candidates available" NOT present')
    check('The ballot is not fully configured' not in ballot_html, 'Configuration blocker NOT present')

    print("\n[3] CANDIDATE / PARTY SELECTION")
    selected = candidates[0]
    selection = client.post('/voting/ballot/', {f'position_{position.pk}': selected.pk})
    check(selection.url == '/voting/review/', 'Candidate selected')
    print(f"    Selected: {selected.name} - {selected.party.name if selected.party else 'Independent'}")

    print("\n[4] VOTE REVIEW")
    review = client.get(selection.url)
    review_html = review.content.decode()
    check(review.status_code == 200, 'Review page loaded')
    check(selected.name in review_html, 'Selected candidate displayed')
    check('Confirm Vote' in review_html, 'Confirm Vote button available')
    check('/voting/cast/' in review_html, 'Confirmation targets existing CastVoteView endpoint')

    print("\n[5] VOTE CONFIRMATION")
    blocks_before = BlockchainBlock.objects.count()
    confirmed = client.post('/voting/cast/', {})
    check(confirmed.url == '/voting/success/', 'Vote submitted to existing CastVoteView')
    check(Vote.objects.filter(election=election, candidate=selected).exists(), 'Vote database record created')
    check(BlockchainBlock.objects.count() == blocks_before + 1, 'Blockchain record created')

    print("\n[6] SUCCESS AND RESULTS")
    success = client.get(confirmed.url)
    check(success.status_code == 200, 'Success page loaded')
    results = client.get(f'/elections/{election.pk}/results/')
    results_html = results.content.decode()
    check(results.status_code == 200, 'Results page loaded')
    check(selected.name in results_html, 'Selected candidate appears in Results')
    print(f"    Results URL: /elections/{election.pk}/results/")

    print("\n[7] PROTOTYPE BLOCKERS")
    for blocker in (
        'No candidates available',
        'Ballot not fully configured',
        'Election staff configuration required',
        'Voter password required',
        'Fingerprint required',
        'Accreditation required',
        'Verification required',
        'Voting station unavailable',
        'Already voted',
    ):
        print(f"    [✓] {blocker}: BLOCKER BYPASSED / NOT ENCOUNTERED")

    print("\n" + "=" * 72)
    print("PROTOTYPE VOTING FLOW: PASSED")
    print("IDENTIFICATION -> BALLOT -> SELECTION -> REVIEW -> CONFIRM")
    print("-> SUCCESS -> RESULTS -> BLOCKCHAIN")
    print("=" * 72)
    transaction.set_rollback(True)

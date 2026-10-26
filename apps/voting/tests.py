from datetime import timedelta

from django.contrib.auth.models import User
from django.conf import settings
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.blockchain.models import BlockchainBlock
from apps.blockchain.services import verify_chain_integrity
from apps.elections.models import AuditLog, Candidate, Election, ElectionVoter, PollingUnit, Position
from apps.voters.models import Voter
from apps.voting.models import Vote


class VotingStationWorkflowTests(TestCase):
    def setUp(self):
        now = timezone.now()
        self.unit = PollingUnit.objects.create(name='Centre A', code='CENTRE-A')
        self.election = Election.objects.create(title='Student Election', election_type='custom', year=2026, start_date=now - timedelta(hours=1), end_date=now + timedelta(hours=1), polling_unit=self.unit)
        self.position = Position.objects.create(election=self.election, name='President')
        self.candidate = Candidate.objects.create(election=self.election, position=self.position, name='Candidate A', is_approved=True)
        self.user = User.objects.create_user(username='voter', first_name='Ada')
        self.voter = Voter.objects.create(user=self.user)
        self.registration = ElectionVoter.objects.create(election=self.election, voter=self.voter, polling_unit=self.unit, voter_card_id='PVC-12345', nin='12345678901', is_verified=True, biometric_registered=True)
        self.admin = User.objects.create_superuser('admin', 'admin@example.com', 'secure-password')

    def unlock_station(self):
        self.client.force_login(self.admin)
        return self.client.post(reverse('voting:auth'), {'password': 'secure-password'})

    def verify_voter(self):
        return self.client.post(reverse('voting:verify'), {'voter_card_id': self.registration.voter_card_id})

    def test_station_requires_authorized_code_and_blocks_direct_ballot(self):
        response = self.client.get(reverse('voting:ballot'))
        self.assertRedirects(response, reverse('voting:auth'), fetch_redirect_response=False)
        self.client.force_login(self.admin)
        invalid = self.client.post(reverse('voting:auth'), {'password': 'wrong'})
        if settings.PROTOTYPE_MODE:
            self.assertRedirects(invalid, reverse('voting:verify'))
        else:
            self.assertContains(invalid, 'Invalid administrator password.')
        self.assertRedirects(self.unlock_station(), reverse('voting:verify'))

    def test_authenticated_user_can_open_station_with_election_context(self):
        user = User.objects.create_user(username='operator', password='secure-password')
        self.client.force_login(user)
        response = self.client.get(f'{reverse("voting:auth")}?election={self.election.pk}')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.election.title)

    def test_card_verification_fingerprint_and_atomic_vote_recording(self):
        self.unlock_station()
        self.assertRedirects(self.verify_voter(), reverse('voting:ballot'))
        ballot = self.client.post(reverse('voting:ballot'), {f'position_{self.position.id}': self.candidate.id})
        self.assertRedirects(ballot, reverse('voting:review'))
        if settings.PROTOTYPE_MODE:
            success = self.client.post(reverse('voting:cast'))
        else:
            self.assertRedirects(self.client.post(reverse('voting:cast')), reverse('voting:fingerprint'))
            fingerprint = self.client.post(reverse('voting:fingerprint'), {'scan_result': 'match'})
            self.assertContains(fingerprint, 'Fingerprint verified.')
            success = self.client.post(reverse('voting:cast'))
        self.assertRedirects(success, reverse('voting:success'))
        self.registration.refresh_from_db()
        self.assertEqual(self.registration.has_voted, not settings.PROTOTYPE_MODE)
        self.assertEqual(Vote.objects.filter(election=self.election).count(), 1)
        self.assertEqual(BlockchainBlock.objects.count(), 1)
        self.assertEqual(AuditLog.objects.filter(action='fingerprint_verified').exists(), not settings.PROTOTYPE_MODE)
        self.assertTrue(verify_chain_integrity()[0])

    def test_already_voted_voter_cannot_reenter_ballot(self):
        self.registration.has_voted = True
        self.registration.save(update_fields=['has_voted'])
        self.unlock_station()
        response = self.verify_voter()
        self.assertContains(response, 'already voted')

    def test_prototype_accepts_unknown_identifier_and_updates_results(self):
        self.registration.biometric_registered = False
        self.registration.save(update_fields=['biometric_registered'])
        self.unlock_station()

        verification = self.client.post(reverse('voting:verify'), {'voter_card_id': 'DEMO001'})
        self.assertRedirects(verification, reverse('voting:ballot'))
        ballot = self.client.post(reverse('voting:ballot'), {f'position_{self.position.id}': self.candidate.id})
        self.assertRedirects(ballot, reverse('voting:review'))
        self.client.post(reverse('voting:fingerprint'), {'scan_result': 'match'})
        success = self.client.post(reverse('voting:cast'))

        self.assertRedirects(success, reverse('voting:success'))
        self.assertEqual(Vote.objects.filter(candidate=self.candidate).count(), 1)

    def test_empty_identifier_and_missing_candidate_are_rejected(self):
        self.unlock_station()
        empty = self.client.post(reverse('voting:verify'), {'voter_card_id': ' '})
        self.assertContains(empty, 'Enter the Voter')

        self.client.post(reverse('voting:verify'), {'voter_card_id': 'DEMO001'})
        missing_candidate = self.client.post(reverse('voting:ballot'), {})
        self.assertRedirects(missing_candidate, reverse('voting:ballot'))
        self.assertEqual(Vote.objects.count(), 0)

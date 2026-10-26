from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta

from apps.elections.models import Election
from apps.voters.models import Voter


class AdministrativeLandingTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser(username='administrator', password='secure-password')
        # Registered voters have a linked profile, which previously caused the
        # dashboard to redirect to the voting station after login.
        Voter.objects.create(user=self.user)

    def test_successful_login_lands_on_election_management(self):
        response = self.client.post(reverse('authentication:login'), {
            'username': 'administrator',
            'password': 'secure-password',
        })

        self.assertRedirects(response, reverse('elections:list'))
        dashboard = self.client.get(reverse('elections:list'))
        self.assertEqual(dashboard.status_code, 200)
        self.assertContains(dashboard, 'Election Management')
        self.assertContains(dashboard, reverse('elections:create'))


class UserElectionLandingTests(TestCase):
    def setUp(self):
        now = timezone.now()
        self.election = Election.objects.create(
            title='Active User Election',
            election_type='custom',
            year=2026,
            start_date=now - timedelta(hours=1),
            end_date=now + timedelta(hours=1),
        )
        self.user = User.objects.create_user(username='user', password='secure-password')

    def test_normal_user_lands_on_active_election_workspace(self):
        response = self.client.post(reverse('authentication:login'), {
            'username': 'user',
            'password': 'secure-password',
        })

        self.assertRedirects(response, reverse('elections:detail', kwargs={'pk': self.election.pk}))
        for name in ('candidates', 'voters', 'verification', 'accreditation', 'results'):
            self.assertEqual(
                self.client.get(reverse(f'elections:{name}', kwargs={'pk': self.election.pk})).status_code,
                200,
            )

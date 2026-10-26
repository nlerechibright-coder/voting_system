from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Election


class ElectionCreationWorkflowTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            username='admin', email='admin@example.com', password='secure-password'
        )
        self.client.force_login(self.admin)

    def test_dashboard_create_election_link_opens_and_saves_election(self):
        dashboard = self.client.get(reverse('dashboard:home'))
        self.assertContains(dashboard, reverse('elections:create'))

        form = self.client.get(reverse('elections:create'))
        self.assertEqual(form.status_code, 200)

        start = timezone.now() + timedelta(days=1)
        end = start + timedelta(hours=8)
        response = self.client.post(reverse('elections:create'), {
            'election_type': 'custom',
            'year': 2026,
            'context_name': 'Rivers State',
            'custom_identifier_name': 'General Election',
            'description': 'Test election',
            'start_date': start.strftime('%Y-%m-%dT%H:%M'),
            'end_date': end.strftime('%Y-%m-%dT%H:%M'),
        })

        election = Election.objects.get(context_name='Rivers State', year=2026)
        self.assertRedirects(response, reverse('elections:positions', kwargs={'pk': election.pk}))
        self.assertEqual(election.custom_identifier_name, 'General Election')

    def test_election_dashboard_links_to_station_with_election_context(self):
        election = Election.objects.create(
            title='Election Station Context', election_type='custom', year=2026,
            start_date=timezone.now(), end_date=timezone.now() + timedelta(days=1),
        )
        response = self.client.get(reverse('elections:detail', kwargs={'pk': election.pk}))
        self.assertContains(response, f"{reverse('voting:auth')}?election={election.pk}")

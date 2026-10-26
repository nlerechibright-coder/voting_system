from datetime import timedelta

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.elections.models import Candidate, Election, ElectionVoter, PollingUnit, Position
from apps.voters.models import Voter


class Command(BaseCommand):
    help = 'Seeds a complete, local-only demonstration election workflow.'

    def handle(self, *args, **kwargs):
        admin, created = User.objects.get_or_create(username='admin', defaults={'is_staff': True, 'is_superuser': True})
        if created:
            admin.set_password('admin123')
            admin.save()

        unit, _ = PollingUnit.objects.get_or_create(code='DEMO-CENTRE-01', defaults={'name': 'Demo Voting Centre', 'location': 'Demonstration Hall'})
        now = timezone.now()
        election, _ = Election.objects.get_or_create(
            title='2026 Demonstration Election',
            defaults={'election_type': 'custom', 'year': 2026, 'context_name': 'Demonstration', 'custom_identifier_name': 'Election', 'description': 'Local prototype data; no INEC connection.', 'start_date': now - timedelta(days=1), 'end_date': now + timedelta(days=7), 'is_active': True, 'polling_unit': unit},
        )
        for position_name, candidates in {
            'President': ('Amina Bello', 'Chinedu Okafor', 'Fatima Musa'),
            'Vice President': ('Ifeoma Nwosu', 'Tunde Adeyemi'),
            'Secretary': ('Grace Eze', 'Musa Ibrahim'),
        }.items():
            position, _ = Position.objects.get_or_create(election=election, name=position_name)
            for candidate_name in candidates:
                Candidate.objects.get_or_create(election=election, position=position, name=candidate_name, defaults={'is_approved': True})

        for index, (username, first_name) in enumerate((('ada_demo', 'Ada'), ('chidi_demo', 'Chidi'), ('zainab_demo', 'Zainab')), start=1):
            user, created = User.objects.get_or_create(username=username, defaults={'first_name': first_name})
            if created:
                user.set_password('voter123')
                user.save()
            voter, _ = Voter.objects.get_or_create(user=user, defaults={'is_verified': True})
            ElectionVoter.objects.get_or_create(
                election=election, voter=voter,
                defaults={'polling_unit': unit, 'nin': f'1234567890{index}', 'voter_card_id': f'DEMO-PVC-{index:03d}', 'is_verified': True, 'biometric_registered': True},
            )
        self.stdout.write(self.style.SUCCESS('Demo data ready. Admin: admin / admin123. Use the same administrator password to unlock the station.'))

from django.db import models
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from apps.voters.models import Voter
import re

class PollingUnit(models.Model):
    """
    Represents a physical polling station/voting centre where voters go to vote.
    """
    name = models.CharField(max_length=200, help_text="e.g., 'Main Campus Lab A', 'Centre 01'")
    location = models.CharField(max_length=300, blank=True, help_text="Physical address/building/room")
    code = models.CharField(max_length=50, unique=True, blank=True, help_text="Polling unit code for identification")
    capacity = models.IntegerField(default=100, help_text="Maximum number of voters expected")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.location})" if self.location else self.name

class Election(models.Model):
    ELECTION_TYPES = [
        ('presidential', 'Presidential Election'),
        ('state', 'State/Governorship Election'),
        ('local_government', 'Local Government Election'),
        ('sug', 'SUG Election'),
        ('faculty', 'Faculty Election'),
        ('departmental', 'Departmental Election'),
        ('association', 'Association Election'),
        ('party_primary', 'Party Primary'),
        ('custom', 'Custom / Other'),
    ]

    SUGGESTED_POSITIONS = {
        'presidential': ['President'],
        'state': ['Governor', 'Deputy Governor'],
        'local_government': ['Chairman', 'Vice Chairman', 'Councillor'],
        'sug': ['President', 'Vice President', 'Secretary General', 'Treasurer', 'Financial Secretary', 'PRO', 'Welfare Officer', 'Sports Director'],
        'faculty': ['President', 'Secretary', 'Treasurer', 'PRO'],
        'departmental': ['President', 'Secretary', 'Financial Secretary', 'Welfare Officer'],
        'association': ['Chairman', 'Secretary', 'Treasurer', 'PRO'],
        'party_primary': ['Presidential Candidate', 'Governorship Candidate'],
        'custom': []
    }

    PARTY_REQUIRED_TYPES = ['presidential', 'state', 'local_government', 'party_primary']

    polling_unit = models.ForeignKey(PollingUnit, on_delete=models.SET_NULL, null=True, blank=True, related_name='elections', help_text="Designated polling unit/voting station for this election")
    
    election_type = models.CharField(max_length=20, choices=ELECTION_TYPES, default='custom')
    year = models.IntegerField(default=2026)
    context_name = models.CharField(max_length=100, blank=True, help_text="e.g., Ikwerre, IAUE, Computer Science Dept")
    custom_identifier_name = models.CharField(max_length=100, blank=True, help_text="Required if Custom/Other is selected")
    
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if self.election_type != 'custom' and self.context_name:
            type_display = self.get_election_type_display()
            self.title = f"{self.context_name} {type_display} {self.year}"
        elif self.election_type == 'custom' and not self.title:
            self.title = f"{self.context_name} Election {self.year}" if self.context_name else "Custom Election"
        super().save(*args, **kwargs)

    @property
    def requires_party(self):
        return self.election_type in self.PARTY_REQUIRED_TYPES

    def get_suggested_positions(self):
        return self.SUGGESTED_POSITIONS.get(self.election_type, [])

    def __str__(self):
        return self.title

class Party(models.Model):
    election = models.ForeignKey(Election, on_delete=models.CASCADE, related_name='parties')
    name = models.CharField(max_length=100)
    abbreviation = models.CharField(max_length=10, blank=True)
    logo = models.ImageField(upload_to='party_logos/', blank=True, null=True)

    def __str__(self):
        return f"{self.name} ({self.abbreviation})"

class Position(models.Model):
    election = models.ForeignKey(Election, on_delete=models.CASCADE, related_name='positions')
    name = models.CharField(max_length=100)
    max_winners = models.IntegerField(default=1)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.election.title})"

class Candidate(models.Model):
    election = models.ForeignKey(Election, on_delete=models.CASCADE, related_name='candidates')
    position = models.ForeignKey(Position, on_delete=models.CASCADE, related_name='candidates')
    party = models.ForeignKey(Party, on_delete=models.SET_NULL, null=True, blank=True, related_name='candidates')
    name = models.CharField(max_length=100)
    photo = models.ImageField(upload_to='candidate_photos/', blank=True, null=True)
    manifesto = models.TextField(blank=True)
    is_approved = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        party_str = f" - {self.party.abbreviation}" if self.party else ""
        return f"{self.name}{party_str} ({self.position.name})"

class ElectionVoter(models.Model):
    election = models.ForeignKey(Election, on_delete=models.CASCADE, related_name='registered_voters')
    voter = models.ForeignKey(Voter, on_delete=models.CASCADE, related_name='election_registrations')
    polling_unit = models.ForeignKey(PollingUnit, on_delete=models.SET_NULL, null=True, blank=True, related_name='registered_voters', help_text="Polling unit where this voter is registered to vote")
    
    nin = models.CharField(max_length=11, blank=True, verbose_name="NIN")
    voter_card_id = models.CharField(max_length=50, blank=True, verbose_name="Voter's Card ID / VIN")
    matric_number = models.CharField(max_length=50, blank=True, verbose_name="Matriculation Number")
    custom_identifier_value = models.CharField(max_length=100, blank=True)

    is_verified = models.BooleanField(default=False)
    biometric_registered = models.BooleanField(default=False, help_text="Prototype fingerprint enrollment completed")
    has_voted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('election', 'voter')

    def clean(self):
        if self.nin:
            if not re.match(r'^\d{11}$', self.nin):
                raise ValidationError({'nin': 'NIN must be exactly 11 digits.'})
        
        if self.matric_number:
            if not re.match(r'^[A-Z0-9/]+$', self.matric_number.upper()):
                raise ValidationError({'matric_number': 'Matric number must contain only letters, numbers, and slashes.'})

    def __str__(self):
        return f"{self.voter.voter_id} in {self.election.title}"

class StaffProfile(models.Model):
    """
    RBAC for election staff. 
    """
    ROLE_CHOICES = [
        ('election_admin', 'Election Administrator'),
        ('verification_officer', 'Verification Officer'),
        ('voter_registration_officer', 'Voter Registration Officer'),
        ('candidate_registration_officer', 'Candidate Registration Officer'),
        ('accreditation_officer', 'Accreditation Officer'),
        ('observer', 'Observer/Auditor'),
    ]
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='staff_profile')
    role = models.CharField(max_length=30, choices=ROLE_CHOICES)
    polling_unit = models.ForeignKey(PollingUnit, on_delete=models.SET_NULL, null=True, blank=True, related_name='staff_members', help_text="Assign this staff member to a specific polling unit")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        pu_name = f" @ {self.polling_unit.name}" if self.polling_unit else ""
        return f"{self.user.username} - {self.get_role_display()}{pu_name}"

    def can_manage_elections(self):
        return self.role in ['election_admin'] or self.user.is_superuser

    def can_verify_voters(self):
        return self.role in ['verification_officer', 'election_admin'] or self.user.is_superuser

    def can_register_voters(self):
        return self.role in ['voter_registration_officer', 'election_admin'] or self.user.is_superuser

    def can_register_candidates(self):
        return self.role in ['candidate_registration_officer', 'election_admin'] or self.user.is_superuser

    def can_accredit_voters(self):
        return self.role in ['accreditation_officer', 'election_admin'] or self.user.is_superuser

    def can_view_audit(self):
        return self.role in ['observer', 'election_admin'] or self.user.is_superuser

class AuditLog(models.Model):
    ACTION_CHOICES = [
        ('create_election', 'Election Created'),
        ('delete_election', 'Election Deleted'),
        ('add_candidate', 'Candidate Added'),
        ('approve_candidate', 'Candidate Approved'),
        ('reject_candidate', 'Candidate Rejected'),
        ('verify_voter', 'Voter Verified'),
        ('generate_credential', 'Credential Generated'),
        ('cast_vote', 'Vote Cast'),
        ('duplicate_vote_attempt', 'Duplicate Vote Attempt'),
        ('create_staff', 'Staff Account Created'),
        ('accredit_voter', 'Voter Accredited'),
        ('blockchain_record_created', 'Blockchain Record Created'),
        ('voter_registered', 'Voter Registered'),
        ('failed_ballot_submission', 'Failed Ballot Submission'),
        ('fingerprint_verified', 'Fingerprint Verified'),
    ]
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    action = models.CharField(max_length=50, choices=ACTION_CHOICES)
    details = models.TextField(blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.action} by {self.user} at {self.timestamp}"
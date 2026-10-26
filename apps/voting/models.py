import hashlib
from django.db import models
from django.utils import timezone
from apps.voters.models import Voter
from apps.elections.models import Election, Candidate, Position

class Vote(models.Model):
    voter = models.ForeignKey(Voter, on_delete=models.PROTECT)
    election = models.ForeignKey(Election, on_delete=models.PROTECT)
    position = models.ForeignKey(Position, on_delete=models.PROTECT)
    candidate = models.ForeignKey(Candidate, on_delete=models.PROTECT)
    timestamp = models.DateTimeField(auto_now_add=True)
    blockchain_hash = models.CharField(max_length=64, blank=True, null=True)

    class Meta:
        unique_together = ('voter', 'election', 'position')

    def __str__(self):
        return f"Vote: {self.voter.user.username} -> {self.candidate.name} for {self.position.name}"

class TemporaryCredential(models.Model):
    voter = models.ForeignKey(Voter, on_delete=models.CASCADE)
    election = models.ForeignKey(Election, on_delete=models.CASCADE)
    credential_hash = models.CharField(max_length=64)
    expires_at = models.DateTimeField()
    is_used = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Temp Credential for {self.voter.voter_id} in {self.election.title}"

    @classmethod
    def generate(cls, voter, election, plain_credential, duration_minutes=20):
        credential_hash = hashlib.sha256(plain_credential.encode('utf-8')).hexdigest()
        expires_at = timezone.now() + timezone.timedelta(minutes=duration_minutes)
        return cls.objects.create(voter=voter, election=election, credential_hash=credential_hash, expires_at=expires_at)

    def is_valid(self, plain_credential):
        if self.is_used or timezone.now() > self.expires_at:
            return False
        input_hash = hashlib.sha256(plain_credential.encode('utf-8')).hexdigest()
        return input_hash == self.credential_hash

    def mark_as_used(self):
        self.is_used = True
        self.save()
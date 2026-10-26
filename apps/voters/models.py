import uuid
from django.db import models
from django.contrib.auth.models import User


def generate_voter_id():
    return str(uuid.uuid4())


class Voter(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='voter_profile')
    voter_id = models.CharField(max_length=36, unique=True, default=generate_voter_id)
    is_verified = models.BooleanField(default=False)
    has_voted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} ({self.voter_id})"
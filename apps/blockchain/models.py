from django.db import models

class BlockchainBlock(models.Model):
    index = models.PositiveIntegerField(unique=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    vote_reference = models.CharField(max_length=100) # Stores "Vote ID: X" for simplicity
    data = models.TextField(null=True, blank=True)    # Stores the JSON payload of the vote
    previous_hash = models.CharField(max_length=64)
    current_hash = models.CharField(max_length=64)

    def __str__(self):
        return f"Block #{self.index}"
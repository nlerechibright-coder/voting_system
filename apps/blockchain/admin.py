from django.contrib import admin
from .models import BlockchainBlock

@admin.register(BlockchainBlock)
class BlockchainBlockAdmin(admin.ModelAdmin):
    list_display = ('index', 'vote_reference', 'timestamp', 'current_hash')
    ordering = ('-index',)
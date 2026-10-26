from django.shortcuts import render
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views import View
from .models import BlockchainBlock
from .services import verify_chain_integrity

class BlockchainExplorerView(LoginRequiredMixin, View):
    def get(self, request):
        blocks = BlockchainBlock.objects.order_by('-index')
        is_valid, message = verify_chain_integrity()
        
        context = {
            'blocks': blocks,
            'is_valid': is_valid,
            'integrity_message': message,
            'page_title': 'Blockchain Explorer'
        }
        return render(request, 'blockchain/explorer.html', context)
import hashlib
import json
from django.utils import timezone
from .models import BlockchainBlock

def create_block(vote_reference, data_dict):
    last_block = BlockchainBlock.objects.order_by('-index').first()

    if last_block:
        index = last_block.index + 1
        previous_hash = last_block.current_hash
    else:
        index = 1
        previous_hash = '0' * 64 

    data_string = json.dumps(data_dict, sort_keys=True)

    # Save first so the hash uses the exact auto_now_add timestamp persisted in
    # the database. Hashing a separately generated timestamp breaks verification.
    block = BlockchainBlock.objects.create(
        index=index,
        vote_reference=vote_reference,
        data=data_string,
        previous_hash=previous_hash,
        current_hash='',
    )
    block_string = f"{block.index}{block.previous_hash}{block.timestamp}{data_string}".encode('utf-8')
    block.current_hash = hashlib.sha256(block_string).hexdigest()
    block.save(update_fields=['current_hash'])
    return block

def verify_chain_integrity():
    blocks = BlockchainBlock.objects.order_by('index')
    if not blocks:
        return True, "No blocks in chain."
    
    for i, block in enumerate(blocks):
        if i == 0:
            if block.previous_hash != '0' * 64:
                return False, f"Genesis block previous hash invalid."
        else:
            if block.previous_hash != blocks[i-1].current_hash:
                return False, f"Block {block.index} previous hash mismatch."
        
        timestamp = str(block.timestamp)
        data_string = block.data
        block_string = f"{block.index}{block.previous_hash}{timestamp}{data_string}".encode('utf-8')
        calculated_hash = hashlib.sha256(block_string).hexdigest()
        
        if calculated_hash != block.current_hash:
            return False, f"Block {block.index} hash mismatch."
            
    return True, "Blockchain integrity verified. All blocks are valid and linked."

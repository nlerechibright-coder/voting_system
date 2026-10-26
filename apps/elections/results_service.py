"""
Results Service Module

Handles vote counting, result generation, and election statistics.
Encapsulates the logic for calculating winners and vote distributions.
"""

from django.db import models

from apps.voting.models import Vote
from apps.elections.models import Candidate, Position, ElectionVoter


def calculate_election_results(election):
    """
    Calculate complete election results for all positions.
    
    Returns a dictionary with:
    - total_votes: int (total votes cast in the election)
    - total_registered: int
    - total_accredited: int
    - total_voted: int
    - position_results: list of dicts with:
        - position: Position object
        - results: list of dicts with candidate, votes, percentage
        - winner: Candidate object (or None)
        - winners: list of Candidate objects (handles ties)
        - is_tie: bool
        - total_votes: int (votes for this position)
    """
    positions = election.positions.all().order_by('name')
    total_votes = Vote.objects.filter(election=election).count()
    
    # Election-level statistics
    total_registered = ElectionVoter.objects.filter(election=election).count()
    total_accredited = ElectionVoter.objects.filter(election=election, is_verified=True).count()
    total_voted = ElectionVoter.objects.filter(election=election, has_voted=True).count()
    
    position_results = []
    
    for pos in positions:
        candidates = Candidate.objects.filter(
            election=election,
            is_approved=True,
        ).filter(
            models.Q(position=pos) | models.Q(position__name__iexact=pos.name)
        ).select_related('party').order_by('name')
        
        pos_votes = []
        total_pos_votes = 0
        
        for cand in candidates:
            votes_count = Vote.objects.filter(election=election, candidate=cand).count()
            total_pos_votes += votes_count
            pos_votes.append({
                'candidate': cand,
                'votes': votes_count,
            })
        
        # Calculate percentages based on THIS position's total votes (not election total)
        for item in pos_votes:
            if total_pos_votes > 0:
                item['percentage'] = round((item['votes'] / total_pos_votes) * 100, 1)
            else:
                item['percentage'] = 0.0
        
        # Sort by votes descending
        pos_votes.sort(key=lambda x: x['votes'], reverse=True)
        
        # Determine winner(s) — handles ties
        winner = None
        winners = []
        is_tie = False
        
        if pos_votes and pos_votes[0]['votes'] > 0:
            max_votes = pos_votes[0]['votes']
            winners = [item['candidate'] for item in pos_votes if item['votes'] == max_votes]
            winner = winners[0] if len(winners) == 1 else None
            is_tie = len(winners) > 1
        
        position_results.append({
            'position': pos,
            'results': pos_votes,
            'total_votes': total_pos_votes,
            'winner': winner,
            'winners': winners,
            'is_tie': is_tie,
        })
    
    return {
        'total_votes': total_votes,
        'total_registered': total_registered,
        'total_accredited': total_accredited,
        'total_voted': total_voted,
        'position_results': position_results,
    }


def get_position_winner(election, position):
    """
    Get the winner for a specific position.
    
    Returns: Candidate object or None (None if tie)
    """
    candidates = Candidate.objects.filter(
        election=election,
        position=position,
        is_approved=True
    )
    
    results = []
    for cand in candidates:
        votes_count = Vote.objects.filter(
            election=election,
            position=position,
            candidate=cand
        ).count()
        results.append({'candidate': cand, 'votes': votes_count})
    
    if not results:
        return None
    
    results.sort(key=lambda x: x['votes'], reverse=True)
    
    if results[0]['votes'] == 0:
        return None
    
    # Check for tie
    max_votes = results[0]['votes']
    top_candidates = [r['candidate'] for r in results if r['votes'] == max_votes]
    
    return top_candidates[0] if len(top_candidates) == 1 else None


def get_votes_for_candidate(election, position, candidate):
    """
    Get vote count for a specific candidate in a specific position.
    
    Returns: int (number of votes)
    """
    return Vote.objects.filter(
        election=election,
        position=position,
        candidate=candidate
    ).count()


def get_total_votes_for_election(election):
    """
    Get total votes cast in an election.
    
    Returns: int
    """
    return Vote.objects.filter(election=election).count()


def get_votes_per_position(election):
    """
    Get vote distribution across positions.
    
    Returns: dict with position_id: vote_count
    """
    positions = election.positions.all()
    results = {}
    
    for pos in positions:
        votes_count = Vote.objects.filter(
            election=election,
            position=pos
        ).count()
        results[pos.id] = votes_count
    
    return results
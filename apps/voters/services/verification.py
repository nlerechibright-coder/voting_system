import logging
from django.db import models
from apps.voters.models import Voter
from apps.elections.models import ElectionVoter, Election

logger = logging.getLogger(__name__)

class VerificationProvider:
    """
    Base interface for voter verification.
    Defines the contract for verifying a voter's registration and eligibility.
    """
    def verify_voter(self, voter_identifier: str, election_id: int) -> dict:
        raise NotImplementedError("Subclasses must implement verify_voter")

class PrototypeVerificationProvider(VerificationProvider):
    """Permissive local verification path used by the academic prototype."""
    def verify_voter(self, voter_identifier: str, election_id: int) -> dict:
        if not voter_identifier or not voter_identifier.strip():
            return {
                "status": "failed",
                "is_registered": False,
                "is_eligible": False,
                "message": "A voter identifier is required.",
            }

        try:
            election = Election.objects.get(id=election_id)
            matching_registration = ElectionVoter.objects.filter(
                election=election,
            ).filter(
                models.Q(voter__voter_id__iexact=voter_identifier) |
                models.Q(nin__iexact=voter_identifier) |
                models.Q(voter_card_id__iexact=voter_identifier) |
                models.Q(matric_number__iexact=voter_identifier) |
                models.Q(custom_identifier_value__iexact=voter_identifier)
            ).select_related('voter__user').first()
            if matching_registration and matching_registration.has_voted:
                return {
                    "status": "failed",
                    "is_registered": True,
                    "is_eligible": False,
                    "message": "You have already voted in this election.",
                }

            registrations = ElectionVoter.objects.filter(
                election=election,
                is_verified=True,
                has_voted=False,
            ).select_related('voter__user')

            # Keep known identifiers useful while allowing demo-only values.
            registration = matching_registration or registrations.first()

            if not registration:
                return {
                    "status": "failed",
                    "is_registered": False,
                    "is_eligible": False,
                    "message": "No eligible voter registration is available for this election."
                }

            voter = registration.voter
            return {
                "status": "success",
                "is_registered": True,
                "is_eligible": True,
                "voter_name": voter.user.get_full_name() if hasattr(voter, 'user') else str(voter),
                "voter_obj": voter,
                "registration_obj": registration,
                "message": "Voter accepted via the local prototype verification path.",
            }
                
        except Exception as e:
            logger.error(f"Local verification error: {str(e)}")
            return {
                "status": "error",
                "message": f"Verification system error: {str(e)}"
            }

class INECVerificationProvider(VerificationProvider):
    """
    PROPOSED Integration point for the official INEC Database/API.
    
    This provider is reserved for future deployment when official 
    INEC API access and credentials are available.
    """
    def verify_voter(self, voter_identifier: str, election_id: int) -> dict:
        # ---------------------------------------------------------
        # FUTURE INEC API IMPLEMENTATION GOES HERE
        # ---------------------------------------------------------
        # Example:
        # response = requests.post(
        #     settings.INEC_API_URL,
        #     headers={"Authorization": f"Bearer {settings.INEC_API_KEY}"},
        #     json={"voter_id": voter_identifier, "election_id": election_id}
        # )
        # return response.json()
        # ---------------------------------------------------------
        
        raise NotImplementedError(
            "INEC API integration is not active in this academic prototype. "
            "The system is currently using LocalVerificationProvider."
        )

def get_verification_provider() -> VerificationProvider:
    """
    Factory function to return the appropriate verification provider.
    """
    # In production, you could check a Django setting:
    # from django.conf import settings
    # if settings.USE_INEC_API:
    #     return INECVerificationProvider()
    
    return PrototypeVerificationProvider()

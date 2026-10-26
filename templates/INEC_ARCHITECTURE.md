# INEC Database Verification Architecture

## System Integration Overview

The proposed electronic voting system is designed with a modular verification architecture to support integration with the Independent National Electoral Commission (INEC) voter database. This integration allows the system to verify whether a voter is officially registered and eligible to participate in an election before granting voting access.

### Authentication Flow
The conceptual authentication and accreditation flow operates as follows:

1. **Voter Identification**: The voter presents their identification information (NIN, Voter's Card, or Voter ID).
2. **INEC Verification Layer**: The system routes the identification data through the `VerificationProvider` interface.
3. **Registration & Eligibility Check**: 
   - *Proposed Deployment*: Queries the authorized INEC database/API to confirm official registration status and election eligibility.
   - *Current Prototype*: Queries the internal system database to simulate the expected verification response.
4. **Fingerprint Verification**: Biometric hardware captures the voter's fingerprint to ensure the person presenting the ID is the actual registered voter (Prototype uses simulated verification).
5. **Accreditation**: Staff records the voter as accredited after identity and eligibility confirmation.
6. **Ballot Access**: An authorized staff member unlocks the station, then the voter is verified by card number and completes final prototype fingerprint confirmation before ballot submission.

## Prototype vs. Production Deployment

### Current Academic Prototype
Due to the unavailability of direct access to the official INEC database/API for this academic project, the external connection has not been activated. The system utilizes a `LocalVerificationProvider` that relies on internal voter records and demonstration data. Fingerprint verification is simulated to demonstrate the workflow logic.

### Proposed Production Deployment
When deployed in a real-world environment, the `INECVerificationProvider` will be activated. This provider will securely connect to the official INEC API using authorized credentials, replacing the local database lookup with real-time electoral register validation. The software architecture requires no structural changes to accommodate this transition, as the voting workflow depends strictly on the verification interface rather than the underlying data source.

## Identification Fields Retained
To ensure compatibility with future INEC API requirements, the voter registration interface captures and retains multiple identification vectors:
- National Identification Number (NIN)
- Permanent Voter's Card (PVC) Number / Voter ID
- Fingerprint templates (for biometric matching)

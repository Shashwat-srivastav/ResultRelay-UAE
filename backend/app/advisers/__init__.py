"""The advisory layer: a model may propose, the gate decides.

Nothing in this package can change a case state. An adviser receives a bounded view of a case and
returns a *proposal*; the proposal is recorded, classified and handed to the deterministic gate as
advisory input only. Three rules hold regardless of what the model says:

1. an adviser never returns an action, only a candidate action;
2. a candidate is rejected outright if it cites a chunk that does not exist or that cannot bind
   the case jurisdiction;
3. the gate's decision is computed without reading the proposal, so a proposal cannot flip it.

The residency check in :mod:`app.advisers.residency` is not decoration. Federal Law No. 2 of 2019,
Article 13 prohibits storing, processing, generating or transforming health data outside the State
without a Health Authority resolution, and Article 24 sets a AED 500,000-700,000 penalty for breach.
A hosted model endpoint outside the UAE is therefore a legal question before it is an engineering
one.
"""

from app.advisers.base import AdvisoryProposal, AdvisoryRecord, Adviser
from app.advisers.guard import advise

__all__ = ["AdvisoryProposal", "AdvisoryRecord", "Adviser", "advise"]

"""Synapse events."""

from mindgrid.platform.events import types


class ProposalCreated(types.EventData):
    proposal_id: str
    source: str
    from_commit: str
    to_commit: str
    items: int
    links: types.Links


PROPOSAL_CREATED = types.define(
    "synapse.proposal_created", "A source changed; a proposal waits for review.", ProposalCreated
)

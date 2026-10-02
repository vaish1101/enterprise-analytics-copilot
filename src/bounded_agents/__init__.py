"""Opt-in architecture spike. Not imported by the product API or default graph."""

GOVERNED_MODE = "governed_v1"
SPIKE_MODE = "bounded_agents_v2"


def create_workflow(*args, mode=GOVERNED_MODE, **kwargs):
    """Explicit library opt-in only; product settings/API are not changed."""
    if mode == GOVERNED_MODE:
        from src.orchestration.graph import EnterpriseAnalyticsGraph
        return EnterpriseAnalyticsGraph(*args, **kwargs)
    if mode == SPIKE_MODE:
        from .runtime import BoundedAgentsGraph
        return BoundedAgentsGraph(*args, **kwargs)
    raise ValueError("Unknown versioned workflow mode")

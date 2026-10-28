"""Connector events (a sync that keeps failing ends with job.failed after its retries)."""

from mindgrid.platform.events import types


class ConnectorSynced(types.EventData):
    connector_id: str
    name: str
    changed: list[str]  # datasets with a new version
    links: types.Links


CONNECTOR_SYNCED = types.define("connector.synced", "A connector sync finished.", ConnectorSynced)
OUTCOMES = [CONNECTOR_SYNCED.name, "job.failed"]

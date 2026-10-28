"""Dataset events."""

from mindgrid.platform.events import types


class DatasetUpdated(types.EventData):
    dataset: str
    version: int
    rows: int
    columns: int
    source: str
    links: types.Links


DATASET_UPDATED = types.define(
    "dataset.updated", "A dataset has a new version (new data).", DatasetUpdated
)

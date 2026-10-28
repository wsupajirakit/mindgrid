from ..sanitize import clean
from ..sections import Section
from .text_decode import decode


def parse(data: bytes) -> list[Section]:
    text = clean(decode(data))
    return [Section(text=text)] if text else []

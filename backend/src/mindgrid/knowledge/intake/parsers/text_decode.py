"""Bytes -> text for text formats: UTF-8 (with or without BOM) only; anything else is
refused rather than guessed (a wrong guess silently corrupts every chunk)."""

from mindgrid.core.errors import ApiError


def decode(data: bytes) -> str:
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise ApiError(400, "document.encoding", "text files must be UTF-8") from None

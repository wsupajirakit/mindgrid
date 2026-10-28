"""The displayed product name and look, changeable from this one place.

Every surface that shows the name (web title and header, sign-in page, API docs, CLI
banner, MCP server name, notifications) reads it from here, through `GET /v1/meta/brand`
for the web. Translations use a `{brand}` placeholder instead of the name. The folder,
repository, package and CLI command names are code identity and do not change with it.
tools/check_brand.py fails when the default name appears anywhere else.
"""

from pydantic import BaseModel, Field

from mindgrid.core.config import AppSettings, env_field, settings_getter

_HEX_COLOR = r"^#[0-9a-fA-F]{6}$"


class BrandSettings(AppSettings):
    name: str = env_field("MINDGRID_BRAND_NAME", "MindGrid", doc="Displayed product name.")
    short_name: str = env_field(
        "MINDGRID_BRAND_SHORT_NAME", "", doc="Short name (narrow headers); blank = the name."
    )
    tagline: str = env_field("MINDGRID_BRAND_TAGLINE", "", doc="Optional line under the name.")
    logo_url: str = env_field(
        "MINDGRID_BRAND_LOGO_URL", "", doc="Logo image URL or path served by the web app."
    )
    primary_color: str = env_field(
        "MINDGRID_BRAND_PRIMARY_COLOR",
        "#4f46e5",
        doc="Primary UI colour (#rrggbb).",
        pattern=_HEX_COLOR,
    )
    primary_color_dark: str = env_field(
        "MINDGRID_BRAND_PRIMARY_COLOR_DARK",
        "#60a5fa",
        doc="Primary UI colour in the dark theme (#rrggbb; light enough to read on black).",
        pattern=_HEX_COLOR,
    )


get_settings = settings_getter(BrandSettings)


class Brand(BaseModel):
    """Public shape of the brand (no secrets; served to signed-out pages too)."""

    name: str = Field(min_length=1)
    short_name: str = Field(min_length=1)
    tagline: str
    logo_url: str
    primary_color: str
    primary_color_dark: str


def current() -> Brand:
    cfg = get_settings()
    return Brand(
        name=cfg.name,
        short_name=cfg.short_name or cfg.name,
        tagline=cfg.tagline,
        logo_url=cfg.logo_url,
        primary_color=cfg.primary_color,
        primary_color_dark=cfg.primary_color_dark,
    )

"""Platform-level settings (other modules declare theirs next to their own code)."""

from typing import Literal

from mindgrid.core.settings_registry import Scope, define

UI_LOCALE = define(
    "ui.locale",
    Literal["en", "th", "it"],
    "en",
    {Scope.SYSTEM, Scope.USER},
    "Interface language (a user's choice overrides the system default).",
)
UI_THEME = define(
    "ui.theme",
    Literal["system", "light", "dark"],
    "dark",
    {Scope.SYSTEM, Scope.USER},
    "Colour theme (a user's choice, saved with their account, overrides the system default).",
)
UI_LAYOUT = define(
    "ui.layout",
    Literal["sidebar", "mega"],
    "sidebar",
    {Scope.SYSTEM, Scope.USER},
    "Navigation layout: a side menu or a top bar with a mega menu (a user's choice wins).",
)

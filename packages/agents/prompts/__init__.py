"""Versionerade prompts + en enkel render-helper.

Prompts lagras som .j2-filer (Jinja2) bredvid denna modul, en per nyckel:
    discovery_system.j2, discovery_user.j2, pm_system.j2, pm_user.j2, ...

`render("discovery_user", brief=...)` laddar discovery_user.j2 och renderar den med
de inskickade variablerna. Att hålla prompterna i egna filer gör dem versionerbara
och diffbara utan att röra Python-koden.

Själva prompt-innehållet (roll, instruktioner, few-shot-exempel) detaljeras separat.
Denna modul är bara laddnings-/renderingsmekaniken.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape

_DIR = Path(__file__).parent

_env = Environment(
    loader=FileSystemLoader(str(_DIR)),
    autoescape=select_autoescape(enabled_extensions=()),
    undefined=StrictUndefined,  # fela hårt om en promptvariabel saknas
    trim_blocks=True,
    lstrip_blocks=True,
)


@lru_cache(maxsize=None)
def _template(key: str):
    return _env.get_template(f"{key}.j2")


def render(key: str, **vars) -> str:
    """Rendera prompten `key` med `vars`. Pydantic-objekt skickas in som de är
    och nås i mallen via attribut (t.ex. {{ brief.name }})."""
    return _template(key).render(**vars).strip()

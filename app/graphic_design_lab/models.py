"""Core data structures for the experimental Graphic Design Lab contracts.

These models are deliberately small. They represent contract-facing data only;
they do not select a graphics provider or initialize production design runtime.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class PageGeometry:
    width_mm: float
    height_mm: float
    orientation: str


@dataclass(frozen=True)
class DesignObject:
    object_id: str
    object_type: str
    layer: str | None = None
    role: str | None = None
    content: Any = None
    geometry: dict[str, Any] = field(default_factory=dict)
    style_ref: str | None = None
    constraints: dict[str, Any] = field(default_factory=dict)
    asset_ref: str | None = None


@dataclass(frozen=True)
class DesignSpread:
    spread_id: str
    kind: str
    objects: tuple[DesignObject, ...]
    period: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class DesignSpec:
    schema_version: str
    document_id: str
    revision_id: str
    product_type: str
    page: PageGeometry
    spreads: tuple[DesignSpread, ...]
    raw: dict[str, Any]

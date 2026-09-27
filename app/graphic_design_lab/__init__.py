"""Experimental Graphic Design Lab contract foundation.

Renderer/compiler/provider runtime is intentionally not initialized here.
"""

from .models import DesignObject, DesignSpec, DesignSpread, PageGeometry
from .validation import validate_design_spec, validate_product_profile

__all__ = [
    "DesignObject",
    "DesignSpec",
    "DesignSpread",
    "PageGeometry",
    "validate_design_spec",
    "validate_product_profile",
]

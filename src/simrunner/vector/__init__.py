from .context import removed, modified

__all__ = [
    "removed",
    "modified",
]

from osgeo import ogr
ogr.UseExceptions()
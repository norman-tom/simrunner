from .context import modified, removed

__all__ = [
    "removed",
    "modified",
]

from osgeo import ogr

ogr.UseExceptions()

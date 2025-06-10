from contextlib import contextmanager
from osgeo import ogr, gdal

def _modify_attribute(ds, attr, value, identifier, key, fid=None):
    """Modify an attribute of a feature in a shapefile. Conditioned on the ID field."""
    layer = ds.GetLayer(0)
    if fid:
        # If a feature ID is provided, find the feature by FID
        feature = layer.GetFeature(fid)
        if feature is None:
            raise ValueError(f"Feature with FID {fid} not found.")
    else:
        # If no FID is provided, find the feature by key:value
        feature = None
        for f in layer:
            if f.GetField(key) == identifier:
                fid = f.GetFID()
                feature = f
                break
        if feature is None:
            raise ValueError(f"Feature with {key}={identifier} not found.")

    
    feature.SetField(attr, value)
    err = layer.SetFeature(feature)
    if err != ogr.OGRERR_NONE:
        raise RuntimeError(f"Failed to set feature attribute. Error code: {err}")
    
    return fid

@contextmanager
def modified(path, attr, value, identifier, key='ID'):
    """Context manager to temporarily modify an attribute of a feature by key:value and restore it after."""
    
   
    orginal_attr = None
    with ogr.Open(path, gdal.GA_Update) as ds:
        # Get the original attribute value
        layer = ds.GetLayer(0)

        try:
            feature = layer.GetFeature(0)
            feature.GetField(key)  # Check if key exists
        except KeyError:
            raise ValueError(f"Key '{key}' not found in the layer. Please check the field name.")
        
        try:
            feature.GetField(attr)  # Check if attr exists
        except KeyError:
            raise ValueError(f"Attribute '{attr}' not found in the layer. Please check the field name.")

        for feature in layer:
            if feature.GetField(key) == identifier:
                fid = feature.GetFID()
                orginal_attr = feature.GetField(attr)
                break
        
        # Modify the attribute
        fid = _modify_attribute(ds, attr, value, identifier, key, fid=fid)
    
    try:
        yield 
    finally:
        # Restore the original attribute value
        if orginal_attr is not None:
            with ogr.Open(path, gdal.GA_Update) as ds:
                _modify_attribute(ds, attr, orginal_attr, identifier, key, fid=fid)


def _remove_features(ds, id_value, key):
    """Temporarily remove multiple features from the layer by a key. Returns the features geometry and attributes for restoration."""
    layer = ds.GetLayer(0)
    deleted_features = []
    
    try:
        feature = layer.GetFeature(0)
        feature.GetField(key) 
    except KeyError:
        raise ValueError(f"Key '{key}' not found in the layer. Please check the field name.")

    # Collect features to delete first (to avoid iteration issues)   
    features_to_delete = []
    layer.ResetReading()
    for feature in layer:
        if feature.GetField(key) == id_value:
            geom = feature.GetGeometryRef().Clone()
            # Get all field names from layer definition
            layer_defn = layer.GetLayerDefn()
            attrs = {}
            for i in range(layer_defn.GetFieldCount()):
                field_name = layer_defn.GetFieldDefn(i).GetName()
                attrs[field_name] = feature.GetField(field_name)
            
            features_to_delete.append((feature.GetFID(), geom, attrs))
    
    # Now delete the features
    for fid, geom, attrs in features_to_delete:
        layer.DeleteFeature(fid)
        deleted_features.append((geom, attrs))
    
    return deleted_features


def _restore_features(ds, deleted_features):
    """Restore multiple previously removed features to the layer using saved geometry and attributes."""
    layer = ds.GetLayer(0)
    
    for geom, attrs in deleted_features:
        new_feature = ogr.Feature(layer.GetLayerDefn())
        new_feature.SetGeometry(geom)
        for key, value in attrs.items():
            new_feature.SetField(key, value)
        
        err = layer.CreateFeature(new_feature)
        if err != ogr.OGRERR_NONE:
            print(f"Failed to restore feature. Error code: {err}")
        new_feature = None  # Clean up


@contextmanager
def removed(path, identifier, key='ID'):
    """Context manager to temporarily remove features by a key:value and restore them after the block."""
    deleted_features = []
    
    # Remove features
    with ogr.Open(path, gdal.GA_Update) as ds:
        deleted_features = _remove_features(ds, identifier, key)
    try:
        yield
    finally:
        # Restore features if any were deleted
        if deleted_features:
            with ogr.Open(path, gdal.GA_Update) as ds:
                _restore_features(ds, deleted_features)


@contextmanager
def only(path: str, identifier, key='ID'):
    """Context manager to only keep features with a specific key:value and remove all others."""
    pass


@contextmanager
def scenario(root: str, scenario: str):
    """Context manager to only use features from a specific scenario.
    
    Scenarios are specified with the 'scenario' attribute in the shapefile.
    Feature can belong to multiple scenarios be sperating with a comma.
    """
    pass
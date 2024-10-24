"""Visualize features from OpenStreetMap and calculates trail mileage for any area.

The main method of this module, create_trail_mileage_map() creates a map of an area of interest
using data from OpenStreetMap. The map is titled with the total trail mileage found in that area.
The create_trail_mileage map() takes in two arguments.
1) The area of interest (which can be described as a bounding box or placename)
2) The desired feature layers to be visualized on the map.

The method creates a local directory called 'trail-mileage-maps' and saves the map in that
directory.
"""

import os
import pathlib
import matplotlib.pyplot as plt
import osmnx
import geopandas as gpd
import pandas as pd
from shapely.geometry import Polygon
from pyproj import Transformer

def create_mask(area) -> gpd.GeoDataFrame:
    """Create polygon boundary for feature layers based on bounding box or placename.
    Args:
        area: A list of four coordinates [north, south, east, west] or placename as a string.
    Returns:
        A polygon boundary representing the area of interest.
    Raises:
        ValueError: If an invalid placename or bounding box is provided.
        TypeError: If the area is described as neither a placename or bounding box.
    """
    if isinstance(area, list):
        if len(area) != 4:
            raise ValueError('List must contain exactly'
                            'four coordinates: [north, south, east, west]')
        north_bound, south_bound, east_bound, west_bound = area
        mask = Polygon([(west_bound, south_bound),
                        (west_bound, north_bound),
                        (east_bound, north_bound),
                        (east_bound, south_bound)]
                        )

        return gpd.GeoDataFrame({'geometry' : [mask]})

    if isinstance(area, str):
        try:
            mask = osmnx.geocode_to_gdf(area)
            return mask
        except ValueError as e:
            raise ValueError(f'Unable to geocode area {area}: {e}')

    else:
        raise TypeError('Area of interest must be described by string or list of'
                         'four coordinates [north, south, east, west]')

def get_features(area, feature_layers_payload: dict) -> dict:
    """Fetch desired feature layers from OpenStreetMap.
    Args:
        area: A list of four coordinates [north, south, east, west] or placename as a string.
        feature_layers_payload: A dictionary used to find tags on OpenStreetMap.
    Returns:
        A dictionary of GeoDataFrames for each feature layer tag.
    Raises:
        ValueError: If a feature layer cannot be retrieved from OpenStreetMap.
        TypeError: If the area is described as neither a placename or bounding box.
    """
    feature_layers = {}
    if isinstance(area, list):
        for tag in feature_layers_payload.keys():
            try:
                feature_layers[tag] = osmnx.features.features_from_bbox(
                    *area,
                    tags=feature_layers_payload.get(tag)
                )
            except ValueError as e:
                print(f'Error fetching features for {tag}: {e} \n'
                      'https://osmnx.readthedocs.io/en/stable/user-reference.html')
                continue

    elif isinstance(area, str):
        for tag in feature_layers_payload.keys():
            try:
                feature_layers[tag] = osmnx.geometries_from_place(
                    area,
                    tags=feature_layers_payload.get(tag)
                )
            except ValueError as e:
                print(f'Error fetching features for {tag}: {e} \n'
                      'https://osmnx.readthedocs.io/en/stable/user-reference.html')

    else:
        raise TypeError('Area of interest must be described by string or list of'
                        'four coordiantes [north, south, east, west]')

    # Filter dictionary to include only GeoDataFrame values
    if not feature_layers:
        raise ValueError('No feature layers were fetched.')
    return {tag: gdf for tag, gdf in feature_layers.items() if isinstance(gdf, gpd.GeoDataFrame)}

def clip_layers( mask: gpd.GeoDataFrame, feature_layers: dict) -> dict:
    """Clip feature layers that extend beyond the mask boundary.
    Args:
        mask: A polygon boundary representing the area of interest.
        feature_layers: A dictionary of GeoDataFrames that contain the geometries of each layer.
    Returns:
        An updated feature layers dictionary where each geometry is clipped to the mask boundary.
    """
    clipped_layers = {key: gpd.clip(gdf,mask) for key, gdf in feature_layers.items()}
    clipped_layers['mask'] = mask
    return clipped_layers

def get_map_projection(mask: gpd.GeoDataFrame) -> str:
    """Find the most appropriate projected coordinate system for the area of interest.
    Args:
        mask: A polygon boundary representing the area of interest.
    Returns:
        The best fitting projected coordinate system as a string.
    """
    mask_polygon = mask['geometry'].iloc[0]
    mask_centroid = mask_polygon.centroid

    # Load available projections and select the ones that contain the mask centroid
    projections_data_fp = pathlib.Path().resolve() / 'projections_data'
    map_projections = gpd.read_file(f'{projections_data_fp}/projections.geojson')
    valid_map_projections = map_projections.loc[map_projections['geometry'].contains(mask_centroid)]

    # Reproject to World Mercator to avoid calculating area with a geographic CRS
    valid_map_projections = valid_map_projections.to_crs('EPSG:3395')

    # Choose the projection with the smallest area to minimize distortion
    chosen_projection = valid_map_projections.loc[valid_map_projections.geometry.area.idxmin()]
    chosen_projection_code = chosen_projection.code
    return chosen_projection_code

def filter_trails(trails: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Merge paths and footways after filtering out non trail surfaces.
    Valid trail surfaces include 'gravel', 'dirt', 'grass','compacted', 'earth', 'ground', 'rock'.
    Args:
        trails: A GeoDataFrame representing the trails feature layer within the area of interest.
    Returns:
        An updated GeoDataFrame that contains all paths and footways with valid trail surfaces.
    """
    path_segments = trails.loc[trails['highway'] == 'path']
    path_segments = path_segments.loc[path_segments['surface'] != 'concrete']
    footway_segments = trails.loc[trails['highway'] == 'footway']
    trail_surfaces = ['gravel', 'dirt', 'grass', 'compacted', 'earth', 'ground', 'rock']
    footway_segments = footway_segments.loc[footway_segments['surface'].isin(trail_surfaces)]
    trails = pd.concat([footway_segments, path_segments])
    return trails

def calculate_trail_miles(mask: gpd.GeoDataFrame, trails: gpd.GeoDataFrame) -> dict:
    """Calculate total trail mileage within area of interest according to chosen CRS.
    Args:
        mask: A polygon boundary representing the area of interest.
        trails: A GeoDataFrame representing the trails feature layer within the area of interest.
    Returns:
        A dictionary containing the keys 'projection' and 'trail_miles', which point to the
        chosen PCS and the calculated trail mileage respectively.
    """
    chosen_projection = get_map_projection(mask)
    trails_projected = trails.to_crs(chosen_projection)
    trail_miles = round(sum(trails_projected['geometry'].length)/1609.344,3)
    try:
        # Only calculate mask area/trail density for single polygons.
        mask_4326_coords = list(mask['geometry'][0].exterior.coords)
        
        # Create list of (longitude, latitude) tuples using the chosen CRS.
        transformer = Transformer.from_crs('EPSG:4326', chosen_projection, always_xy=True)
        mask_projected_coords = [transformer.transform(lon, lat) for lon, lat in mask_4326_coords]
        
        # Calculate average trail mileage per square mile within area of interest.
        mask_projected_area = Polygon(mask_projected_coords).area/2589990
        trail_density_per_mile = round(trail_miles/mask_projected_area, 3)
        return {'projection' : chosen_projection,
                'trail_miles' : trail_miles,
                'trail_density_per_mile' : trail_density_per_mile}
    
    # If area of interest is a multipolygon, don't calculate trail density.
    except AttributeError:
        return {'projection' : chosen_projection, 'trail_miles' : trail_miles}

def show(clipped_layers, plot_title):
    """Visualize the clipped feature layers within the area of interest.
    Args:
        clipped_layers: Dictionary of GeoDataFrames which contain the feature layers fetched from
        OpenStreetMap and clipped to the mask boundary.
        plot_title: String displaying chosen projection system and total trail mileage caluclated.
    Returns:
        None
    """
    _, ax = plt.subplots(figsize=(12,8))
    ax.set_title(plot_title)

    def plot_layer(name, color, **kwargs):
        if name in clipped_layers:
            clipped_layers.get(name).plot(ax=ax, color=color, **kwargs)
        else:
            print(f'No {name} to map')

    plot_layer('mask', '#ECF2D4', zorder=float('-inf'))
    plot_layer('trails', '#BA6461', linestyle='dashed', linewidth=0.6, zorder=float('inf'))
    plot_layer('water', '#9FD9E9')
    plot_layer('streets', '#FFFFFF', linewidth=0.6)
    plot_layer('roads', '#F9E9A0', linewidth=1.5)
    plot_layer('highways','#F3CD71', linewidth=2)
    plot_layer('parks', '#CEDFC2')
    plot_layer('buildings', '#D4D1CB')

def create_trail_mileage_map(area, feature_layers_payload):
    """Main function to create and save a trail mileage map as a .pdf.
    Args:
        area: A list of four coordinates [north, south, east, west] or placename as a string.
        feature_layers_payload: A dictionary used to find tags on OpenStreetMap.
    Returns:
        0
    """
    mask = create_mask(area)
    feature_layers = get_features(area, feature_layers_payload)
    clipped_layers = clip_layers(mask, feature_layers)
    try:
        clipped_layers['trails'] = filter_trails(clipped_layers['trails'])
        trails_projected = calculate_trail_miles(mask, clipped_layers['trails'])
        if 'trail_density_per_mile' in trails_projected:
            plot_title =  (f"{trails_projected['trail_miles']} Miles of Trail"
                           f" ({trails_projected['trail_density_per_mile']} Miles/ Square Mile)"
                           f" Within Area of Interest Based on"
                           f" {str(trails_projected['projection']).upper()} Projection.")
        else:
            plot_title =  (f"{trails_projected['trail_miles']}"
            f" Miles of Trail Within Area of Interest"
            f" Based on {str(trails_projected['projection']).upper()} Projection")

    except ValueError as e:
        plot_title = f'No trail miles found: {e}'
    show(clipped_layers, plot_title)
    os.makedirs('trail-mileage-maps', exist_ok=True)
    plt.savefig(f'trail-mileage-maps/{area}-trails.pdf')
    return 0


if __name__ == '__main__':

    FEATURE_LAYERS_PAYLOAD = {
        'highways': {
            'highway': ['motorway', 'trunk']
        },
        'roads': {
            'highway': ['primary', 'secondary', 'tertiary']
        },
        'streets': {
            'highway': ['residential', 'unclassified']
        },
        'trails': {
            'highway': ['path', 'footway']
        },
        'parks': {
            'leisure': ['park', 'nature_reserve'],
            'boundary': ['protected_area'],
            'landuse': ['grass'],
            'natural': ['wood']
        },
        'water': {
            'water': ['river', 'pond', 'lake', 'reservoir'],
            'waterway': ['river', 'canal'],
            'natural': ['water']
        },
        'buildings': {
            'building': True
        }
    }

    NORTH_BOUND = 37.335
    SOUTH_BOUND = 37.25
    EAST_BOUND = -107.81
    WEST_BOUND = -107.915

    BBOX = [NORTH_BOUND, SOUTH_BOUND, EAST_BOUND, WEST_BOUND]
    PLACENAME = 'Durango, Colorado, USA'

    create_trail_mileage_map(BBOX, FEATURE_LAYERS_PAYLOAD)

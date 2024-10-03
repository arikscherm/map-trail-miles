"""This module visualizes features from OpenStreetMap and calculates trail mileage for some area.

The main method of this module, create_trail_mileage_map() creates a map of desired feature layers
for an area of interest titled with the total trail mileage along with the projected coordinate
system it used to calculate the total trail mileage. 
The create_trail_mileage map() takes in two arguments.
1) The area of interest (which can be described as a bounding box or placename)
2) The desired feature layers to be visualized on the map.
"""

import os
import pathlib
import matplotlib.pyplot as plt
import osmnx
import geopandas as gpd
import pandas as pd
from shapely.geometry import Polygon

def create_mask(area) -> gpd.GeoDataFrame:
    """Create polygon boundary for feature layers based on bounding box or placename.
    Args:
        area: A list of four coordinates [north, south, east, west] or placename as a string.
    """
    if isinstance(area, list):
        if len(area) != 4:
            raise ValueError("""List must contain exactly
                              four coordinates: [north, south, east, west]""")
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
            raise ValueError(f"Unable to geocode area {area}: {e}")

    else:
        raise TypeError("""Area of interest must be described by string or list of
                         four coordinates [north, south, east, west]""")

def get_features(area, feature_layers_payload: dict) -> dict:
    """Create a dictionary of GeoDataFrames for each feature layer tag.
    Inputs: 
        area: A list of four coordinates [north, south, east, west] or placename as a string.
        feature_layers_payload: A dictionary used to find tags on OpenStreetMap.
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
                print(f"""Error fetching features for {tag}: {e} \n
                      https://osmnx.readthedocs.io/en/stable/user-reference.html""")
                continue

    elif isinstance(area, str):
        for tag in feature_layers_payload.keys():
            try:
                feature_layers[tag] = osmnx.geometries_from_place(
                    area,
                    tags=feature_layers_payload.get(tag)
                )
            except ValueError as e:
                print(f"""Error fetching features for {tag}: {e} \n
                      https://osmnx.readthedocs.io/en/stable/user-reference.html""")

    else:
        raise TypeError("""Area of interest must be described by string or list of
                         four coordiantes [north, south, east, west]""")

    # Filter dictionary to include only GeoDataFrame values
    if not feature_layers:
        raise ValueError('No feature layers were fetched.')
    return {tag: gdf for tag, gdf in feature_layers.items() if isinstance(gdf, gpd.GeoDataFrame)}

def clip_layers( mask: gpd.GeoDataFrame, feature_layers: dict) -> dict:
    """Clip feature layers that extend beyond the mask boundary for the area of interest.
    Inputs:
        mask: A polygon boundary representing the area of interest.
        feature_layers_payload: A dictionary used to find tags on OpenStreetMap.
    """
    clipped_layers = {key: gpd.clip(gdf,mask) for key, gdf in feature_layers.items()}
    clipped_layers['mask'] = mask
    return clipped_layers

def get_map_projection(mask: gpd.GeoDataFrame) -> str:
    """Find the most appropriate projected coordinate system for the area of interest.
    Inputs: 
        mask: A polygon boundary representing the area of interest.
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

def filter_trails(trails: gpd.GeoSeries) -> gpd.GeoDataFrame:
    """Merge paths and footways after filtering out non trail surfaces.
    Inputs: 
        trails: A GeoDataFrame representing the trails feature layer within the area of interest.
    """
    path_segments = trails.loc[trails['highway'] == 'path']
    path_segments = path_segments.loc[path_segments['surface'] != 'concrete']
    footway_segments = trails.loc[trails['highway'] == 'footway']
    trail_surfaces = ['gravel', 'dirt', 'grass','compacted', 'earth', 'ground', 'rock']
    footway_segments = footway_segments.loc[footway_segments['surface'].isin(trail_surfaces)]
    trails = pd.concat([footway_segments, path_segments])
    return trails

def calculate_trail_miles(mask: gpd.GeoSeries, trails: gpd.GeoSeries) -> dict:
    """Calculate total trail mileage within area of interest after choosing best PCS.
    Inputs:
        mask: A polygon boundary representing the area of interest.
        trails: A GeoDataFrame representing the trails feature layer within the area of interest.
    """
    chosen_projection = get_map_projection(mask)
    trails_projected = trails.to_crs(chosen_projection)
    trail_miles = round(sum(trails_projected['geometry'].length)/1609.344,3)
    return {'projection' : chosen_projection, 'trail_miles' : trail_miles}

def show(clipped_layers, plot_title):
    """Visualize the clipped feature layers within the area of interest.
    Inputs:
        clipped_layers: Dict of GeoDataFrames which contain the feature layers fetched from OSM.
        plot_title: String displaying chosen projection system and total trail mileage caluclated.
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
    """Main function to create and save a trail mileage map as a .pdf
    Inputs: 
        area: A list of four coordinates [north, south, east, west] or placename as a string.
        feature_layers_payload: A dictionary used to find tags on OpenStreetMap.
    """
    mask = create_mask(area)
    feature_layers = get_features(area, feature_layers_payload)
    clipped_layers = clip_layers(mask, feature_layers)
    try:
        clipped_layers['trails'] = filter_trails(clipped_layers['trails'])
        trails_projected = calculate_trail_miles(mask, clipped_layers['trails'])
        plot_title =  (f"{trails_projected['trail_miles']} Miles of Trail Within Area of Interest"
                    f"Based on {str(trails_projected['projection']).upper()} Projection")

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

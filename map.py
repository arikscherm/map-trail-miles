import osmnx
import geopandas as gpd
import pandas as pd
from shapely.geometry import Polygon
import matplotlib.pyplot as plt
import sys

import shapely

# Create polygon boundary for feature layers based on bounding box or placename
# Input: area can be a list of four coordinates [north, south, east, west] or a placename as a string.
def create_mask(area) -> gpd.GeoDataFrame:
    if isinstance(area, list):
        if len(area) != 4:
            raise ValueError("List must contain exactly four coordinates: [north, south, east, west]")
        north_bound, south_bound, east_bound, west_bound = area
        mask = Polygon([(west_bound, south_bound), (west_bound, north_bound), (east_bound, north_bound), (east_bound, south_bound)])
        return gpd.GeoDataFrame({'geometry' : [mask]})
    
    elif isinstance(area, str):
        try:
            mask = osmnx.geocode_to_gdf(area)
            return mask
        except Exception as e:
            raise Exception(f"Unable to geocode area {area}: {e}")
    
    else:
        raise TypeError("Area of interest must be described by string or list of four coordiantes [north, south, east, west]")


# Create a dictionary of GeoDataFrames for each feature layer tag
def get_features(area, feature_layers_payload: dict) -> dict:
    if not isinstance(feature_layers_payload, dict):
        raise TypeError("Feature layers must be represented by dictionary")
    feature_layers = {}
    if isinstance(area, list):
        for tag in feature_layers_payload.keys():
            try:
                feature_layers[tag] = osmnx.features.features_from_bbox(
                    *area,
                    tags=feature_layers_payload.get(tag)
                )  
            except Exception as e:
                print(f'Error fetching features for {tag}: {e} \n https://osmnx.readthedocs.io/en/stable/user-reference.html')
                continue
    
    elif isinstance(area, str):
        for tag in feature_layers_payload.keys():
            try:
                feature_layers[tag] = osmnx.geometries_from_place(
                    area,
                    tags=feature_layers_payload.get(tag)
                )    
            except Exception as e:
                print(f'Error fetching features for {tag}: {e} \n https://osmnx.readthedocs.io/en/stable/user-reference.html')

    else:
        raise TypeError("Area of interest must be described by string or list of four coordiantes [north, south, east, west]")
            
    # Filter dictionary to include only GeoDataFrame values
    return {tag: gdf for tag, gdf in feature_layers.items() if isinstance(gdf, gpd.GeoDataFrame)}


def clip_layers(feature_layers: dict, mask: gpd.GeoDataFrame) -> dict:
    clipped_layers = {key: gpd.clip(gdf,mask) for key, gdf in feature_layers.items()}
    return clipped_layers


# Find the most appropriate projected coordinate system for the area of interest
def get_map_projection(mask: gpd.GeoDataFrame) -> str:
    mask_polygon = mask['geometry'].iloc[0]
    mask_centroid = mask_polygon.centroid

    # Load available projections and select the ones that contain the mask centroid
    map_projections = gpd.read_file('projections.geojson')
    valid_map_projections = map_projections.loc[map_projections['geometry'].contains(mask_centroid)]

    # Reproject to World Mercator to avoid calculating area with a geographic CRS
    valid_map_projections = valid_map_projections.to_crs('EPSG:3395')
    # Choose the projection with the smallest area to minimize distortion
    projection_to_use = valid_map_projections[valid_map_projections.geometry.area == valid_map_projections.geometry.area.min()]
    projection_to_use_code = projection_to_use.code
    return projection_to_use_code.iloc[0]


# Join 'highway : path' tags and 'highway : footway' tags after filtering 'highway : footway' tags by surface
def filter_trails(trails: gpd.GeoSeries) -> str:
    trail_segments = trails.loc[trails['highway'] == 'path']
    footways = trails.loc[trails['highway'] == 'footway']
    footway_trail_surfaces = ['gravel', 'dirt', 'grass','compacted']
    footways_trail_segments = footways.loc[footways['surface'].isin(footway_trail_surfaces)]
    trails = pd.concat([footways_trail_segments, trail_segments])
    return trails

    
def calculate_trail_miles(mask: gpd.GeoSeries, trails: gpd.GeoSeries) -> str:
    projection_to_use = get_map_projection(mask)
    trails_projected = trails.to_crs(projection_to_use) 
    trail_miles = round(sum(trails_projected['geometry'].length)/1609.344,3)
    return f'{trail_miles} Miles of Trail Within Area of Interest Based on {str(trails_projected.crs).upper()} Projection'
    

# Visualize the clipped feature layers
def show(clipped_layers, plot_title):
    figure, ax = plt.subplots(figsize=(12,8))
    ax.set_title(plot_title)

    plot_layer = lambda name, color, **kwargs: (
        clipped_layers[name].plot(ax=ax, color=color, **kwargs)
        if name in clipped_layers else print(f'No {name} to map')
    )

    plot_layer('mask', '#ECF2D4', zorder=float('-inf'))
    plot_layer('trails', '#BA6461', linestyle='dashed', linewidth=0.8, zorder=float('inf'))
    plot_layer('water', '#9FD9E9')
    plot_layer('streets', '#FFFFFF')
    plot_layer('roads', '#F9E9A0', linewidth=1.5)
    plot_layer('highways','#F3CD71', linewidth=2)
    plot_layer('parks', '#CEDFC2')
    plot_layer('buildings', '#D4D1CB')


# Main function to create and save a trail mileage map
def create_trail_mileage_map(area, feature_layers_payload):
    try:
        mask = create_mask(area)
    except Exception as e:
        print(e)
        return None

    feature_layers = get_features(area, feature_layers_payload) 
    clipped_layers = clip_layers(feature_layers, mask)
    clipped_layers['trails'] = filter_trails(clipped_layers['trails'])
    try:
        plot_title = calculate_trail_miles(mask, clipped_layers['trails'])
    except Exception as e:
        plot_title = f'No trail miles found: {e}'
    show(clipped_layers, plot_title)
    plt.savefig(f'trail-mileage-maps/{area}-trails.pdf')



if __name__ == '__main__':

    feature_layers_payload = {
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
            'highway': ['path']
        },
        'parks': {
            'leisure': ['park', 'nature_reserve'],
            'boundary': ['protected_area'],
            'landuse': ['grass']
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
        
    # north_bound = 37.335
    # south_bound = 37.25
    # east_bound = -107.81
    # west_bound = -107.915

    north_bound = 50.5
    south_bound = 49.5
    east_bound = -99.5
    west_bound = -100.5


    bbox = [north_bound, south_bound, east_bound, west_bound]
    placename = 'Durango, Colorado, USA'

    area = bbox # | placename

    create_trail_mileage_map(area, feature_layers_payload)



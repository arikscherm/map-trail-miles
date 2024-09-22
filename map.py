import osmnx
import geopandas as gpd
from shapely.geometry import Polygon
import matplotlib.pyplot as plt

# Create polygon boundary for feature layers based on bounding box or placename
# Input: area can be a list of four coordinates [north, south, east, west] or a placename as a string.
def create_mask(area) -> gpd.GeoSeries:
    if isinstance(area, list):
        if len(area) != 4:
            raise ValueError("List must contain exactly four coordinates: [north, south, east, west]")
        north_bound, south_bound, east_bound, west_bound = area
        mask = Polygon([(west_bound, south_bound), (west_bound, north_bound), (east_bound, north_bound), (east_bound, south_bound)])
        return gpd.GeoSeries(mask)
    
    elif isinstance(area, str):
        try:
            mask = osmnx.geocode_to_gdf(area)
            return mask
        except Exception as e:
            print(e)
    
    else:
        raise TypeError("Area of interest must be described by string or list of four coordiantes [north, south, east, west]")


# Create a dictionary of GeoDataFrames for each feature layer tag
def get_features(area: list, feature_layers_payload: dict) -> dict:
    feature_layers = {}
    if isinstance(area, list):
        for tag in feature_layers_payload.keys():
            try:
                feature_layers[tag] = osmnx.features.features_from_bbox(
                    *area,
                    tags=feature_layers_payload[tag]
                )  
            except Exception as e:
                print(f'Error fetching features for {tag}: {e}')
                continue
    
    elif isinstance(area, str):
        for tag in feature_layers_payload.keys():
            try:
                feature_layers[tag] = osmnx.geometries_from_place(
                    area,
                    tags=feature_layers_payload[tag]
                )    
            except Exception as e:
                print(f'Error fetching features for {tag}: {e}')
                continue

    else:
        raise TypeError("Area of interest must be described by string or list of four coordiantes [north, south, east, west]")
            
    # Filter dictionary to include only GeoDataFrame values
    return {k: v for k, v in feature_layers.items() if isinstance(v, gpd.GeoDataFrame)}


def clip_layers(feature_layers: dict, mask: gpd.GeoSeries) -> dict:
    clipped_layers = {key: gpd.clip(gdf,mask) for key, gdf in feature_layers.items()}
    return clipped_layers


# Find the most appropriate projected coordinate system for the area of interest
def get_map_projection(mask: gpd.GeoSeries) -> str:
    mask_center = mask.iloc[0].centroid

    # Load available projections and select the ones that contain the mask centroid
    map_projections = gpd.read_file('projections.geojson')
    valid_map_projections = map_projections.loc[map_projections['geometry'].contains(mask_center)]

    # Reproject to World Mercator to avoid calculating area with a geographic CRS
    valid_map_projections = valid_map_projections.to_crs('EPSG:3395')

    # Choose the projection with the smallest area to minimize distortion
    projection_to_use = valid_map_projections[valid_map_projections.geometry.area == valid_map_projections.geometry.area.min()]
    return str(projection_to_use.code.iloc[0])

    
def calculate_trail_miles(mask: gpd.GeoSeries, trails: gpd.GeoSeries) -> str:
    projection_to_use = get_map_projection(mask)
    trails_projected = trails.to_crs(projection_to_use) 
    trail_miles = round(sum(trails_projected['geometry'].length)/1609.344,3)
    return f'{trail_miles} Miles of Trail Within Area of Interest Based on {str(trails_projected.crs).upper()} Projection'
    

# Visualize the clipped feature layers
def show(clipped_layers, mask, plot_title, trails):
    figure, ax = plt.subplots(figsize=(12,8))
    ax.set_title(plot_title)
    
    mask.plot(ax=ax, color='floralwhite')
    try: 
        clipped_layers['trails'].plot(ax=ax, color='indianred',linestyle='dashed',linewidth=0.8, zorder=float('inf'))
    except Exception as e:
        print(f"No trails to map: {e}")
    try: 
        clipped_layers['water'].plot(ax=ax,color='skyblue')
    except Exception as e:
        print(f"No water to map: {e}")
    try: 
        clipped_layers['streets'].plot(ax=ax,color='gainsboro')
    except Exception as e:
        print(f"No streets to map: {e}")
    try: 
        clipped_layers['roads'].plot(ax=ax, color='darkgrey',linewidth=1.5)
    except Exception as e:
        print(f"No roads to map: {e}")
    try: 
        clipped_layers['highways'].plot(ax=ax, color='dimgrey',linewidth=2)
    except Exception as e:
        print(f"No highways to map: {e}")
    try: 
        clipped_layers['parks'].plot(ax=ax,color='beige')
    except Exception as e:
        print(f"No parks to map: {e}")
    try: 
        clipped_layers['buildings'].plot(ax=ax,color='silver')
    except Exception as e:
        print(f"No buildings to map: {e}")


# Main function to create and save a trail mileage map
def create_trail_miles_map(area, feature_layers_payload):
    mask = create_mask(area)
    feature_layers = get_features(area, feature_layers_payload) 
    clipped_layers = clip_layers(feature_layers,mask)
    try:
        plot_title = calculate_trail_miles(mask, clipped_layers['trails'])
    except:
        plot_title = "No trail miles found"
    show(clipped_layers, mask, plot_title, clipped_layers['trails'])
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
            'waterway': ['river']
        },
        'buildings': {
            'building': True
        }
    }
        
    north_bound = 37.335
    south_bound = 37.25
    east_bound = -107.81
    west_bound = -107.915


    bbox = [north_bound, south_bound, east_bound, west_bound]
    placename = 'Durango, Colorado, USA'

    area = bbox # | placename

    create_trail_miles_map(area, feature_layers_payload)



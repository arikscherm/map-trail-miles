import osmnx
import geopandas as gpd
from shapely.geometry import Polygon
import matplotlib.pyplot as plt

#Use bounding box or placename to create polygon boundary for feature layers
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

#Create a dictionary of GeoDataFrames for each feature layer tag
def get_features(area: gpd.GeoSeries, feature_layers_payload: dict) -> dict:
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
            
    #Filter dictionary to include only GeoDataFrame values
    return {k: v for k, v in feature_layers.items() if isinstance(v, gpd.GeoDataFrame)}


def clip_layers(feature_layers: dict, mask: gpd.GeoSeries) -> dict:
    clipped_layers = {key: gpd.clip(gdf,mask) for key, gdf in feature_layers.items()}
    return clipped_layers
    
    
def calculate_trail_miles(trails_gdf: gpd.GeoSeries) -> float:
    area_pcs = 'EPSG:2774' #TODO: Paramterize this
    trails_pcs = trails_gdf.to_crs(area_pcs) 
    trail_miles = round(sum(trails_pcs['geometry'].length)/1609.34,3)
    return f'{trail_miles} Miles of Trail Within Area of Interest Based on {str(trails_pcs.crs).upper()} Projection'
    
    
def show(clipped_layers, mask, plot_title, trails_gdf):
    figure, ax = plt.subplots(figsize=(12,8))
    ax.set_title(plot_title)
    
    mask.plot(ax=ax, color='floralwhite')
    clipped_layers['trails'].plot(ax=ax, color='indianred',linestyle='dashed',linewidth=0.8, zorder=float('inf'))
    clipped_layers['water'].plot(ax=ax,color='skyblue')
    clipped_layers['streets'].plot(ax=ax,color='gainsboro')
    clipped_layers['roads'].plot(ax=ax, color='darkgrey',linewidth=1.5)
    clipped_layers['highways'].plot(ax=ax, color='dimgrey',linewidth=2)
    clipped_layers['parks'].plot(ax=ax,color='beige')
    clipped_layers['buildings'].plot(ax=ax,color='silver')

def create_trail_miles_map(area, feature_layers_payload):
    mask = create_mask(area)
    feature_layers = get_features(area, feature_layers_payload) 
    clipped_layers = clip_layers(feature_layers,mask)
    plot_title = calculate_trail_miles(clipped_layers['trails'])
    show(clipped_layers, mask, plot_title, clipped_layers['trails'])
    plt.savefig('trails.pdf')



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
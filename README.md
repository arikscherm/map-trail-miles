# map-trail-miles

This project maps out features from OpenStreetMap and calculates total trail mileage within a geographic area of interest.

## Prerequisites

Before running, ensure the following Python libraries are installed:

- [Shapely](https://shapely.readthedocs.io/en/stable/installation.html)
- [GeoPandas](https://geopandas.org/en/stable/getting_started.html)
- [OSMnx](https://osmnx.readthedocs.io/en/stable/installation.html)
- [Matplotlib](https://matplotlib.org/stable/index.html)


To set up a conda environment for this project, run 
`conda env create -f environment.yml`

## Usage

The main function in the `map.py` script, `create_trail_miles_map()` takes in two arguments.
1. `area`: The geographic area of interest. This can be defined in two ways:
   1. A **placename** that Nominatim/OpenStreetMap recognizes (e.g., "Durango, Colorado, USA").
   2. A **list of coordinates** which define a [bounding box](https://www.keene.edu/campus/maps/tool/) `[north_bound, south_bound, east_bound, west_bound]`.

2. `feature_class_payload`: This determines which feature layers and tags are fetched from OpenStreetMap.

Here's an example using a bounding box around Durango, Colorado:

  ```python
  area = [37.335, 37.25, -107.81, -107.915]

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
```

<img width="705" alt="image" src="https://github.com/user-attachments/assets/f7c11be8-57d4-4412-b5a8-90822c5e02ce">



import pathlib
import unittest
import geopandas as gpd
from shapely.geometry import Polygon
from shapely.geometry import LineString
from map import create_mask
from map import get_features
from map import clip_layers
from map import get_map_projection
from map import filter_trails


class TestCreateMask(unittest.TestCase):
	
	def test_valid_bbox(self):
		valid_bbox = [50.5, 49.5, -99.5, -100.5]
		result = create_mask(valid_bbox)
		self.assertEqual(type(result), gpd.GeoDataFrame)
		self.assertEqual(type(result['geometry'].iloc[0]), Polygon)

	def test_valid_placename(self):
		valid_placename = "Globeville, Denver, Colorado, USA"
		result = create_mask(valid_placename)
		self.assertEqual(type(create_mask(valid_placename)), gpd.GeoDataFrame)
		self.assertEqual(type(result['geometry'].iloc[0]), Polygon)

	def test_invalid_bbox(self):
		invalid_bbox = [1,2,3]
		with self.assertRaises(ValueError):
			result = create_mask(invalid_bbox)

	def test_invalid_placename(self):
		invalid_placename = "Placename not found in OSM"
		with self.assertRaises(Exception):
			result = create_mask(invalid_placename)

	def test_invalid_type(self):
		invalid_input_type = 100
		with self.assertRaises(Exception):
			result = create_mask(invalid_input_type)

	# def test_out_of_bound_coordinates(self):
	# 	out_of_bound_coordinates = [200,199,-200,-199]
	# 	with self.assertRaises(Exception):
	# 		result = create_mask(out_of_bound_coordinates)


class TestGetFeatures(unittest.TestCase):

	# inputs for get_features
	feature_layers_payload = {
	       'highways': {
	           'highway': ['motorway']
	       }
	   }
	
	empty_result_payload = {
			'some_layer' : {
				'some_tag' : ['attributes']
			}
	}

	invalid_payload = {'invalid_tag' : 'invalid_feature_layer'}
	
	valid_placename = "Globeville, Denver, Colorado, USA"

	def test_valid_bbox(self):
		#bbox around I-25 and I-70
		valid_bbox = [39.78, 39.77, -104.98, -104.99]
		result = get_features(valid_bbox, self.feature_layers_payload)
		self.assertEqual(type(result), dict)
		self.assertEqual(type(result.get('highways')), gpd.GeoDataFrame)

	def test_valid_placename(self):
		result = get_features(self.valid_placename, self.feature_layers_payload)
		self.assertEqual(type(result), dict)
		self.assertEqual(type(result.get('highways')), gpd.GeoDataFrame)

	def test_empty_result(self):
		with self.assertRaises(Exception):	
			result = get_features(self.valid_placename, self.empty_result_payload)

	def test_invalid_payload(self):
		with self.assertRaises(Exception):	
			result = get_features(self.valid_placename, self.invalid_payload)


class TestClipLayers(unittest.TestCase):

	# Create mock inputs for clip_layers
	test_line_in_bounds = LineString([(1,1), (1,5)])
	test_line_out_of_bounds = LineString([(8,1), (8,20)])
	test_polygon_in_bounds = Polygon([(2,2),(4,2),(3,3)])
	test_polygon_out_of_bounds = Polygon([(5,8),(7,8),(6,20)])

	test_lines_gdf = gpd.GeoDataFrame({'geometry' : [test_line_in_bounds, test_line_out_of_bounds]})
	test_polygons_gdf = gpd.GeoDataFrame({'geometry' : [test_polygon_in_bounds, test_polygon_out_of_bounds]})

	layers_to_clip = {
		'lines' : test_lines_gdf,
		'polygons' : test_polygons_gdf
	}

	mask_polygon = Polygon([(0,0),(0,10),(5,25),(10 ,10),(10,0)])
	mask_gdf = gpd.GeoDataFrame({'geometry' : [mask_polygon]})

	def test_clip_layers(self):
		#maybe floor these to make sure contains() doesn't mess up math
		result = clip_layers(self.mask_gdf, self.layers_to_clip)
		self.assertEqual(type(result), dict)
		clipped_lines = gpd.GeoSeries(result['lines']['geometry'])
		clipped_polygons = gpd.GeoSeries(result['polygons']['geometry'])

		lines_clipped_correctly = self.mask_gdf['geometry'].contains(clipped_lines.all()).iloc[0]
		self.assertEqual(lines_clipped_correctly, True)
		polygons_clipped_correctly = self.mask_gdf['geometry'].contains(clipped_polygons[1]).iloc[0]
		self.assertEqual(polygons_clipped_correctly, True)


class TestMapProjection(unittest.TestCase):

	def test_epsg2774(self):
		polygon = Polygon([(-107.915, 37.25),(-107.915, 37.35),(-107.81, 37.35),(-107.81, 37.25)])
		mask = gpd.GeoDataFrame({'geometry' : [polygon]})
		result = get_map_projection(mask)
		self.assertEqual(result, 'EPSG:2774')


	def test_epsg3395(self):
		polygon = Polygon([(137.23, -26.91),(137.23, -26.92),(137.24, -26.92),(137.24, -26.91)])
		mask = gpd.GeoDataFrame({'geometry' : [polygon]})
		result = get_map_projection(mask)
		self.assertEqual(result, 'EPSG:3395')


class TestFilterTrails(unittest.TestCase):
	test_data = pathlib.Path().resolve() / 'test_data'
	unfiltered_trails = gpd.read_file(f'{test_data}/test_trails.geojson')
	filtered_trails = filter_trails(unfiltered_trails)

	def test_fetched_paths(self):
		self.assertTrue(self.filtered_trails.loc[self.filtered_trails['highway'] == 'path'].bool)

	def test_fetched_footways(self):
		self.assertTrue(self.filtered_trails.loc[self.filtered_trails['highway'] == 'footway'].bool)

	def test_filter_footways(self):
		footways = self.filtered_trails.loc[self.filtered_trails['highway'] == 'footway']

		self.assertTrue(footways.loc[footways['surface'] == 'concrete'].empty)
		self.assertTrue(footways.loc[footways['surface'] == 'asphalt'].empty)
		self.assertTrue(footways.loc[footways['surface'] == 'paved'].empty)


if __name__ == '__main__':
    unittest.main()

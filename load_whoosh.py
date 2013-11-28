#!/usr/bin/env python
# -*- coding: utf-8 -*-
DATABASE = ('dbname=epsg82 user=tompohys host=localhost')
INDEX = "index"

import os,sys
import psycopg2
import psycopg2.extensions
psycopg2.extensions.register_type(psycopg2.extensions.UNICODE)

from whoosh.index import create_in, open_dir
from whoosh.fields import *
from whoosh.query import *
from whoosh.qparser import QueryParser
from osgeo import gdal, osr, ogr
from pprint import pprint
from whoosh import fields, columns
from whoosh.analysis import StemmingAnalyzer


###############################################################################
print "INICIALIZING"
###############################################################################
print " - DATABASE"
con = psycopg2.connect(DATABASE)
if not con:
  print "Connection to Postgres FAILED"
  sys.exit(1)
con.set_client_encoding('utf-8')
cur = con.cursor()


print " - WHOOSH!"
class EPSGSchema(SchemaClass):
  
  code = TEXT(stored = True, sortable=True, field_boost=5.0) # "EPSG:4326" #coord_ref_sys_code
  code_trans = NUMERIC(stored = True, sortable = True, field_boost = 5.0)
  name = TEXT(stored = True, sortable=True, spelling=True, field_boost=3.0, analyzer=StemmingAnalyzer()) # Name "WGS 84" #coord_ref_sys_name
  alt_name = STORED
  kind = ID(stored = True) # "ProjectedCRS" | "GeodeticCRS" #coord_ref_sys_kind
  area = TEXT(stored = True, sortable=True, spelling=True) #epsg_area/area_of_use
  status = BOOLEAN(stored = True) # "1 = Valid", "0 - Invalid"
  popularity = NUMERIC(stored = True, sortable=True)  # number [0..1] - our featured = 1

  # Description of used transformation - "", "Czech republic (accuracy 1 meter)"
  trans = TEXT(stored = True, sortable=True, spelling=True, field_boost=3.0, analyzer=StemmingAnalyzer()) # area of used towgs transformation + (accuracy) else ""
  trans_alt_name = STORED
  trans_remarks = TEXT(stored = True)
  
  # Specific fields for all coordinate systems
  wkt = TEXT(stored = True)
  bbox = NUMERIC # [area_north_bound_lat,area_west_bound_lon,area_south_bound_lat,area_east_bound_lon]

  scope = STORED # crs_scope
  remarks = STORED # remarks
  information_source = STORED # information_source
  revision_date = STORED # revision_date

  # Advanced with additional types such as "Elipsoid" | "Area" | ...
  datum_code = NUMERIC(stored = True, field_boost=5.0) # epsg code for stored CRS
  children_code = NUMERIC(stored = True)
  data_source = TEXT(stored = True)
  uom = TEXT(stored = True)
  target_uom = STORED
  prime_meridian = NUMERIC(stored = True)
  greenwich_longitude = NUMERIC(stored=True)
  concatop = STORED
  method = STORED
  files = STORED
  reverse = STORED
  orientation = STORED
  abbreviation = STORED
  order = STORED
  description = STORED
  primary = STORED
  #datum_name = TEXT(stored = True, sortable=True, spelling=True, field_boost=3.0, analyzer=stem_ana)
  #datum_deprecated = BOOLEAN(stored = True)
  #towgs = ID(stored = True) # epsg code for transformation used in wkt or empty
  #geogcs = ID(stored = True) # 
  #ellipsoid_code = NUMERIC(stored = True, field_boost=5.0) 
  #ellipsoid_name = TEXT(stored = True, sortable=True, spelling=True, field_boost=3.0 ,analyzer=stem_ana)
  #ellipsoid_deprecated = BOOLEAN(stored = True)
  
  # Specific for projected coordinate systems
  #projection = ID(stored = True)

# MAKE DIRECTORY AND CREATE INDEX
if not os.path.exists(INDEX):
    os.mkdir(INDEX)
ix = create_in(INDEX, EPSGSchema)

###############################################################################
print " - SELECT EPSG FROM COORDINATE REFERENCE SYSTEM AND TRANSFORMATION"
###############################################################################

cur.execute('SELECT coord_ref_sys_code, coord_ref_sys_name,crs_scope, remarks, information_source, revision_date,datum_code, area_of_use_code,coord_ref_sys_kind,deprecated,source_geogcrs_code,data_source  FROM epsg_coordinatereferencesystem WHERE coord_ref_sys_code > 5513 and coord_ref_sys_code < 5600')
for code, name, scope, remarks, information_source, revision_date,datum_ref_sys_code, area_code, coord_ref_sys_kind, deprecated, source_geogcrs_code,data_source in cur.fetchall():
  
  try:
    name = name.encode('LATIN1').decode('utf-8')
  except:
    print "NOT POSIBLE TO DECODE:", code, name
    continue
  
  #Load WKT from GDAL
  ref = osr.SpatialReference()
  ref.ImportFromEPSG(int(code))  
  text = ref.ExportToWkt().decode('utf-8')
  
  # Get boundingbox and area of use
  cur.execute('SELECT area_of_use, area_north_bound_lat, area_west_bound_lon, area_south_bound_lat, area_east_bound_lon FROM epsg_area WHERE area_code = %s;', (area_code,))
  area_of_use = cur.fetchall()
  for area, area_north_bound_lat, area_west_bound_lon, area_south_bound_lat, area_east_bound_lon in area_of_use:
    bbox = area_north_bound_lat,area_west_bound_lon,area_south_bound_lat,area_east_bound_lon

  # Get alias of name
  cur.execute('SELECT alias FROM epsg_alias WHERE object_table_name = %s and object_code = %s', ("epsg_coordinatereferencesystem", code,))
  for alt_name in cur.fetchall():
    pass
  
  popularity = 1.0
  status = int(deprecated)
  code = str(code).decode('utf-8')
  reverse = 0
  
  doc = {
    'code': code,
    'code_trans' : 0,
    'name': name,
    'alt_name' : alt_name,
    'kind': u"CRS-" + coord_ref_sys_kind.replace(" ", ""),
    'area': area,
    'status': status,
    'popularity': popularity,
    'trans' : u"",
    'trans_alt_name' : u"",
    'trans_remarks': u"",
    'wkt': text,
    'bbox': bbox,
    'scope': scope,
    'remarks': remarks,
    'information_source': information_source,
    'revision_date': revision_date,
    'datum_code' : datum_ref_sys_code,
    'children_code' : u"",
    'data_source' : data_source,
    'uom' : u"",
    'target_uom': u"",
    'prime_meridian' : 0,
    'greenwich_longitude' : 0,
    'concatop' : u"",
    'method' : u"",
    'files' : u"",
    'reverse' : reverse,
    'orientation' : u"",
    'abbreviation' : u"",
    'order' : u"",
    'description':u"",
    'primary' : 0
    }  

# transofrmation to wgs84
  cur.execute('SELECT epsg_coordoperation.coord_op_code, epsg_coordoperation.coord_op_accuracy, epsg_coordoperation.coord_op_type, epsg_area.area_of_use, epsg_coordoperation.deprecated, epsg_coordoperation.coord_op_scope, epsg_coordoperation.remarks, epsg_coordoperation.information_source, epsg_coordoperation.revision_date, epsg_coordoperation.uom_code_source_coord_diff,epsg_coordoperation.coord_op_method_code FROM epsg_coordoperation LEFT JOIN epsg_area ON area_of_use_code = area_code  WHERE source_crs_code = %s and target_crs_code = 4326',(source_geogcrs_code,))
  towgs84 = cur.fetchall()  
  op_code_original = 0
  op_code_trans = {}
  towgs84_original = ref.GetTOWGS84()
  
  if len(towgs84) != 0:
    for op_code, op_accuracy,coord_op_type, area, deprecated, coord_op_scope, remarks, information_source, revision_date,uom_code,coord_op_method_code in towgs84:
      cur.execute('SELECT parameter_value, param_value_file_ref FROM epsg_coordoperationparamvalue WHERE coord_op_code = %s', (op_code, ))
      values = cur.fetchall()
      if len(values) == 7:
        v = tuple( map(lambda x: float(x[0]), values) ) # tuple of 7 floats
      elif len(values) == 3:
        v = tuple( map(lambda x: float(x[0]), values) + [0]*4 ) # tuple of 3+4 floats
      elif len(values) == 1 and values[0][1] != '': 
        v = values[0][1] # nadgrid file
    
      #print op_code, values
      op_code_trans[op_code] = v
      if towgs84_original == v:
        op_code_original = op_code
        #print "ORIGINAL",code, op_code_original

          
          
    for op_code, op_accuracy, coord_op_type, area, deprecated, coord_op_scope, remarks, information_source, revision_date,uom_code,coord_op_method_code in towgs84:
      popularity_accuracy = 0.0
      if op_accuracy == None or op_accuracy == 0.0:
        trans = area + u" "+ u"(unknown accuracy)"
      else:
        popularity_accuracy = 1.0 / op_accuracy
        trans = area + u" " + str(op_accuracy) + u"m accuracy"
    
      values = op_code_trans[op_code]

      popularity_trans = 0.5
      if (values != (0,0,0,0,0,0,0) and type(values) == tuple):
        ref.SetTOWGS84(*values)
      elif type(values) == str:
        pass
        # TODO: NADGRIDS: WKT PROJ EXTENSION[] with +nadgrids http://www.spatialreference.org/ref/sr-org/6/prettywkt/
        # read by ref.GetAttrValue('EXTENSION',1)
      else:
        popularity_trans = 0.0

      if op_code == op_code_original:
        #doc['code'] = code
        doc['wkt'] = text
        popularity_trans = 3.0
        doc['primary'] = 1
      else:
        doc['wkt'] = ref.ExportToWkt().decode('utf-8')
        # doc['scope'] = coord_op_scope
        doc['trans_remarks'] = remarks
        # doc['information_source'] = information_source
        # doc['revision_date'] = revision_date
      
      cur.execute('SELECT uom_code,unit_of_meas_name FROM epsg_unitofmeasure WHERE uom_code = %s', (uom_code,))
      for uom_code, unit_name in cur.fetchall():
        doc['uom'] = unit_name
      
      cur.execute('SELECT coord_op_method_code,coord_op_method_name FROM epsg_coordoperationmethod WHERE coord_op_method_code = %s', (coord_op_method_code,))
      for method_code, method_name in cur.fetchall():
        doc['method'] = method_name
      
      cur.execute('SELECT alias FROM epsg_alias WHERE object_table_name = %s and object_code = %s', ("epsg_coordoperation", op_code, ))
      for alt_name in cur.fetchall():
        doc['trans_alt_name'] = alt_name
      if coord_op_type == "concatenated operation":
        cur.execute('SELECT single_operation_code,op_path_step FROM epsg_coordoperationpath WHERE concat_operation_code = %s ', (op_code,))
        step_codes = []
        for single_op, step in cur.fetchall():
          step_codes.append(single_op)
        doc['concatop'] = step_codes, # STEP [1235,5678,4234] , codes of transformation
          
        
      if doc['wkt'] == "" or doc['wkt'] == None:
        popularity = 0.0 
      
      doc['code_trans'] = op_code  
      doc['popularity'] = popularity + popularity_trans + popularity_accuracy
      doc['trans'] = trans
      doc['status'] = int(status or deprecated)
      
      # WRITE INTO WHOOSH!
      with ix.writer() as writer:
        writer.add_document(**doc)   
  else:
    
    with ix.writer() as writer:
      writer.add_document(**doc)
      
###############################################################################
print " - SELECT EPSG FROM DATUM"
###############################################################################

cur.execute('SELECT datum_code, datum_name, datum_type, ellipsoid_code, area_of_use_code, datum_scope, remarks, information_source, revision_date, data_source, deprecated, prime_meridian_code  FROM epsg_datum LIMIT 10') # 
for code, name, kind, ellipsoid_code, area_code,scope,remarks,information_source,revision_date,data_source, deprecated, prime_meridian_code in cur.fetchall():
  code = str(code)
  
  cur.execute('SELECT area_of_use, area_north_bound_lat, area_west_bound_lon, area_south_bound_lat, area_east_bound_lon FROM epsg_area WHERE area_code = %s;', (area_code,))
  area_of_use = cur.fetchall()
  for area, area_north_bound_lat, area_west_bound_lon, area_south_bound_lat, area_east_bound_lon in area_of_use:
    bbox = area_north_bound_lat,area_west_bound_lon,area_south_bound_lat,area_east_bound_lon
  
  cur.execute('SELECT alias FROM epsg_alias WHERE object_table_name = %s and object_code = %s', ("epsg_datum",code,))
  for alt_name in cur.fetchall():
    pass
    
  doc = {
          'code': code + u"-datum",
          'code_trans' : 0,
          'name': name,
          'alt_name' : alt_name,
          'kind': u"Datum-" + kind,
          'area': area,
          'status': deprecated,
          'popularity': 1.0,
          'trans' : u"",
          'trans_alt_name' : u"",
          'trans_remarks': u"",
          'wkt': u"",
          'bbox': bbox,
          'scope': scope,
          'remarks': remarks,
          'information_source': information_source,
          'revision_date': revision_date,
          'datum_code' : 0,
          'children_code' : ellipsoid_code,
          'data_source' : data_source,
          'uom' : u"",
          'target_uom': u"",
          'prime_meridian' : prime_meridian_code,
          'greenwich_longitude' : 0,
          'concatop' : u"",
          'method' : u"",
          'files' : u"",
          'reverse' : reverse,
          'orientation' : u"",
          'abbreviation' : u"",
          'order' : u"",
          'description':u"",
          'primary' : 1
          
          
          
    
    }
   
  with ix.writer() as writer:
    writer.add_document(**doc)


###############################################################################
print " - SELECT EPSG FROM ELLIPSOID"
###############################################################################

cur.execute('SELECT ellipsoid_code, ellipsoid_name, uom_code, remarks, information_source, revision_date, data_source, deprecated FROM epsg_ellipsoid LIMIT 10') # 
for code, name, uom_code,remarks,information_source,revision_date,data_source, deprecated in cur.fetchall():
  code = str(code)
  
  cur.execute('SELECT area_of_use, area_north_bound_lat, area_west_bound_lon, area_south_bound_lat, area_east_bound_lon FROM epsg_area WHERE area_code = %s;', (area_code,))
  area_of_use = cur.fetchall()
  for area, area_north_bound_lat, area_west_bound_lon, area_south_bound_lat, area_east_bound_lon in area_of_use:
    bbox = area_north_bound_lat,area_west_bound_lon,area_south_bound_lat,area_east_bound_lon
  
  cur.execute('SELECT alias FROM epsg_alias WHERE object_table_name = %s and object_code = %s', ("epsg_ellipsoid", code, ))
  for alt_name in cur.fetchall():
    doc['alt_name'] = alt_name
  
  cur.execute('SELECT unit_of_meas_name FROM epsg_unitofmeasure WHERE uom_code = %s ', (uom_code, ))
  for unit_name in cur.fetchall():
    pass
  
  doc = {
    'code': code + u"-ellipsoid",
    'code_trans' : 0,
    'name': name,
    'alt_name' : alt_name,
    'area': area,
    'wkt': u"",
    'bbox': bbox,
    'scope': u"",
    'remarks': remarks,
    'trans_remarks': u"",
    'information_source': information_source,
    'revision_date': revision_date,
    'status': int(deprecated),
    'trans' : u"",
    'trans_alt_name' : u"",
    'datum_code' : 0,
    'uom' : unit_name,
    'target_uom': u"",
    'kind': u"Ellipsoid",
    'popularity': 1.0,
    'children_code' : 0,
    'data_source' : data_source,
    'prime_meridian' : 0,
    'greenwich_longitude' : 0,
    'concatop' : u"",
    'method' : u"",
    'files' : u"",
    'reverse' : reverse,
    'orientation' : u"",
    'abbreviation' : u"",
    'order' : u"",
    'description':u"",
    'primary' : 1    
    }
    
  with ix.writer() as writer:
    writer.add_document(**doc)
    
###############################################################################
print " - SELECT EPSG FROM PRIME MERIDIAN"
###############################################################################

cur.execute('SELECT prime_meridian_code, prime_meridian_name,greenwich_longitude, uom_code, remarks, information_source, revision_date, data_source, deprecated FROM epsg_primemeridian LIMIT 10') # 
for code, name, greenwich_longitude, uom_code,remarks,information_source,revision_date,data_source, deprecated in cur.fetchall():
  code = str(code)

  cur.execute('SELECT alias FROM epsg_alias WHERE object_table_name = %s and object_code = %s', ("epsg_primemeridian", code, ))
  for alt_name in cur.fetchall():
    doc['alt_name'] = alt_name
    
  cur.execute('SELECT unit_of_meas_name FROM epsg_unitofmeasure WHERE uom_code = %s ', (uom_code, ))
  for unit_name in cur.fetchall():
    pass
  doc = {
    'code': code + u"-primemeridian",
    'code_trans' : 0,
    'name': name,
    'alt_name' : alt_name,
    'area': u"",
    'wkt': u"",
    'bbox': 0,
    'scope': u"",
    'remarks': remarks,
    'trans_remarks': u"",
    'information_source': information_source,
    'revision_date': revision_date,
    'status': int(deprecated),
    'trans' : u"",
    'trans_alt_name' : u"",
    'datum_code' : 0,
    'uom' : unit_name,
    'target_uom': u"",
    'kind': u"Prime meridian",
    'popularity': 1.0,
    'children_code' : 0,
    'data_source' : data_source,
    'prime_meridian' : 0,
    'greenwich_longitude' : greenwich_longitude,
    'concatop' : u"",
    'method' : u"",
    'files' : u"",
    'reverse' : reverse,
    'orientation' : u"",
    'abbreviation' : u"",
    'order' : u"",
    'description':u"",
    'primary' : 1      
    
    

    }
    
    
  with ix.writer() as writer:
    writer.add_document(**doc)

###############################################################################
print " - SELECT EPSG FROM METHOD"
###############################################################################

cur.execute('SELECT coord_op_method_code, coord_op_method_name,reverse_op, remarks, information_source, revision_date, data_source, deprecated FROM epsg_coordoperationmethod LIMIT 10') # 
for code, name, reverse_op, remarks, information_source, revision_date, data_source, deprecated in cur.fetchall():
  code = str(code)


  cur.execute('SELECT alias FROM epsg_alias WHERE object_table_name = %s and object_code = %s', ("epsg_coordoperationmethod", code, ))
  for alt_name in cur.fetchall():
    doc['alt_name'] = alt_name
    
    
  doc = {
    'code': code + u"-method",
    'code_trans' : 0,
    'name': name,
    'alt_name' : alt_name,
    'area': u"",
    'wkt': u"",
    'bbox': 0,
    'scope': u"",
    'remarks': remarks,
    'trans_remarks': u"",
    'information_source': information_source,
    'revision_date': revision_date,
    'status': int(deprecated),
    'trans' : u"",
    'trans_alt_name' : u"",
    'datum_code' : 0,
    'uom' : u"",
    'target_uom': u"",
    'kind': u"Method",
    'popularity': 1.0,
    'children_code' : 0,
    'data_source' : data_source,
    'prime_meridian' : 0,
    'greenwich_longitude' : u"",
    'concatop' : u"",
    'method' : u"",
    'files' : u"",
    'reverse' : reverse_op,
    'orientation' : u"",
    'abbreviation' : u"",
    'order' : u"",
    'description':u"",
    'primary' : 1      
    
    

    }
  with ix.writer() as writer:
    writer.add_document(**doc)

###############################################################################
print " - SELECT EPSG FROM COORDINATE SYSTEMS"
###############################################################################

cur.execute('SELECT coord_sys_code, coord_sys_name, coord_sys_type, remarks, information_source, revision_date, data_source, deprecated FROM epsg_coordinatesystem LIMIT 10') # 
for code, name, kind, remarks, information_source, revision_date, data_source, deprecated in cur.fetchall():
  code = str(code)

  doc = {
    'code': code + u"-coordsys",
    'code_trans' : 0,
    'name': name,
    'alt_name' : u"",
    'area': u"",
    'wkt': u"",
    'bbox': 0,
    'scope': u"",
    'remarks': remarks,
    'trans_remarks': u"",
    'information_source': information_source,
    'revision_date': revision_date,
    'status': int(deprecated),
    'trans' : u"",
    'trans_alt_name' : u"",
    'datum_code' : 0,
    'uom' : u"",
    'target_uom': u"",
    'kind': u"CoordSys-" + kind,
    'popularity': 1.0,
    'children_code' : 0,
    'data_source' : data_source,
    'prime_meridian' : 0,
    'greenwich_longitude' : u"",
    'concatop' : u"",
    'method' : u"",
    'files' : u"",
    'reverse' : 0,
    'orientation' : u"",
    'abbreviation' : u"",
    'order' : u"",
    'description':u"",
    'primary' : 1      

    }
    
  with ix.writer() as writer:
    writer.add_document(**doc)

###############################################################################
print " - SELECT EPSG FROM COORDINATE AXIS"
###############################################################################

cur.execute('SELECT epsg_coordinateaxis.coord_axis_code, epsg_coordinateaxis.coord_sys_code, epsg_coordinateaxis.coord_axis_orientation, epsg_coordinateaxis.coord_axis_abbreviation, epsg_coordinateaxis.uom_code, epsg_coordinateaxis.coord_axis_order, epsg_coordinateaxisname.coord_axis_name, epsg_coordinateaxisname.description, epsg_coordinateaxisname.remarks, epsg_coordinateaxisname.information_source, epsg_coordinateaxisname.data_source, epsg_coordinateaxisname.revision_date, epsg_coordinateaxisname.deprecated FROM epsg_coordinateaxis LEFT JOIN epsg_coordinateaxisname ON epsg_coordinateaxis.coord_axis_name_code=epsg_coordinateaxisname.coord_axis_name_code LIMIT 10') # 
for code, sys_code, orientation, abbreviation, uom_code, order, axis_name, description, remarks, information_source, data_source, revision_date, deprecated  in cur.fetchall():
  code = str(code)
  
  cur.execute('SELECT unit_of_meas_name FROM epsg_unitofmeasure WHERE uom_code = %s ', (uom_code, ))
  for unit_name in cur.fetchall():
    pass
    
  doc = {
    'code': code + u"-axis",
    'code_trans' : 0,
    'name': axis_name,
    'alt_name' : u"",
    'area': u"",
    'wkt': u"",
    'bbox': 0,
    'scope': u"",
    'remarks': remarks,
    'trans_remarks': u"",
    'information_source': information_source,
    'revision_date': revision_date,
    'status': int(deprecated),
    'trans' : u"",
    'trans_alt_name' : u"",
    'datum_code' : 0,
    'uom' : unit_name,
    'target_uom': u"",
    'kind': u"Axis",
    'popularity': 1.0,
    'children_code' : sys_code, #for connect to coordinate system
    'data_source' : data_source,
    'prime_meridian' : 0,
    'greenwich_longitude' : u"",
    'concatop' : u"",
    'method' : u"",
    'files' : u"",
    'reverse' : 0,
    'orientation' : orientation,
    'abbreviation' : abbreviation,
    'order' : order,
    'description': description,
    'primary' : 1      
    

    }





  with ix.writer() as writer:
    writer.add_document(**doc)

###############################################################################
print " - SELECT EPSG FROM AREA"
###############################################################################

cur.execute('SELECT area_code, area_name, area_of_use, area_south_bound_lat, area_north_bound_lat, area_west_bound_lon, area_east_bound_lon, area_polygon_file_ref, remarks,information_source,data_source,revision_date,deprecated FROM epsg_area LIMIT 10') # 
for code, name, area,area_south_bound_lat,area_north_bound_lat,area_west_bound_lon,area_east_bound_lon,area_polygon_file_ref,remarks,information_source,data_source,revision_date, deprecated in cur.fetchall():
  code = str(code)
  bbox = area_north_bound_lat,area_west_bound_lon,area_south_bound_lat,area_east_bound_lon
  
  cur.execute('SELECT alias FROM epsg_alias WHERE object_table_name = %s and object_code = %s', ("epsg_area", code, ))
  for alt_name in cur.fetchall():
    doc['alt_name'] = alt_name
  
  doc = {
    'code': code + u"-area",
    'code_trans' : 0,
    'name': name,
    'alt_name' : alt_name,
    'area': area,
    'wkt': u"",
    'bbox': bbox,
    'scope': u"",
    'remarks': remarks,
    'trans_remarks': u"",
    'information_source': information_source,
    'revision_date': revision_date,
    'status': int(deprecated),
    'trans' : u"",
    'trans_alt_name' : u"",
    'datum_code' : 0,
    'uom' : unit_name,
    'target_uom': u"",
    'kind': u"Area",
    'popularity': 1.0,
    'children_code' : 0,
    'data_source' : data_source,
    'prime_meridian' : 0,
    'greenwich_longitude' : u"",
    'concatop' : u"",
    'method' : u"",
    'files': area_polygon_file_ref,
    'reverse' : 0,
    'orientation' : u"",
    'abbreviation' : u"",
    'order' : u"",
    'description': u"",
    'primary' : 1  
    }




  with ix.writer() as writer:
    writer.add_document(**doc)


###############################################################################
print " - SELECT EPSG FROM UNIT OF MEASURE"
###############################################################################

cur.execute('SELECT uom_code, unit_of_meas_name, unit_of_meas_type, target_uom_code, remarks, information_source, data_source, revision_date, deprecated FROM epsg_unitofmeasure LIMIT 10') # 
for code, name, kind, target_uom, remarks, information_source, data_source, revision_date, deprecated in cur.fetchall():
  code = str(code)
  
  cur.execute('SELECT alias FROM epsg_alias WHERE object_table_name = %s and object_code = %s', ("epsg_unitofmeasure", code, ))
  for alt_name in cur.fetchall():
    doc['alt_name'] = alt_name

  if target_uom == 9102:
    target_uom = "angle"
  elif target_uom == 9101:
    target_uom = "radian"
  elif target_uom == 9001:
    target_uom = "metre"
  elif target_uom == 9201:
    target_uom = "unity"
  
  doc = {
    'code': code + u"-units",
    'code_trans' : 0,
    'name': name,
    'alt_name' : alt_name,
    'area': u"",
    'wkt': u"",
    'bbox': u"",
    'scope': u"",
    'remarks': remarks,
    'trans_remarks': u"",
    'information_source': information_source,
    'revision_date': revision_date,
    'status': int(deprecated),
    'trans' : u"",
    'trans_alt_name' : u"",
    'datum_code' : 0,
    'uom' : unit_name,
    'target_uom': target_uom,
    'kind': u"Measure-" + kind,
    'popularity': 1.0,
    'children_code' : 0,
    'data_source' : data_source,
    'prime_meridian' : 0,
    'greenwich_longitude' : u"",
    'concatop' : u"",
    'method' : u"",
    'files': u"",
    'reverse' : 0,
    'orientation' : u"",
    'abbreviation' : u"",
    'order' : u"",
    'description': u"",
    'primary' : 1  
    }
    

  with ix.writer() as writer:
    writer.add_document(**doc)

      
  
      
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
prepGridMask.py

VERSION AND LAST UPDATE:
 v1.0  04/04/2022
 v1.1  05/03/2022

PURPOSE:
 This program creates a grid mask to identify coastal points and 
  open/deep water points, based on water depth and distance to the coast.
 This is useful for model validation against satellite data,
  where coastal areas should be excluded, as well as to run specific 
  assessments comparing deep water with coastal areas.
 prepGridMask.py has an extra option to identify Ocean Names and 
  NWS forecast areas, when running the model passing one argument.

USAGE:
 The grid mask uses the same resolution (lat/lon arrays) as 
  the sample file (see xr.open_dataset below and edit file name) that
  must be given by the user (where lat/lon arrays are defined)
 The file distFromCoast.nc was generated by organizeDistanceToCoast.py
 You can replace etopo1.nc bathymetry by any other source, such as GEBCO,
  just pay attention to longitude standards (-180to180 or 0to360). Both
  distFromCoast.nc and etopo1.nc must be in the same directory you are
  running this code (or symbolic link, ln -s).
 To include the Ocean Names and Forecast Areas identification, user must
  pass an argument where: 1 is for just the large ocean names (North
  Atlantic, South Atlantic etc); 2 is the NCEP/NWS High Seas Marine Zones;
  and 3 is the NCEP/NWS Offshore Marine Zones. The shapefile of such
  areas must be given (see links below with instructions to download it)
  together with the path (see goshp, hsshp, and ofshp below). By default,
  these areas are not included (argument is 0). An example to run and 
  include the Ocean Names and NCEP/NWS High Seas Marine Zones is:
  python3 prepGridMask.py 2

 Fix values mindepth and mindfc can be edited below (see mindepth, and 
  mindfc), as well as the prefix name for the outputs (figures and netcdf),
  gridn

 Example (from linux terminal command line):
  nohup python3 prepGridMask.py 2 >> nohup_prepGridMask.out 2>&1 &

OUTPUT:
 netcdf file gridInfo_*.nc containing:
  mask info identifying land, ocean points, and coastal points.
  distance to the nearest coast
  water depth
  GlobalOceansSeas, HighSeasMarineZones, and OffshoreMarineZones
 figures illustrating these fields

DEPENDENCIES:
 See setup.py and the imports below.
 ww3 sample file (change name ww3gefs.20160921_field.nc below)
 distFromCoast.nc generated by organizeDistanceToCoast.py
 bathymetry (etopo is used by default)
 Shapefiles for the GlobalOceansSeas, HighSeasMarineZones,
  and OffshoreMarineZones. They can be downloaded at:
  https://www.marineregions.org/downloads.php
  https://www.weather.gov/gis/ click on "AWIPS basemaps", 
   "Coastal and Offshore Marine Zones", "High Seas Marine Zones"
   * this does not include a projection file in the directory, so I had 
   to artificially create a .prj file
  https://www.weather.gov/gis/ click on "AWIPS basemaps", 
  "Coastal and Offshore Marine Zones", "Offshore Marine Zones"
   * this does not include a projection file in the directory, so I had 
   to artificially create a .prj file

AUTHOR and DATE:
 04/04/2022: Ricardo M. Campos, first version.
 05/03/2022: Ricardo M. Campos, allow users to choose if they want to
   process ocean names and forecast areas or not (as it take some time).

PERSON OF CONTACT:
 Ricardo M Campos: ricardo.campos@noaa.gov

"""

import numpy as np
from matplotlib.mlab import *
from pylab import *
import matplotlib
matplotlib.use('Agg')
import xarray as xr
import netCDF4 as nc
from mpl_toolkits.basemap import shiftgrid
from matplotlib.colors import BoundaryNorm
import xarray
import matplotlib.pyplot as plt
import cartopy.crs as ccrs
import cartopy
from matplotlib import ticker
# import pickle
import warnings; warnings.filterwarnings("ignore")
# netcdf format
fnetcdf="NETCDF4"

palette = plt.cm.jet
# Font size and style
sl=14
matplotlib.rcParams.update({'font.size': sl}); plt.rc('font', size=sl) 
matplotlib.rc('xtick', labelsize=sl); matplotlib.rc('ytick', labelsize=sl); matplotlib.rcParams.update({'font.size': sl})

fainfo=np.int(0)
if len(sys.argv) == 2 :
	fainfo=np.int(sys.argv[1])
elif len(sys.argv) > 2:
	sys.exit(' Too many inputs')

# -----------------
# Grid Name
gridn='GFS10mxt'
# Minimum water depth
mindepth=80. # in meters
# Minimum distance from the coast
mindfc=50. # in Km
# -----------------
outpath='/home/rmc/develop/'
# -----------------
if fainfo>=1:
	# marineregions Global Ocean shapefile path
	goshp="/home/rmc/develop/shapefiles/GlobalOceansSeas/"
	import salem
	import regionmask
if fainfo>=2:
	# NOAA HighSeasMarineZones
	hsshp="/home/rmc/develop/shapefiles/NOAA/HighSeasMarineZones/"
if fainfo>=3:
	# NOAA OffshoreMarineZones
	ofshp="/home/rmc/develop/shapefiles/NOAA/OffshoreMarineZones/"

# Sample file Model(reference) lat lon array
ds=xr.open_dataset('ww3.gfs-v16.glo_10mxt.PR3.20210924_20211024.nc')
lat = ds['latitude'].values[:]; lon = ds['longitude'].values[:]
if "MAPSTA" in ds.keys():
	mapsta=ds["MAPSTA"].values[:,:]
	nmapsta=1
else:
	nmapsta=0

ds.close(); del ds
print(' read model sample to get lat/lon: OK')

# ====== BATHYMETRY Etopo grid ==============
ds = xr.open_dataset('etopo1.nc')
latb = ds['lat'].values[:]; lonb = ds['lon'].values[:]
b = ds['z'].values[:,:]
# interpolate Bathymetry to Model
dsi = ds.interp(lat=lat[:], lon=lon[:])
ib = dsi['z'].values[:,:]
ds.close(); del ds, dsi
print(' read bathymetry: OK')

# ======  Distance to the Coast ==============
ds = xr.open_dataset('distFromCoast.nc')
latd = ds['latitude'].values[:]; lond = ds['longitude'].values[:]
dfc = ds['distcoast'].values[:,:]
# interpolate to Model
dsc = ds.interp(latitude=lat[:], longitude=lon[:])
idfc = dsc['distcoast'].values[:,:]; ds.close(); del ds, dsc
print(' read distance to coast: OK')

# Build Mask (nan = land excluded; 0 = ocean excluded; 1 = ocean valid)
mask = np.zeros((lat.shape[0],lon.shape[0]),'f')
# excluding continent or model mask
if nmapsta==1:
	ind = np.where((ib>0)|(mapsta>100)|(mapsta==0)); mask[ind[0],ind[1]] = np.nan; del ind
else:
	ind = np.where(ib>0); mask[ind[0],ind[1]] = np.nan; del ind
	
# excluding based on depth and dist-to-coast criteria
ind = np.where( (ib<=(-1*mindepth)) & (idfc>=mindfc) & (np.isnan(mask)==False) ); mask[ind[0],ind[1]] = 1; del ind
mask[:,0]=mask[:,-1]
print(' grid mask: OK')

if fainfo>=1:
	# ======  Ocean Names ==============
	# from https://www.marineregions.org/downloads.php  "Global Oceans and Seas"
	print(' '); print(' Allocating ocean names. This may take a while ...')
	# initialize matrix. Look at lon standard (-180to180 versus 0to360)
	oni = np.zeros((lat.shape[0],lon.shape[0]),'f')
	oni,nlon = shiftgrid(180.,oni,lon,start=False)
	nmask,nlon = shiftgrid(180.,mask,lon,start=False)
	ind=np.where(np.isnan(nmask)==True)
	oni[ind]=np.nan; del ind
	# Read shapefile
	odata = salem.read_shapefile(goshp+"goas_v01.shp")
	# take Ocean Names
	ocnames=np.array(odata['name'].values[:])
	ocnames=np.append(np.array(['Undefined']),ocnames)
	# indexes
	ilon=np.arange(0,lon.shape[0]); ilat=np.arange(0,lat.shape[0])
	milon,milat = meshgrid(ilon,ilat); del ilon,ilat
	# loop through the Oceans
	for i in range(1,size(ocnames)):

		basin = odata.loc[odata['name']==ocnames[i]]
		# basin.reset_index(drop=True, inplace=True)
		# https://regionmask.readthedocs.io/en/v0.3.1/_static/notebooks/mask_numpy.html
		# https://salem.readthedocs.io/en/stable/examples.html

		aux = regionmask.defined_regions.srex.mask(nlon,lat)
		aux.values[:,:]=milon
		aux = aux.salem.subset(shape=basin)
		aux = aux.salem.roi(shape=basin)
		ind=np.where(aux>=0)
		ilon=np.array(aux.values[ind]).astype('int')
		del aux,ind

		aux = regionmask.defined_regions.srex.mask(nlon,lat)
		aux.values[:,:]=milat
		aux = aux.salem.subset(shape=basin)
		aux = aux.salem.roi(shape=basin)
		ind=np.where(aux>=0)
		ilat=np.array(aux.values[ind]).astype('int')
		del aux,ind

		oni[ilat,ilon] = np.int(i)

		del basin,ilat,ilon

		print(' '+ocnames[i]+' : OK')

	# Return to 0to360 lon standard
	nmask[nmask>=0.]=1.; oni=oni*nmask
	foni,nnlon = shiftgrid(0.,oni,nlon,start=False)
	del nnlon,oni,odata

# ======  Forecast Areas ==============
if fainfo>=2:
	# *** High Seas Marine Zones ***
	# from https://www.weather.gov/gis/ click on "AWIPS basemaps", "Coastal and Offshore Marine Zones", "High Seas Marine Zones"
	# this does not include a projection file in the directory. So I had to artificially create a .prj file
	print(' '); print(' Allocating NWS Forecast areas, High Seas Marine Zones. This may take a while ...')
	fcta = np.zeros((lat.shape[0],lon.shape[0]),'f')
	ind=np.where(np.isnan(nmask)==True)
	fcta[ind]=np.nan; del ind
	# Read shapefile
	fdata = salem.read_shapefile(hsshp+"hz30jn17.shp")
	# take Ocean Names
	hsmznames=np.array(fdata['NAME'].values[:])
	hsmznames=np.append(np.array(['Undefined']),hsmznames)
	# loop through the Areas
	for i in range(1,size(hsmznames)):

		basin = fdata.loc[fdata['NAME']==hsmznames[i]]
		# basin.reset_index(drop=True, inplace=True)
		# https://regionmask.readthedocs.io/en/v0.3.1/_static/notebooks/mask_numpy.html
		# https://salem.readthedocs.io/en/stable/examples.html

		aux = regionmask.defined_regions.srex.mask(nlon,lat)
		aux.values[:,:]=milon
		aux = aux.salem.subset(shape=basin)
		aux = aux.salem.roi(shape=basin)
		ind=np.where(aux>=0)
		ilon=np.array(aux.values[ind]).astype('int')
		del aux,ind

		aux = regionmask.defined_regions.srex.mask(nlon,lat)
		aux.values[:,:]=milat
		aux = aux.salem.subset(shape=basin)
		aux = aux.salem.roi(shape=basin)
		ind=np.where(aux>=0)
		ilat=np.array(aux.values[ind]).astype('int')
		del aux,ind

		fcta[ilat,ilon] = np.int(i)

		del basin,ilat,ilon

		print(' '+hsmznames[i]+' : OK')

	# Return to 0to360 lon standard
	fcta=fcta*nmask
	hsmz,nnlon = shiftgrid(0.,fcta,nlon,start=False)
	del nnlon,fdata,fcta

if fainfo>=3:
	# *** Offshore Marine Zones ***
	# from https://www.weather.gov/gis/ click on "AWIPS basemaps", "Coastal and Offshore Marine Zones", "Offshore Marine Zones"
	# this does not include a projection file in the directory. So I had to artificially create a .prj file
	print(' '); print(' Allocating NWS Forecast areas, Offshore Marine Zones. This may take a while ...')
	fcta = np.zeros((lat.shape[0],lon.shape[0]),'f')
	ind=np.where(np.isnan(nmask)==True)
	fcta[ind]=np.nan; del ind
	# Read shapefile
	fdata = salem.read_shapefile(ofshp+"oz22mr22.shp")
	# take Zone Names
	ofmznames=np.array(fdata['NAME'].values[:])
	ofmznames=np.append(np.array(['Undefined']),ofmznames)
	ofmzids=np.array(fdata['ID'].values[:])
	ofmzids=np.append(np.array(['Undefined']),ofmzids)
	# loop through the Areas
	for i in range(1,size(ofmzids)):

		basin = fdata.loc[fdata['ID']==ofmzids[i]]
		# basin.reset_index(drop=True, inplace=True)
		# https://regionmask.readthedocs.io/en/v0.3.1/_static/notebooks/mask_numpy.html
		# https://salem.readthedocs.io/en/stable/examples.html

		aux = regionmask.defined_regions.srex.mask(nlon,lat)
		aux.values[:,:]=milon
		aux = aux.salem.subset(shape=basin)
		aux = aux.salem.roi(shape=basin)
		ind=np.where(aux>=0)
		ilon=np.array(aux.values[ind]).astype('int')
		del aux,ind

		aux = regionmask.defined_regions.srex.mask(nlon,lat)
		aux.values[:,:]=milat
		aux = aux.salem.subset(shape=basin)
		aux = aux.salem.roi(shape=basin)
		ind=np.where(aux>=0)
		ilat=np.array(aux.values[ind]).astype('int')
		del aux,ind

		fcta[ilat,ilon] = np.int(i)

		del basin,ilat,ilon

		print(' '+ofmznames[i]+' : OK')

	# Return to 0to360 lon standard
	fcta=fcta*nmask
	ofmz,nnlon = shiftgrid(0.,fcta,nlon,start=False)
	del nnlon,fdata,fcta
	# ====================

print(' '); print(' Done! Final plots and netcdf output file ...')

# ======== PLOTS =================

# Bathymetry
# Water depth is positive, by definition
ib = np.array(ib*-1); ib[ib<0]=np.nan; ib[np.isnan(mask)==True]=np.nan
levels = np.linspace( ib[(np.isnan(ib)==False)].min(), np.percentile(ib[(np.isnan(ib)==False)],99.), 100)
#
fig, ax = plt.subplots(nrows=1,ncols=1,subplot_kw={'projection': ccrs.PlateCarree()},figsize=(7,4))
ax.set_extent([lon.min(),lon.max(),lat.min(),lat.max()], crs=ccrs.PlateCarree())
gl = ax.gridlines(crs=ccrs.PlateCarree(), draw_labels=True, linewidth=0.5, color='grey', alpha=0.5, linestyle='--')
gl.xlabel_style = {'size': 9, 'color': 'k','rotation':0}; gl.ylabel_style = {'size': 9, 'color': 'k','rotation':0}
plt.contourf(lon,lat,ib,levels,transform = ccrs.PlateCarree(),cmap=palette,extend="max", zorder=2)
ax.add_feature(cartopy.feature.OCEAN,facecolor=("white"))
ax.add_feature(cartopy.feature.LAND,facecolor=("lightgrey"), edgecolor='grey',linewidth=0.5)
ax.add_feature(cartopy.feature.BORDERS, edgecolor='grey', linestyle='-',linewidth=0.5, alpha=1)
ax.coastlines(resolution='110m', color='grey',linewidth=0.5, linestyle='-', alpha=1)
fig.tight_layout()
ax = plt.gca()
pos = ax.get_position()
l, b, w, h = pos.bounds
cax = plt.axes([l+0.07, b-0.07, w-0.15, 0.025]) # setup colorbar axes.
cbar=plt.colorbar(cax=cax, orientation='horizontal'); cbar.ax.tick_params(labelsize=10)
tick_locator = ticker.MaxNLocator(nbins=7); cbar.locator = tick_locator; cbar.update_ticks()
plt.axes(ax)  # make the original axes current again
fig.tight_layout()
# plt.savefig(outpath+'bathymetry_'+gridn+'.eps', format='eps', dpi=200)
plt.savefig(outpath+'bathymetry_'+gridn+'.png', dpi=300, facecolor='w', edgecolor='w',orientation='portrait', papertype=None, format='png',transparent=False, bbox_inches='tight', pad_inches=0.1)
# The pickle command below allows saving the figure for later editing (very convenient for publications etc). Similat to .mat in matlab.
# pickle.dump(fig, open('bathymetry_'+gridn+'.pickle', 'wb'))
plt.close('all'); del ax, fig

# Distance from the coast 
# idfc[np.isnan(mask)==True]=np.nan
idfc[np.isnan(ib)==True]=np.nan
levels = np.linspace( idfc[(np.isnan(idfc)==False)].min(), np.percentile(idfc[(np.isnan(idfc)==False)],99.), 100)
fig, ax = plt.subplots(nrows=1,ncols=1,subplot_kw={'projection': ccrs.PlateCarree()},figsize=(7,4))
ax.set_extent([lon.min(),lon.max(),lat.min(),lat.max()], crs=ccrs.PlateCarree())
gl = ax.gridlines(crs=ccrs.PlateCarree(), draw_labels=True, linewidth=0.5, color='grey', alpha=0.5, linestyle='--')
gl.xlabel_style = {'size': 9, 'color': 'k','rotation':0}; gl.ylabel_style = {'size': 9, 'color': 'k','rotation':0}
plt.contourf(lon,lat,idfc,levels,transform = ccrs.PlateCarree(),cmap=palette,extend="max", zorder=2)
ax.add_feature(cartopy.feature.OCEAN,facecolor=("white"))
ax.add_feature(cartopy.feature.LAND,facecolor=("lightgrey"), edgecolor='grey',linewidth=0.5)
ax.add_feature(cartopy.feature.BORDERS, edgecolor='grey', linestyle='-',linewidth=0.5, alpha=1)
ax.coastlines(resolution='110m', color='grey',linewidth=0.5, linestyle='-', alpha=1)
fig.tight_layout()
ax = plt.gca()
pos = ax.get_position()
l, b, w, h = pos.bounds
cax = plt.axes([l+0.07, b-0.07, w-0.15, 0.025]) # setup colorbar axes.
cbar=plt.colorbar(cax=cax, orientation='horizontal'); cbar.ax.tick_params(labelsize=10)
tick_locator = ticker.MaxNLocator(nbins=7); cbar.locator = tick_locator; cbar.update_ticks()
plt.axes(ax)  # make the original axes current again
fig.tight_layout()
# plt.savefig(outpath+'DistanceToCoast_'+gridn+'.eps', format='eps', dpi=200)
plt.savefig(outpath+'DistanceToCoast_'+gridn+'.png', dpi=300, facecolor='w', edgecolor='w',orientation='portrait', papertype=None, format='png',transparent=False, bbox_inches='tight', pad_inches=0.1)
# The pickle command below allows saving the figure for later editing (very convenient for publications etc). Similat to .mat in matlab.
# pickle.dump(fig, open('DistanceToCoast_'+gridn+'.pickle', 'wb'))
plt.close('all'); del ax, fig

# Final Mask
levels = np.linspace(-2,3,10)
# fig, ax = plt.subplots(figsize=(7,4))
fig, ax = plt.subplots(nrows=1,ncols=1,subplot_kw={'projection': ccrs.PlateCarree()},figsize=(7,4))
# ax = plt.axes(projection=ccrs.Robinson())
# ax = plt.axes(projection=ccrs.PlateCarree()) 
ax.set_extent([lon.min(),lon.max(),lat.min(),lat.max()], crs=ccrs.PlateCarree())
gl = ax.gridlines(crs=ccrs.PlateCarree(), draw_labels=True, linewidth=0.5, color='grey', alpha=0.5, linestyle='--')
gl.xlabel_style = {'size': 9, 'color': 'k','rotation':0}; gl.ylabel_style = {'size': 9, 'color': 'k','rotation':0}
# plt.contourf(lon,lat,foni,levels,transform = ccrs.PlateCarree(),cmap=palette,extend="max", zorder=2)
ax.add_feature(cartopy.feature.OCEAN,facecolor=("white"), zorder=1)
ax.add_feature(cartopy.feature.LAND,facecolor=("lightgrey"), edgecolor='grey',linewidth=0.5, zorder=1)
ax.add_feature(cartopy.feature.BORDERS, edgecolor='grey', linestyle='-',linewidth=0.5, alpha=1, zorder=1)
ax.coastlines(resolution='110m', color='grey',linewidth=0.5, linestyle='-', alpha=1, zorder=3)
norm = BoundaryNorm(levels, ncolors=palette.N, clip=False)
im = ax.contourf(lon,lat,-mask,shading='flat',cmap=palette,norm=norm, zorder=2)
fig.tight_layout()
# plt.savefig(outpath+'Mask_'+gridn+'.eps', format='eps', dpi=200)
plt.savefig(outpath+'Mask_'+gridn+'.png', dpi=300, facecolor='w', edgecolor='w',orientation='portrait', papertype=None, format='png',transparent=False, bbox_inches='tight', pad_inches=0.1)
# The pickle command below allows saving the figure for later editing (very convenient for publications etc). Similat to .mat in matlab.
# pickle.dump(fig, open('Mask_'+gridn+'.pickle', 'wb'))
plt.close('all'); del ax, fig

print('Number of Ocean points: '+repr(mask[mask>=0].shape[0]))
print('Number of Ocean points valid: '+repr(mask[mask>0].shape[0]))

if fainfo>=1:
	# Ocean names
	levels = np.arange(0,size(ocnames)+2,1)
	# fig, ax = plt.subplots(figsize=(7,4))
	fig, ax = plt.subplots(nrows=1,ncols=1,subplot_kw={'projection': ccrs.PlateCarree()},figsize=(7,4))
	# ax = plt.axes(projection=ccrs.Robinson())
	# ax = plt.axes(projection=ccrs.PlateCarree()) 
	ax.set_extent([lon.min(),lon.max(),lat.min(),lat.max()], crs=ccrs.PlateCarree())
	gl = ax.gridlines(crs=ccrs.PlateCarree(), draw_labels=True, linewidth=0.5, color='grey', alpha=0.5, linestyle='--')
	gl.xlabel_style = {'size': 9, 'color': 'k','rotation':0}; gl.ylabel_style = {'size': 9, 'color': 'k','rotation':0}
	# plt.contourf(lon,lat,foni,levels,transform = ccrs.PlateCarree(),cmap=palette,extend="max", zorder=2)
	ax.add_feature(cartopy.feature.OCEAN,facecolor=("white"), zorder=1)
	ax.add_feature(cartopy.feature.LAND,facecolor=("lightgrey"), edgecolor='grey',linewidth=0.5, zorder=1)
	ax.add_feature(cartopy.feature.BORDERS, edgecolor='grey', linestyle='-',linewidth=0.5, alpha=1, zorder=1)
	ax.coastlines(resolution='110m', color='grey',linewidth=0.5, linestyle='-', alpha=1, zorder=3)
	norm = BoundaryNorm(levels, ncolors=palette.N, clip=False)
	im = ax.pcolormesh(lon,lat,foni,shading='flat',cmap=palette,norm=norm, zorder=2)
	im = ax.contour(lon,lat,foni,levels=levels,colors='black',linewidths=0.5,zorder=3)
	fig.tight_layout()
	# plt.savefig(outpath+'OceanNames_'+gridn+'.eps', format='eps', dpi=200)
	plt.savefig(outpath+'OceanNames_'+gridn+'.png', dpi=300, facecolor='w', edgecolor='w',orientation='portrait', papertype=None, format='png',transparent=False, bbox_inches='tight', pad_inches=0.1)
	# pickle.dump(fig, open('OceanNames_'+gridn+'.pickle', 'wb'))
	plt.close('all'); del ax, fig

if fainfo>=2:
	# High Seas Marine Zones
	levels = np.arange(0,size(hsmznames)+1,1)
	# fig, ax = plt.subplots(figsize=(7,4))
	fig, ax = plt.subplots(nrows=1,ncols=1,subplot_kw={'projection': ccrs.PlateCarree()},figsize=(7,4))
	# ax = plt.axes(projection=ccrs.Robinson())
	# ax = plt.axes(projection=ccrs.PlateCarree()) 
	ax.set_extent([lon.min(),lon.max(),lat.min(),lat.max()], crs=ccrs.PlateCarree())
	gl = ax.gridlines(crs=ccrs.PlateCarree(), draw_labels=True, linewidth=0.5, color='grey', alpha=0.5, linestyle='--')
	gl.xlabel_style = {'size': 9, 'color': 'k','rotation':0}; gl.ylabel_style = {'size': 9, 'color': 'k','rotation':0}
	# plt.contourf(lon,lat,foni,levels,transform = ccrs.PlateCarree(),cmap=palette,extend="max", zorder=2)
	ax.add_feature(cartopy.feature.OCEAN,facecolor=("white"), zorder=1)
	ax.add_feature(cartopy.feature.LAND,facecolor=("lightgrey"), edgecolor='grey',linewidth=0.5, zorder=1)
	ax.add_feature(cartopy.feature.BORDERS, edgecolor='grey', linestyle='-',linewidth=0.5, alpha=1, zorder=1)
	ax.coastlines(resolution='110m', color='grey',linewidth=0.5, linestyle='-', alpha=1, zorder=3)
	norm = BoundaryNorm(levels, ncolors=palette.N, clip=False)
	ahsmz=np.copy(hsmz); ahsmz[ahsmz<1]=np.nan
	im = ax.pcolormesh(lon,lat,ahsmz,zorder=2)
	im = ax.contour(lon,lat,hsmz,levels=levels,colors='black',linewidths=0.5,zorder=3)
	fig.tight_layout(); del ahsmz
	# plt.savefig(outpath+'HighSeasMarineZones_'+gridn+'.eps', format='eps', dpi=200)
	plt.savefig(outpath+'HighSeasMarineZones_'+gridn+'.png', dpi=300, facecolor='w', edgecolor='w',orientation='portrait', papertype=None, format='png',transparent=False, bbox_inches='tight', pad_inches=0.1)
	# pickle.dump(fig, open('HighSeasMarineZones_'+gridn+'.pickle', 'wb'))
	plt.close('all'); del ax, fig

if fainfo>=3:
	# Offshore Marine Zones
	levels = np.arange(0,size(ofmznames)+1,1)
	# fig, ax = plt.subplots(figsize=(7,4))
	fig, ax = plt.subplots(nrows=1,ncols=1,subplot_kw={'projection': ccrs.PlateCarree()},figsize=(7,4))
	# ax = plt.axes(projection=ccrs.Robinson())
	# ax = plt.axes(projection=ccrs.PlateCarree()) 
	ax.set_extent([lon.min(),lon.max(),lat.min(),lat.max()], crs=ccrs.PlateCarree())
	gl = ax.gridlines(crs=ccrs.PlateCarree(), draw_labels=True, linewidth=0.5, color='grey', alpha=0.5, linestyle='--')
	gl.xlabel_style = {'size': 9, 'color': 'k','rotation':0}; gl.ylabel_style = {'size': 9, 'color': 'k','rotation':0}
	# plt.contourf(lon,lat,foni,levels,transform = ccrs.PlateCarree(),cmap=palette,extend="max", zorder=2)
	ax.add_feature(cartopy.feature.OCEAN,facecolor=("white"), zorder=1)
	ax.add_feature(cartopy.feature.LAND,facecolor=("lightgrey"), edgecolor='grey',linewidth=0.5, zorder=1)
	ax.add_feature(cartopy.feature.BORDERS, edgecolor='grey', linestyle='-',linewidth=0.5, alpha=1, zorder=1)
	ax.coastlines(resolution='110m', color='grey',linewidth=0.5, linestyle='-', alpha=1, zorder=3)
	norm = BoundaryNorm(levels, ncolors=palette.N, clip=False)
	aofmz=np.copy(ofmz); aofmz[aofmz<1]=np.nan
	im = ax.pcolormesh(lon,lat,aofmz,zorder=2)
	im = ax.contour(lon,lat,ofmz,levels=levels,colors='black',linewidths=0.5,zorder=3)
	fig.tight_layout(); del aofmz
	# plt.savefig(outpath+'OffshoreMarineZones_'+gridn+'.eps', format='eps', dpi=200)
	plt.savefig(outpath+'OffshoreMarineZones_'+gridn+'.png', dpi=300, facecolor='w', edgecolor='w',orientation='portrait', papertype=None, format='png',transparent=False, bbox_inches='tight', pad_inches=0.1)
	# pickle.dump(fig, open('HighSeasMarineZones_'+gridn+'.pickle', 'wb'))
	plt.close('all'); del ax, fig

print('plots ok')

# ================== SAVE NETCDF FILE ==================
# open a new netCDF file for writing.
ncfile = nc.Dataset(outpath+'gridInfo_'+gridn+'.nc', "w", format=fnetcdf) 
ncfile.description='Bathymetry, Distance from the coast, Mask, and Areas (GlobalOceansSeas, NOAA HighSeasMarineZones, NOAA OffshoreMarineZones). Total of '+repr(mask[mask>=0].shape[0])+' Ocean grid points, and '+repr(mask[mask>0].shape[0])+' valid ocean grid points to use.'
# dimensions.
ncfile.createDimension( 'latitude' , lat.shape[0] ); ncfile.createDimension( 'longitude' , lon.shape[0] )
if fainfo>=1:
	ncfile.createDimension('GlobalOceansSeas', ocnames.shape[0] )
if fainfo>=2:
	ncfile.createDimension('HighSeasMarineZones', hsmznames.shape[0] )
if fainfo>=3:
	ncfile.createDimension('OffshoreMarineZones', ofmznames.shape[0] )

# create  variables
lats = ncfile.createVariable('latitude',dtype('float32').char,('latitude',)) 
lons = ncfile.createVariable('longitude',dtype('float32').char,('longitude',)) 
if fainfo>=1:
	vocnames = ncfile.createVariable('names_GlobalOceansSeas',dtype('a25'),('GlobalOceansSeas'))
	vfoni = ncfile.createVariable('GlobalOceansSeas',dtype('float32').char,('latitude','longitude'))
if fainfo>=2:
	vhsmznames = ncfile.createVariable('names_HighSeasMarineZones',dtype('a25'),('HighSeasMarineZones'))
	vhsmz = ncfile.createVariable('HighSeasMarineZones',dtype('float32').char,('latitude','longitude'))
if fainfo>=3:
	vofmznames = ncfile.createVariable('names_OffshoreMarineZones',dtype('a25'),('OffshoreMarineZones'))
	vofmzids = ncfile.createVariable('id_OffshoreMarineZones',dtype('a25'),('OffshoreMarineZones'))
	vofmz = ncfile.createVariable('OffshoreMarineZones',dtype('float32').char,('latitude','longitude'))

# main fields
vdfc = ncfile.createVariable('distcoast',dtype('float32').char,('latitude','longitude'))
vib = ncfile.createVariable('depth',dtype('float32').char,('latitude','longitude'))
vmask = ncfile.createVariable('mask',dtype('float32').char,('latitude','longitude'))

# Assign units attributes
vdfc.units = 'km'
vib.units = 'm'
lats.units = 'degrees_north'
lons.units = 'degrees_east'
# write data to vars.
lats[:] = lat[:]; lons[:] = lon[:]
vdfc[:,:]=idfc[:,:]
vib[:,:]=ib[:,:] 
vmask[:,:]=mask[:,:]
if fainfo>=1:
	vocnames[:] = ocnames[:]
	vfoni[:,:]=foni[:,:]
if fainfo>=2:
	vhsmznames[:] = hsmznames[:]
	vhsmz[:,:]=hsmz[:,:]
if fainfo>=3:
	vofmznames[:] = ofmznames[:]
	vofmzids[:] = ofmzids[:]
	vofmz[:,:]=ofmz[:,:]
	
# close the file
ncfile.close()
print('netcdf ok')


#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
modelBuoy_collocation.py

VERSION AND LAST UPDATE:
 v1.0  05/11/2022
 v1.1  05/18/2022

PURPOSE:
 Collocation/pairing ww3 point output results with wave buoys.
 Matchups of ww3 results and buoy data are generated, for the same
  points (lat/lon) and time.

USAGE:
 This code is designed for ww3 hindcast or general simulations, not 
  forecast with consecutive cycles (overlapped time) or ensemble forecasts.
 Multiple files can be entered and appended, creating a continuous 
  time array. Enter a list at ww3list.txt
 WW3 netcdf results for point output tables (tab) is utilized.
 It uses two public buoy databases, NDBC and Copernicus,
  which (at least one) must have been previously downloaded. See
  get_buoydata_copernicus.sh and retrieve_ndbc_nc.py
 Edit ndbcp and copernp to set paths.
 Users should confirm the buoys' names at the "f=nc.Dataset" lines below.
 Python code can be run directly, without input arguments.
 Additionally, users and enter two extra arguments, gridIndo and CycloneMap,
  generated by prepGridMask.py and procyclmap.py, where the information
  for the buoy's position (nearest grid point) will be extracted and
  included in the output netcdf file.

OUTPUT:
 netcdf file ww3buoy_collocation_*.nc containing the matchups of buoy 
  and ww3 data, for the stations (lat/lon) where both data sources 
  are available.

DEPENDENCIES:
 See dependencies.py and the imports below.
 ww3 table results in netcdf format (list of files ww3list.txt)
 NDBC buoy data (see retrieve_ndbc_nc.py)
 Copernicus buoy data (see get_buoydata_copernicus.sh)

AUTHOR and DATE:
 05/11/2022: Ricardo M. Campos, first version.
 05/18/2022: Ricardo M. Campos, inclusion of gridInfo mask information,
  with water depth, distance to coast, ocean names, forecast areas, and
  cyclone information.

PERSON OF CONTACT:
 Ricardo M Campos: ricardo.campos@noaa.gov

"""

import numpy as np
from matplotlib.mlab import *
from pylab import *
import xarray as xr
import netCDF4 as nc
import time
from time import strptime
from calendar import timegm
import warnings; warnings.filterwarnings("ignore")
# netcdf format
fnetcdf="NETCDF4"

# Paths
# NDBC buoys
# ndbcp="/data/buoys/NDBC/wparam"
ndbcp="/work/noaa/marine/ricardo.campos/data/buoys/NDBC/ncformat/wparam"
# Copernicus buoys
# copernp="/data/buoys/Copernicus/wtimeseries"
copernp="/work/noaa/marine/ricardo.campos/data/buoys/Copernicus/wtimeseries"
# import os; os.system("ls /modelpath/*tab.nc > ww3list.txt &")
wlist=np.loadtxt('ww3list.txt',dtype=str)
if size(wlist)==1:
	wlist=[wlist]

# Options of including grid and cyclone information
gridinfo=np.int(0); cyclonemap=np.int(0)
if len(sys.argv) >= 2 :
	gridinfo=np.str(sys.argv[1])
if len(sys.argv) >= 3:
	cyclonemap=np.str(sys.argv[2])
if len(sys.argv) > 3:
	sys.exit(' Too many inputs')

# READ DATA
print(" ")
if gridinfo!=0:
	f=nc.Dataset(gridinfo)
	mlat=np.array(f.variables['latitude'][:]); mlon=np.array(f.variables['longitude'][:])
	mask=f.variables['mask'][:,:]; distcoast=f.variables['distcoast'][:,:]; depth=f.variables['depth'][:,:]
	oni=f.variables['GlobalOceansSeas'][:,:]; hsmz=f.variables['HighSeasMarineZones'][:,:]
	ocnames=f.variables['names_GlobalOceansSeas'][:]; hsmznames=f.variables['names_HighSeasMarineZones'][:] 
	f.close(); del f
	print(" GridInfo Ok. "+gridinfo)

	if cyclonemap!=0:
		fcy=nc.MFDataset(cyclonemap, aggdim='time')
		clat=np.array(fcy.variables['lat'][:]); clon=np.array(fcy.variables['lon'][:])
		cmap=fcy.variables['cmap']; ctime=fcy.variables['time'][:]
		cinfo=np.str(fcy.info); cinfo=np.array(np.str(cinfo).split(':')[1].split(';'))
		if np.array_equal(clat,mlat)==True & np.array_equal(clon,mlon)==True: 
			print(" CycloneMap Ok. "+cyclonemap)
		else:
			sys.exit(' Error: Cyclone grid and Mask grid are different.')

# Model
for t in range(0,size(wlist)):
	try:
		f=nc.Dataset(np.str(wlist[t]))
	except:
		print(" Cannot open "+wlist[t])
	else:
		# list of station/buoy names
		if t==0:
			auxstationname=f.variables['station_name'][:,:]; stname=[]
			for i in range(0,auxstationname.shape[0]):
				stname=np.append(stname,"".join(np.array(auxstationname[i,:]).astype('str')))

		ahs = np.array(f.variables['hs'][:,:]).T
		atm = np.array(f.variables['tr'][:,:]).T
		adm = np.array(f.variables['th1m'][:,:]).T
		at = np.array(f.variables['time'][:]*24*3600 + timegm( strptime(np.str(f.variables['time'].units).split(' ')[2][0:4]+'01010000', '%Y%m%d%H%M') )).astype('double')
		f.close(); del f
		if t==0:
			mhs=np.copy(ahs)
			mtm=np.copy(atm)
			mdm=np.copy(adm)
			mtime=np.copy(at)
		else:
			mhs=np.append(mhs,ahs,axis=1)
			mtm=np.append(mtm,atm,axis=1)
			mdm=np.append(mdm,adm,axis=1)
			mtime=np.append(mtime,at)

		del ahs,atm,adm,at

print(" Read WW3 data OK. Start building the matchups model/buoy ...")

# Buoys
bhs=np.zeros((size(stname),size(mtime)),'f')*np.nan
btm=np.zeros((size(stname),size(mtime)),'f')*np.nan
bdm=np.zeros((size(stname),size(mtime)),'f')*np.nan
lat=np.zeros(size(stname),'f')*np.nan; lon=np.zeros(size(stname),'f')*np.nan
# help reading NDBC buoys, divided by year
yrange=np.array(np.arange(time.gmtime(mtime.min())[0],time.gmtime(mtime.min())[0]+1,1)).astype('int')
# loop buoys
for b in range(0,size(stname)):

	ahs=[]
	try:

		ahs=[];atm=[];adm=[];atime=[]
		for y in yrange:

			f=nc.Dataset(ndbcp+"/"+stname[b]+"h"+repr(y)+".nc")
			ahs = np.append(ahs,f.variables['wave_height'][:,0,0])
			atm = np.append(atm,f.variables['average_wpd'][:,0,0])
			adm = np.append(adm,f.variables['mean_wave_dir'][:,0,0])
			atime = np.append(atime,np.array(f.variables['time'][:]).astype('double'))
			lat[b] = f.variables['latitude'][:]; lon[b] = f.variables['longitude'][:]
			f.close(); del f

	except:
		try:
			f=nc.Dataset(copernp+"/GL_TS_MO_"+stname[b]+".nc")
			ahs = np.nanmean(f.variables['VHM0'][:,:],axis=1)
			atm = np.nanmean(f.variables['VTM02'][:,:],axis=1)
			adm = np.nanmean(f.variables['VMDR'][:,:],axis=1)
			atime = np.array(f.variables['TIME'][:]*24*3600 + timegm( strptime('195001010000', '%Y%m%d%H%M') )).astype('double')
			lat[b] = np.nanmean(f.variables['LATITUDE'][:]); lon[b] = np.nanmean(f.variables['LONGITUDE'][:])
			f.close(); del f
		except:
			ahs=[]

	else:
		if size(ahs>0):
			c=0
			for t in range(0,size(mtime)):
				indt=np.where(np.abs(atime-mtime[t])<1800.)
				if size(indt)>0:
					if np.any(ahs[indt[0]].mask==False):
						bhs[b,t] = np.nanmean(ahs[indt[0]][ahs[indt[0]].mask==False])
						c=c+1
					if np.any(atm[indt[0]].mask==False):
						btm[b,t] = np.nanmean(atm[indt[0]][atm[indt[0]].mask==False])
					if np.any(adm[indt[0]].mask==False):
						bdm[b,t] = np.nanmean(adm[indt[0]][adm[indt[0]].mask==False])

					del indt

			# print("counted "+repr(c)+" at "+stname[b])

	print("done "+stname[b])
	del ahs

# Simple quality-control (range)
ind=np.where((bhs>30.)|(bhs<0.0))
if size(ind)>0:
	bhs[ind]=np.nan; del ind

ind=np.where((btm>40.)|(btm<0.0))
if size(ind)>0:
	btm[ind]=np.nan; del ind

ind=np.where((bdm>360.)|(bdm<-180.))
if size(ind)>0:
	bdm[ind]=np.nan; del ind

ind=np.where((mhs>30.)|(mhs<0.0))
if size(ind)>0:
	mhs[ind]=np.nan; del ind

ind=np.where((mtm>40.)|(mtm<0.0))
if size(ind)>0:
	mtm[ind]=np.nan; del ind

ind=np.where((mdm>360.)|(mdm<-180.))
if size(ind)>0:
	mdm[ind]=np.nan; del ind

# Clean data. Select matchups only when model and buoy are available.
ind=np.where( (np.isnan(lat)==False) & (np.isnan(lon)==False) & (np.isnan(np.nanmean(mhs,axis=1))==False) & (np.isnan(np.nanmean(bhs,axis=1))==False) )
if size(ind)>0:
	stname=np.array(stname[ind[0]])
	lat=np.array(lat[ind[0]])
	lon=np.array(lon[ind[0]])
	mhs=np.array(mhs[ind[0],:])
	mtm=np.array(mtm[ind[0],:])
	mdm=np.array(mdm[ind[0],:])
	bhs=np.array(bhs[ind[0],:])
	btm=np.array(btm[ind[0],:])
	bdm=np.array(bdm[ind[0],:])
else:
	sys.exit(' Error: No matchups Model/Buoy available.')

print(" Matchups model/buoy complete. Total of "+repr(size(ind))+" points avaliable."); del ind

# Processing grid and/or cyclone information
if gridinfo!=0:
	alon=np.copy(lon); alon[alon<0]=alon[alon<0]+360.
	indgplat=[]; indgplon=[]
	for i in range(0,lat.shape[0]):
		# indexes nearest point.
		indgplat = np.append(indgplat,np.where( abs(mlat-lat[i])==abs(mlat-lat[i]).min() )[0][0])
		indgplon = np.append(indgplon,np.where( abs(mlon-alon[i])==abs(mlon-alon[i]).min() )[0][0])

	indgplat=np.array(indgplat).astype('int'); indgplon=np.array(indgplon).astype('int')
	pdistcoast=np.zeros(lat.shape[0],'f')*np.nan
	pdepth=np.zeros(lat.shape[0],'f')*np.nan
	poni=np.zeros(lat.shape[0],'f')*np.nan
	phsmz=np.zeros(lat.shape[0],'f')*np.nan
	for i in range(0,lat.shape[0]):
		pdistcoast[i]=distcoast[indgplat[i],indgplon[i]]
		pdepth[i]=depth[indgplat[i],indgplon[i]]
		poni[i]=oni[indgplat[i],indgplon[i]]
		phsmz[i]=hsmz[indgplat[i],indgplon[i]]

	print(" Included Grid Information.")

	# Excluding shallow water points too close to the coast (mask information not accurate)
	ind=np.where( (np.isnan(pdistcoast)==False) & (np.isnan(pdepth)==False) )
	if size(ind)>0:
		stname=np.array(stname[ind[0]])
		lat=np.array(lat[ind[0]])
		lon=np.array(lon[ind[0]])
		mhs=np.array(mhs[ind[0],:])
		mtm=np.array(mtm[ind[0],:])
		mdm=np.array(mdm[ind[0],:])
		bhs=np.array(bhs[ind[0],:])
		btm=np.array(btm[ind[0],:])
		bdm=np.array(bdm[ind[0],:])
		pdistcoast=np.array(pdistcoast[ind[0]])
		pdepth=np.array(pdepth[ind[0]])
		poni=np.array(poni[ind[0]])
		phsmz=np.array(phsmz[ind[0]])
	else:
		sys.exit(' Error: No matchups Model/Buoy available after using grid mask.')

	del ind

	if cyclonemap!=0:
		fcmap=np.zeros((lat.shape[0],mtime.shape[0]),'f')*np.nan
		for t in range(0,size(mtime)):
			# search for cyclone time index and cyclone map
			indt=np.where(np.abs(ctime-mtime[t])<5400.)
			if size(indt)>0:
				for i in range(0,lat.shape[0]):
					fcmap[i,t] = np.array(cmap[indt[0][0],indgplat[i],indgplon[i]])

				del indt
			else:
				print(' Warning: No cyclone information for this time step: '+repr(t))

			print(' Done cyclone analysis at time-step: '+repr(t))

		ind=np.where(fcmap<0)
		if size(ind)>0:
			fcmap[ind]=np.nan

		print(" Included Cyclone Information.")

# Save netcdf output file 
lon[lon>180.]=lon[lon>180.]-360.
initime=np.str(time.gmtime(mtime.min())[0])+np.str(time.gmtime(mtime.min())[1]).zfill(2)+np.str(time.gmtime(mtime.min())[2]).zfill(2)+np.str(time.gmtime(mtime.min())[3]).zfill(2)
fintime=np.str(time.gmtime(mtime.max())[0])+np.str(time.gmtime(mtime.max())[1]).zfill(2)+np.str(time.gmtime(mtime.max())[2]).zfill(2)+np.str(time.gmtime(mtime.max())[3]).zfill(2)
ncfile = nc.Dataset('WW3.Buoy_'+initime+'to'+fintime+'.nc', "w", format=fnetcdf)
ncfile.history="Matchups of WAVEWATCHIII point output (table) and NDBC and Copernicus Buoys. Total of "+repr(bhs[bhs>0.].shape[0])+" observations or pairs model/observation."
# create  dimensions. 2 Dimensions
ncfile.createDimension('buoypoints', bhs.shape[0] )
ncfile.createDimension('time', bhs.shape[1] )
if gridinfo!=0:
	ncfile.createDimension('GlobalOceansSeas', ocnames.shape[0] )
	ncfile.createDimension('HighSeasMarineZones', hsmznames.shape[0] )
if cyclonemap!=0:
	ncfile.createDimension('cycloneinfo', cinfo.shape[0] )
	vcinfo = ncfile.createVariable('cycloneinfo',dtype('a25'),('cycloneinfo'))

# create variables.
vt = ncfile.createVariable('time',np.dtype('float64').char,('time'))
vstname = ncfile.createVariable('buoyID',dtype('a25'),('buoypoints'))
vlat = ncfile.createVariable('latitude',np.dtype('float32').char,('buoypoints'))
vlon = ncfile.createVariable('longitude',np.dtype('float32').char,('buoypoints'))
#
vmhs = ncfile.createVariable('model_hs',np.dtype('float32').char,('buoypoints','time'))
vmtm = ncfile.createVariable('model_tm',np.dtype('float32').char,('buoypoints','time'))
vmdm = ncfile.createVariable('model_dm',np.dtype('float32').char,('buoypoints','time'))
vbhs = ncfile.createVariable('obs_hs',np.dtype('float32').char,('buoypoints','time'))
vbtm = ncfile.createVariable('obs_tm',np.dtype('float32').char,('buoypoints','time'))
vbdm = ncfile.createVariable('obs_dm',np.dtype('float32').char,('buoypoints','time'))
if gridinfo!=0:
	vpdistcoast = ncfile.createVariable('distcoast',np.dtype('float32').char,('buoypoints')) 
	vpdepth = ncfile.createVariable('depth',np.dtype('float32').char,('buoypoints')) 
	vponi = ncfile.createVariable('GlobalOceansSeas',np.dtype('float32').char,('buoypoints'))
	vocnames = ncfile.createVariable('names_GlobalOceansSeas',dtype('a25'),('GlobalOceansSeas'))
	vphsmz = ncfile.createVariable('HighSeasMarineZones',np.dtype('float32').char,('buoypoints')) 
	vhsmznames = ncfile.createVariable('names_HighSeasMarineZones',dtype('a25'),('HighSeasMarineZones'))
if cyclonemap!=0:
	vcmap = ncfile.createVariable('cyclone',np.dtype('float32').char,('buoypoints','time'))

# Assign units
vlat.units = 'degrees_north' ; vlon.units = 'degrees_east'
vt.units = 'seconds since 1970-01-01T00:00:00+00:00'
vmhs.units='m'; vbhs.units='m'
vmtm.units='s'; vbtm.units='s'
vmdm.units='degrees'; vbdm.units='degrees'
if gridinfo!=0:
	vpdepth.units='m'; vpdistcoast.units='km'

# Allocate Data
vt[:]=mtime[:]; vstname[:]=stname[:]
vlat[:] = lat[:]; vlon[:] = lon[:]
vmhs[:,:]=mhs[:,:]
vmtm[:,:]=mtm[:,:]
vmdm[:,:]=mdm[:,:]
vbhs[:,:]=bhs[:,:]
vbtm[:,:]=btm[:,:]
vbdm[:,:]=bdm[:,:]
if gridinfo!=0:
	vpdistcoast[:]=pdistcoast[:]
	vpdepth[:]=pdepth[:]
	vponi[:]=poni[:]; vocnames[:] = ocnames[:]
	vphsmz[:]=phsmz[:]; vhsmznames[:] = hsmznames[:]
if cyclonemap!=0:
	vcmap[:,:]=fcmap[:,:]; vcinfo[:] = cinfo[:]
#
ncfile.close()
print(' ')
print('Done. Netcdf ok. New file saved: WW3.Buoy_'+initime+'to'+fintime+'.nc')


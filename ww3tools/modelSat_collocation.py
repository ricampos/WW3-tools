#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
modelSat_collocation.py

VERSION AND LAST UPDATE:
 v1.0  05/10/2022
 v1.1  06/30/2022
 v1.2  07/20/2022
 v1.3  02/13/2023

PURPOSE:
 Collocation/pairing ww3 field output results with altimeters.
 Matchups of ww3 results and satellite data are generated, for the same
  points (lat/lon) and time.
 Additional information is included as well, such as water depth,
  distance to the nearest coast, ocean names, forecast zones, satellite
  IDs, and cyclone information.
 This code is designed for ww3 hindcasts or forecast with 
  consecutive cycles (overlapped time). The ww3 file(s) are not entered
  directly, but it is informed through a list, ww3list.txt (or any other
  name), that is read as an argument. Multiple file names can be writen 
  in the list, ww3 results will be appended, depending on the data 
  structure selected (hindcast or forecast). The default is hindcast, so 
  arrays are directly appended in time. By entering a second argument 
  (any integer greated than zero), the program assumes it is a forecast data 
  structure, i.e., the list contains consecutive cycles (each file is 
  one cycle). In this case, another output variable is included in the
  final netcdf file, 'cycle', with the time of the nowcast/cycle. By
  calculating time-cycle, you can obtain the forecast lead time in seconds.
 This code reads satellite data previously gridded (gridSatGlobal_Altimeter.py)
  for each satellite mission. A list with one or multiple satellite 
  missions must be entered, e.g. satlist.txt (text file) including netcdf
  files of gridded altimeter data. 

USAGE:
 Four arguments must be entered by the user:
 (1) WAVEWATCHIII field outputs (netcdf or grib2) in a list with all
   files (e.g. ww3list.txt).
 (2) Altimeter Gridded netcdf files (generated by gridSatGlobal_Altimeter.py)
   also written into a list (e.g. satlist.txt). Each line contains
   one satellite mission.
 (3) GridInfo netcdf file (generated by prepGridMask.py).
 (4) Cyclone map netcdf file (generated by procyclmap.py). In case of multiple
   years in separated files, you can enter CycloneMap_*.nc and all the
   files/years in that directory will be properly read.
 (5) Optional information to define hindcast or forecast time array structure,
   where 0 (zero) is for hindcast and any value above it will interpreted as
   forecast. 
 It is important to mention that the grid points of WAVEWATCHIII results
  must be the same as GridInfo, Cyclone map, and gridded satellite data,
  so it is recommended to run the following codes to prepare that:
  prepGridMask.py, procyclmap.py, and gridSatGlobal_Altimeter.py.
 Examples (from linux terminal command line):
  python3 modelSat_collocation.py "ww3list_201901_c00.txt" "satlist.txt" "gridInfo_GEFS.nc" "CycloneMap_2019.nc" 1
  nohup python3 modelSat_collocation.py "ww3list_201901_c00.txt" "satlist.txt" "gridInfo_GEFS.nc" "CycloneMap_2019.nc" 1 >> nohup_modelSat_collocation.out 2>&1 &

OUTPUT:
 netcdf file WW3.Altimeter_*.nc containing the matchups of WAVEWATCHIII
  and altimeter data for the same positions, plus the water depth, 
  distance to the nearest coast, ocean names, forecast zones, satellite
  names, and cyclone information.
 for the example above, the program will select the tag 201901_c00 to
  name the output file as WW3.Altimeter_201901_c00_2019010103to2019021603.nc
  containing WW3.Altimeter, the tag to identify the simulation, and start
  and final date (to confirm the time intervall expected is correct).

DEPENDENCIES:
 See setup.py and the imports below.
 GridInfo netcdf file (generated by prepGridMask.py)
 Cyclone map netcdf file (generated by procyclmap.py)
 Altimeter Gridded netcdf files (generated by gridSatGlobal_Altimeter.py)
 WAVEWATCHIII field outputs (netcdf or grib2)

AUTHOR and DATE:
 05/10/2022: Ricardo M. Campos, first version.
 06/30/2022: Ricardo M. Campos, including option of using a forecast
  data structure, where each file name on the ww3list is taken as a
  forecast cycle.
 07/20/2022: Ricardo M. Campos, fix longitude standards among data.
 02/13/2023: Ricardo M. Campos, new management of array sizes to speed 
  up the process (1 month of GEFS reduced from 8+ hours to 2 hours).

PERSON OF CONTACT:
 Ricardo M Campos: ricardo.campos@noaa.gov

"""

import numpy as np
from matplotlib.mlab import *
from pylab import *
import xarray as xr
import netCDF4 as nc
import time
import timeit
from time import strptime
from calendar import timegm
import sys
import warnings; warnings.filterwarnings("ignore")
# netcdf format
fnetcdf="NETCDF4"
# start time
start = timeit.default_timer()

# Inputs
forecastds=0
if len(sys.argv) < 5 :
	sys.exit(' At least 4 arguments (list of ww3 files; list of satellite [gridded] files; gridInfo; and cyclone map) must be entered.')
if len(sys.argv) >= 5 :
	# list of WAVEWATCHIII files
	# import os; os.system("ls -d $PWD/*.nc > ww3list.txt &")
	wlist=np.loadtxt(np.str(sys.argv[1]),dtype=str)
	ftag=np.str(sys.argv[1]).split('list')[1].split('.txt')[0]
	print(' Reading ww3 list '+np.str(sys.argv[1]))
	print(' Tag '+ftag)
	# list of gridded satellite files
	# ls -d $PWD/AltimeterGridded_*.nc > satlist.txt
	slist=np.loadtxt(np.str(sys.argv[2]),dtype=str)
	# grid information
	gridinfo=np.str(sys.argv[3])
	print(' Using gridInfo '+gridinfo)
	# cyclone map
	cyclonemap=np.str(sys.argv[4])
	print(' Using cyclone map '+cyclonemap)
if len(sys.argv) >= 6:
	forecastds=np.int(sys.argv[5])
	if forecastds>0:
		print(' Forecast-type data structure')
if len(sys.argv) > 7:
	sys.exit(' Too many inputs')


# READ mask Grid Info
f=nc.Dataset(gridinfo)
mlat=np.array(f.variables['latitude'][:]); mlon=np.array(f.variables['longitude'][:])
mask=f.variables['mask'][:,:]; distcoast=f.variables['distcoast'][:,:]; depth=f.variables['depth'][:,:]
oni=f.variables['GlobalOceansSeas'][:,:]; hsmz=f.variables['HighSeasMarineZones'][:,:]
ocnames=f.variables['names_GlobalOceansSeas'][:]; hsmznames=f.variables['names_HighSeasMarineZones'][:] 
f.close(); del f
print(" "); print(" GridInfo Ok.")
# -------------

# READ Cyclone map
if "*" in np.str(cyclonemap).split('/')[-1]:
	fcy=nc.MFDataset(cyclonemap, aggdim='time')
else:
	fcy=nc.Dataset(cyclonemap)

clat=np.array(fcy.variables['lat'][:]); clon=np.array(fcy.variables['lon'][:])
cmap=fcy.variables['cmap']; ctime=fcy.variables['time'][:]
cinfo=np.str(fcy.info); cinfo=np.array(np.str(cinfo).split(':')[1].split(';'))

if np.array_equal(clat,mlat)==True & np.array_equal(clon,mlon)==True: 
	print(" CycloneMap Ok.")
	ind=np.where(mlon>180.)
	if size(ind)>0:
		mlon[mlon>180.] = mlon[mlon>180.]-360.
		clon[clon>180.] = clon[clon>180.]-360.
		del ind
else:
	sys.exit(' Error: Cyclone grid and Mask grid are different.')

# -------------
# Select initial and final model times (to speed up satellite data reading)
auxmtime=[];c=0
for i in [0,1,-1]:
	try:
		if np.str(wlist[i]).split('/')[-1].split('.')[-1]=='nc':
			f = nc.Dataset(np.str(wlist[i]))
			if c==0:
				if np.str(f.variables['time'].units).split(' ')[0] == 'seconds':
					tincr=1
				elif np.str(f.variables['time'].units).split(' ')[0] == 'hours':
					tincr=3600
				elif np.str(f.variables['time'].units).split(' ')[0] == 'days':
					tincr=24*3600

				wtime = np.array(f.variables['time'][0]*tincr + timegm( strptime(np.str(f.variables['time'].units).split(' ')[2][0:4]+'01010000', '%Y%m%d%H%M') )).astype('double')
				wtimef = np.array(f.variables['time'][-1]*tincr + timegm( strptime(np.str(f.variables['time'].units).split(' ')[2][0:4]+'01010000', '%Y%m%d%H%M') )).astype('double')		
				nrt=np.abs(wtimef-wtime)
				del wtimef
			elif c==2:
				wtime = np.array(f.variables['time'][-1]*tincr + timegm( strptime(np.str(f.variables['time'].units).split(' ')[2][0:4]+'01010000', '%Y%m%d%H%M') )).astype('double')
			else:
				wtime = np.array(f.variables['time'][0]*tincr + timegm( strptime(np.str(f.variables['time'].units).split(' ')[2][0:4]+'01010000', '%Y%m%d%H%M') )).astype('double')

			f.close(); del f

		elif (np.str(wlist[i]).split('/')[-1].split('.')[-1]=='grib2') or (np.str(wlist[i]).split('/')[-1].split('.')[-1]=='grb2'):
			f = xr.open_dataset(np.str(wlist[i]), engine='cfgrib')
			if c==0:
				wtime = np.double(timegm(strptime(np.str(f.time.values)[0:-10], '%Y-%m-%dT%H:%M:%S')))
				wtimef = np.double(timegm(strptime(np.str(f.time.values + f.step.values[-1])[0:-10], '%Y-%m-%dT%H:%M:%S')))
				nrt=np.abs(wtimef-wtime)
				del wtimef
			elif c==2:
				wtime = np.double(timegm(strptime(np.str(f.time.values + f.step.values[-1])[0:-10], '%Y-%m-%dT%H:%M:%S')))			
			else:
				wtime = np.double(timegm(strptime(np.str(f.time.values)[0:-10], '%Y-%m-%dT%H:%M:%S')))

			f.close(); del f

	except:
		print(" Error: Cannot open "+np.str(wlist[i]))
	else:
		auxmtime=np.append(auxmtime,wtime); del wtime
		c=c+1

del c
if forecastds>0:
	lforecastds=np.int(np.ceil(nrt/(auxmtime[1]-auxmtime[0]))+1); del nrt
	if forecastds<lforecastds:
		print(" Forecastds updated to "+repr(lforecastds))
		forecastds=lforecastds

# READ list Gridded Satellites
if size(slist)==1:
	slist=[slist]

sdname=np.array(['JASON3','JASON2','CRYOSAT2','JASON1','HY2','SARAL','SENTINEL3A','ENVISAT','ERS1','ERS2','GEOSAT','GFO','TOPEX','SENTINEL3B'])
slat=[];slon=[];swnd=[];shs=[];stime=[];sid=[]
for i in range(0,size(slist)):
	try:
		f=nc.Dataset(slist[i])
		astime=np.array(f.variables['stime'][:])
	except:
		print(" Error: Cannot open "+np.str(slist[i]))
	else:
		print('ok')
		if (np.nanmin(astime)>=auxmtime.max()) or (np.nanmax(astime)<auxmtime.min()):
			print('  -   satellite '+slist[i]+' time range outside the model time interval.')
		else:
			slat=np.append(slat,np.array(f.variables['latitude'][:]))
			slon=np.append(slon,np.array(f.variables['longitude'][:]))

			if 'wndcal' in f.variables.keys():	
				swnd=np.append(swnd,np.array(f.variables['wndcal'][:]))
			elif 'wnd' in f.variables.keys():
				swnd=np.append(swnd,np.array(f.variables['wnd'][:]))
			else:
				sys.exit(' Error: No Wind data in: '+slist[i])

			if 'hskcal' in f.variables.keys():
				shs=np.append(shs,np.array(f.variables['hskcal'][:]))
			elif 'hskucal':
				shs=np.append(shs,np.array(f.variables['hskucal'][:]))
			elif 'hs':
				shs=np.append(shs,np.array(f.variables['hs'][:]))
			else:
				sys.exit(' Error: No Hs data in: '+slist[i])

			stime=np.append(stime,astime)
			if np.str(slist[i]).split('_')[1].split('.')[0] in sdname:
				sid=np.append(sid,np.zeros(stime.shape[0],'int')+np.int(np.where(np.str(slist[i]).split('_')[1].split('.')[0] == sdname)[0][0]))
			else:
				sys.exit(' Error: Problem identifying satellite mission from file name: '+slist[i])

			print('  - ok '+slist[i])

		del astime
		f.close(); del f

indes=np.where( (stime>=(auxmtime.min()-(3.*3600.))) & (stime<=(auxmtime.max()+(3.*3600.))) )
if size(indes)>0:
	stime=stime[indes[0]]; sid=sid[indes[0]]
	shs=shs[indes[0]]; swnd=swnd[indes[0]]
	slat=slat[indes[0]]; slon=slon[indes[0]]
else:
	sys.exit(' Insufficient amount of matchups model/satellite.')

del indes,auxmtime
if size( np.where(slon>180.) )>0:
	slon[slon>180.] = slon[slon>180.]-360.

print(" Satellite Data Ok.")

# READ list WW3 files
if size(wlist)==1:
	wlist=[wlist]

print(" Start building the matchups model/satellite ...")
fwhs=np.zeros(stime.shape[0]*(forecastds+1),'f')*np.nan; fwwnd=np.zeros(stime.shape[0]*(forecastds+1),'f')*np.nan
fshs=np.zeros(stime.shape[0]*(forecastds+1),'f')*np.nan; fswnd=np.zeros(stime.shape[0]*(forecastds+1),'f')*np.nan; fsid=np.zeros(stime.shape[0]*(forecastds+1),'f')*np.nan
flat=np.zeros(stime.shape[0]*(forecastds+1),'f')*np.nan; flon=np.zeros(stime.shape[0]*(forecastds+1),'f')*np.nan; fcmap=np.zeros(stime.shape[0]*(forecastds+1),'f')*np.nan
ftime=np.zeros(stime.shape[0]*(forecastds+1),'d')*np.nan; fmonth=np.zeros(stime.shape[0]*(forecastds+1),'i')*np.nan
fdistcoast=np.zeros(stime.shape[0]*(forecastds+1),'f')*np.nan; fdepth=np.zeros(stime.shape[0]*(forecastds+1),'f')*np.nan; foni=np.zeros(stime.shape[0]*(forecastds+1),'i')*np.nan; fhsmz=np.zeros(stime.shape[0]*(forecastds+1),'i')*np.nan
if forecastds>0:
	fcycle=np.zeros(stime.shape[0]*(forecastds+1),'d')*np.nan

c=0
for i in range(0,size(wlist)):
	try:
		if np.str(wlist[i]).split('/')[-1].split('.')[-1]=='nc':
			# netcdf format
			fformat=1
			f=nc.Dataset(np.str(wlist[i]))
			wlon=np.array(f.variables['longitude'][:]); wlat=np.array(f.variables['latitude'][:])
			wtime = np.array(f.variables['time'][:]*24*3600 + timegm( strptime(np.str(f.variables['time'].units).split(' ')[2][0:4]+'01010000', '%Y%m%d%H%M') )).astype('double')

		elif (np.str(wlist[i]).split('/')[-1].split('.')[-1]=='grib2') or (np.str(wlist[i]).split('/')[-1].split('.')[-1]=='grb2'):
			# grib2 format
			fformat=2
			f = xr.open_dataset(np.str(wlist[i]), engine='cfgrib')
			wlon=np.array(f['longitude'].values); wlat=np.array(f['latitude'].values)
			if wlat[-1]<wlat[0]:
				wlat=np.array(np.flipud(wlat)); iwlat=1
			else:
				iwlat=0

			auxtime = np.array(f.time.values + f.step.values )
			wtime=np.zeros((auxtime.shape[0]),'d')*np.nan
			for j in range(0,wtime.shape[0]):
				wtime[j]=np.double(timegm(strptime(np.str(auxtime[j])[0:-10], '%Y-%m-%dT%H:%M:%S')))

			del auxtime

	except:
		print(" Error: Cannot open "+np.str(wlist[i]))
	else:
		print(" Ok read "+np.str(wlist[i])+" starting matchups ...")

		if size( np.where(wlon>180.) )>0:
			wlon[wlon>180.] = wlon[wlon>180.]-360.

		if np.array_equal(wlat,mlat)==False | np.array_equal(wlon,mlon)==False: 
			sys.exit(' Error: Cyclone grid and Mask grid are different.')

		# Coincident/Matching Time (model/satellite)
		aux=np.intersect1d(wtime, stime, assume_unique=False, return_indices=True)
		indtauxw=np.array(aux[1]).astype('int'); del aux
		# loop through ww3 time steps
		for t in range(0,size(indtauxw)):

			# search for cyclone time index and cyclone map
			indc=np.where(np.abs(ctime-wtime[indtauxw[t]])<5400.)
			if size(indc)>0:
				acmap=np.array(cmap[indc[0][0],:,:])
				del indc
			else:
				acmap=np.zeros((mlat.shape[0],mlon.shape[0]),'f')*np.nan
				print(' Warning: No cyclone information for this time step: '+repr(t))

			inds=np.where(np.abs(stime-wtime[indtauxw[t]])<1800.)
			if size(inds)>0:
				if fformat==1:
					# WW3 Significant Wave Height and Wind Speed
					try:
						whs = np.array(f.variables['hs'][indtauxw[t],:,:])
						wwnd = np.array(np.sqrt( f.variables['uwnd'][indtauxw[t],:,:]**2 + f.variables['vwnd'][indtauxw[t],:,:]**2 ))
					except:
						whs = np.array(f.variables['HTSGW_surface'][indtauxw[t],:,:])
						wwnd = np.array(np.sqrt( f.variables['UGRD_surface'][indtauxw[t],:,:]**2 + f.variables['VGRD_surface'][indtauxw[t],:,:]**2 ))		

				elif fformat==2:
					# WW3 Significant Wave Height and Wind Speed
					if iwlat==1:
						whs = np.array(np.flipud(f['swh'].values[indtauxw[t],:,:]))
						wwnd = np.array(np.sqrt( np.flipud(f['u'].values[indtauxw[t],:,:])**2 + np.flipud(f['v'].values[indtauxw[t],:,:])**2 ))
					else:
						whs = np.array(f['swh'].values[indtauxw[t],:,:])
						wwnd = np.array(np.sqrt( f['u'].values[indtauxw[t],:,:]**2 + f['v'].values[indtauxw[t],:,:]**2 ))

				# loop through the gridded satellite data for that selected time matching WW3 time.
				for j in range(0,size(inds)):
					# indexes and lat/lon for the WW3 grid point
					indgplat = np.where( abs(mlat-slat[inds[0][j]])==abs(mlat-slat[inds[0][j]]).min() )[0][0]
					indgplon = np.where( abs(mlon-slon[inds[0][j]])==abs(mlon-slon[inds[0][j]]).min() )[0][0]
					if (mask[indgplat,indgplon]==1) & (distcoast[indgplat,indgplon]>0.) & (depth[indgplat,indgplon]>0.):
						# model
						fwhs[c]=whs[indgplat,indgplon]; fwwnd[c]=wwnd[indgplat,indgplon]
						# satellite
						fshs[c]=shs[inds[0][j]]; fswnd[c]=swnd[inds[0][j]]; fsid[c]=sid[inds[0][j]]
						# position
						flat[c]=mlat[indgplat]; flon[c]=mlon[indgplon]
						# grid info
						fdistcoast[c]=distcoast[indgplat,indgplon]; fdepth[c]=depth[indgplat,indgplon]
						foni[c]=oni[indgplat,indgplon]; fhsmz[c]=hsmz[indgplat,indgplon]
						# cyclone info
						fcmap[c]=acmap[indgplat,indgplon]
						# time
						ftime[c]=np.double(wtime[indtauxw[t]])
						fmonth[c]=np.int(time.gmtime(wtime[indtauxw[t]])[1])
						if forecastds>0:
							fcycle[c]=np.double(np.nanmin(wtime))

						c=c+1

					del indgplat, indgplon

				del inds, acmap, whs, wwnd

			print(repr(t))

		f.close(); del f
		print(" Done "+np.str(wlist[i]))


fcy.close(); del fcy
print(' Data Collocation/Matchups Ok.')

# Quality Control
ind=np.where( (fwhs>0.0) & (fwhs<20.0) & (fwwnd>0.0) & (fwwnd<60.0) & (fshs>0.0) & (fshs<20.0) & (fswnd>0.0) & (fswnd<60.0) )
if size(ind)>0:
	print(' Total amount of matchups model/satellite: '+repr(size(ind)))
	fwhs=np.array(fwhs[ind[0]]); fwwnd=np.array(fwwnd[ind[0]])
	fshs=np.array(fshs[ind[0]]); fswnd=np.array(fswnd[ind[0]]); fsid=np.array(fsid[ind[0]]).astype('int')
	flat=np.array(flat[ind[0]]); flon=np.array(flon[ind[0]])
	ftime=np.array(ftime[ind[0]]).astype('double'); fmonth=np.array(fmonth[ind[0]]).astype('int')
	fdistcoast=np.array(fdistcoast[ind[0]]); fdepth=np.array(fdepth[ind[0]])
	foni=np.array(foni[ind[0]]).astype('int'); fhsmz=np.array(fhsmz[ind[0]]).astype('int'); fcmap=np.array(fcmap[ind[0]]).astype('int')
	if forecastds>0:
		fcycle=np.array(fcycle[ind[0]]).astype('double')

	initime=repr(time.gmtime(ftime.min())[0])+str(time.gmtime(ftime.min())[1]).zfill(2)+str(time.gmtime(ftime.min())[2]).zfill(2)+str(time.gmtime(ftime.min())[3]).zfill(2)
	fintime=repr(time.gmtime(ftime.max())[0])+str(time.gmtime(ftime.max())[1]).zfill(2)+str(time.gmtime(ftime.max())[2]).zfill(2)+str(time.gmtime(ftime.max())[3]).zfill(2)
	sdname=np.array(sdname).astype('O')
	# Save netcdf output file
	ncfile = nc.Dataset('WW3.Altimeter'+ftag+'_'+initime+'to'+fintime+'.nc', "w", format=fnetcdf)
	ncfile.history="Matchups of WAVEWATCHIII and AODN Altimeter data. Total of "+repr(size(ind))+" observations or pairs model/observation."
	# create  dimensions. 2 Dimensions
	ncfile.createDimension('index',ftime.shape[0])
	ncfile.createDimension('satellite', sdname.shape[0] )
	ncfile.createDimension('GlobalOceansSeas', ocnames.shape[0] )
	ncfile.createDimension('HighSeasMarineZones', hsmznames.shape[0] )
	ncfile.createDimension('cycloneinfo', cinfo.shape[0] )
	# create variables.
	vt = ncfile.createVariable('time',np.dtype('float64').char,('index'))
	vmonth = ncfile.createVariable('month',np.dtype('int16').char,('index'))	
	vlat = ncfile.createVariable('latitude',np.dtype('float32').char,('index'))
	vlon = ncfile.createVariable('longitude',np.dtype('float32').char,('index'))
	vdistcoast = ncfile.createVariable('distcoast',np.dtype('float32').char,('index'))
	vdepth = ncfile.createVariable('depth',np.dtype('float32').char,('index'))
	voni = ncfile.createVariable('GlobalOceansSeas',np.dtype('int16').char,('index'))
	vocnames = ncfile.createVariable('names_GlobalOceansSeas',dtype('a25'),('GlobalOceansSeas'))
	vhsmz = ncfile.createVariable('HighSeasMarineZones',np.dtype('int16').char,('index'))
	vhsmznames = ncfile.createVariable('names_HighSeasMarineZones',dtype('a25'),('HighSeasMarineZones'))
	vcmap = ncfile.createVariable('cyclone',np.dtype('int16').char,('index'))
	vcinfo = ncfile.createVariable('cycloneinfo',dtype('a25'),('cycloneinfo'))
	vsid = ncfile.createVariable('satelliteID',np.dtype('int16').char,('index'))
	vsdname = ncfile.createVariable('names_satellite',dtype('a25'),('satellite'))
	# results
	vwhs = ncfile.createVariable('model_hs',np.dtype('float32').char,('index'))
	vwwnd = ncfile.createVariable('model_wnd',np.dtype('float32').char,('index'))
	vshs = ncfile.createVariable('obs_hs',np.dtype('float32').char,('index'))
	vswnd = ncfile.createVariable('obs_wnd',np.dtype('float32').char,('index'))
	# Assign units
	vlat.units = 'degrees_north' ; vlon.units = 'degrees_east'
	vt.units = 'seconds since 1970-01-01T00:00:00+00:00'
	vwhs.units='m'; vshs.units='m'
	vwwnd.units='m/s'; vswnd.units='m/s'
	vdepth.units='m'; vdistcoast.units='km'
	if forecastds>0:
		vcycle = ncfile.createVariable('cycle',np.dtype('float64').char,('index'))
		vcycle.units = 'seconds since 1970-01-01T00:00:00+00:00'; vcycle[:]=fcycle[:]

	# Allocate Data
	vt[:]=ftime[:]; vmonth[:]=fmonth[:]
	vlat[:] = flat[:]; vlon[:] = flon[:]
	vdistcoast[:] = fdistcoast[:]; vdepth[:] = fdepth[:]
	voni[:] = foni[:]; vocnames[:] = ocnames[:]
	vhsmz[:] = fhsmz[:]; vhsmznames[:] = hsmznames[:]; vsdname[:] = sdname[:]
	vcmap[:] = fcmap[:]; vcinfo[:] = cinfo[:]; vsid[:] = fsid[:]
	vwhs[:] = fwhs[:]; vshs[:] = fshs[:]
	vwwnd[:] = fwwnd[:]; vswnd[:] = fswnd[:]
	#
	ncfile.close()
	print(' ')
	print('Done. Netcdf ok. New file saved: WW3.Altimeter'+ftag+'_'+initime+'to'+fintime+'.nc')

else:
	print(' Insufficient amount of matchups model/satellite to save output file.')

stop = timeit.default_timer()
print('Concluded in '+repr(int(round(stop - start,0)))+' seconds')


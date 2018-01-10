# Copyright (c) 2017, AGILE team
# Authors: Nicolo' Parmiggiani <nicolo.parmiggiani@gmail.com>,
#
# Any information contained in this software is property of the AGILE TEAM
# and is strictly private and confidential. All rights reserved.


import sys
import MySQLdb as mysql
from conf import get_conf
import pyfits
import numpy as np
from numpy import rec
from pyfits import Column
import os
from astropy.time import Time
from astropy.coordinates import SkyCoord


# create FITS with event in time window from observation
def write_fits(tstart,tstop,observationid,filename):

    tstart = float(tstart)
    tstop = float(tstop)

    #connect to database
    conf_dictionary = get_conf()

    host = conf_dictionary['host']
    username = conf_dictionary['username']
    password = conf_dictionary['password']
    port = conf_dictionary['port']
    databas_evt = conf_dictionary['evt-database']
    database_pipe = conf_dictionary['database']


    # get events list
    conn = mysql.connect(host,username,password,databas_evt)
    cursor = conn.cursor(mysql.cursors.DictCursor)

    cursor.execute("SELECT * FROM evt3 WHERE TIME_REAL > "+str(tstart)+" AND TIME_REAL < "+str(tstop)+" AND OBS_ID = "+str(observationid))

    events = cursor.fetchall()

    cursor.close()
    conn.close()

    #get observation info
    conn = mysql.connect(host,username,password,database_pipe)
    cursor = conn.cursor(mysql.cursors.DictCursor)

    #get observation info
    cursor.execute("SELECT * FROM observation_parameters WHERE observationid = "+str(observationid))

    observation_parameters = cursor.fetchone()

    cursor.close()
    conn.close()

    hdulist = pyfits.open('examples/base_empty.fits')

    primary_hdu = hdulist[0]

    events_hdu = hdulist[1]

    # CREATE EVENTS data table HDU

    c_e_1 = Column(name = 'EVENT_ID', format = '1J', bscale = 1, bzero = 2147483648, array=np.array([x['EVT_ID'] for x in events]))
    c_e_2 = Column(name = 'TIME',format = '1D', unit = 's', array=np.array([x['TIME'] for x in events]))
    c_e_3 = Column(name = 'RA',format = '1E', unit = 'deg', array=np.array([x['RA'] for x in events]))
    c_e_4 = Column(name = 'DEC', format = '1E', unit = 'deg', array=np.array([x['DEC'] for x in events]))
    c_e_5 = Column(name = 'ENERGY', format = '1E', unit = 'TeV', array=np.array([x['ENERGY'] for x in events]))
    c_e_6 = Column(name = 'DETX', format = '1E', unit = 'deg', array=np.array([x['DETX'] for x in events]))
    c_e_7 = Column( name = 'DETY', format = '1E', unit = 'deg', array=np.array([x['DETY'] for x in events]))
    c_e_8 = Column(name = 'MC_ID', format = '1J', array=np.array([x['MC_ID'] for x in events]))

    coldefs = pyfits.ColDefs([c_e_1, c_e_2,c_e_3,c_e_4,c_e_5,c_e_6,c_e_7,c_e_8])

    data_tbhdu = pyfits.BinTableHDU.from_columns(coldefs)
    data_tbhdu.header = hdulist[1].header


    #convert coordinate from galactic to celestial (icrs)
    obs_gal_coord = SkyCoord(observation_parameters['lon'],observation_parameters['lat'], unit='deg', frame='galactic')

    print obs_gal_coord
    obs_icrs_coord = obs_gal_coord.icrs

    print obs_icrs_coord

    obs_ra = str(obs_icrs_coord.ra.degree)
    obs_dec = str(obs_icrs_coord.dec.degree)

    print obs_ra
    print obs_dec

    #change header content
    data_tbhdu.header['NAXIS2'] = len(events)
    data_tbhdu.header['DSVAL2'] = str(observation_parameters['emin'])+":"+str(observation_parameters['emax'])
    data_tbhdu.header['DSVAL3'] = "CIRCLE("+obs_ra+","+obs_dec+","+str(observation_parameters['fov'])+")"
    data_tbhdu.header['MMN00001'] = "None"
    data_tbhdu.header['MMN00002'] = "None"
    data_tbhdu.header['TELESCOP'] = str(observation_parameters['name'])
    data_tbhdu.header['OBS_ID'] = str(observationid)

    # # time_second/86400 + 51544.5 = time_mjd
    # tstart_mjd = str(float(tstart)/86400 + 51544.5)
    # tstop_mjd = str(float(tstop)/86400 + 51544.5)
    # print tstart_mjd
    # print tstop_mjd
    # # UTC timescale
    # tstart_astropy = Time(tstart_mjd, format='mjd')
    # tstop_astropy = Time(tstop_mjd, format='mjd')
    #
    # #convert to ISO
    # tstart_astropy = tstart_astropy.iso
    # tstop_astropy = tstop_astropy.iso

    #date time
    data_tbhdu.header['DATE_OBS'] = ""
    data_tbhdu.header['TIME_OBS'] = ""
    data_tbhdu.header['DATE_END'] = ""
    data_tbhdu.header['TIME_END'] = ""
    data_tbhdu.header['TSTART'] = str(tstart)
    data_tbhdu.header['TSTOP'] = str(tstop)
    data_tbhdu.header['MJDREFI'] = "51544"
    data_tbhdu.header['MJDREFF'] = "0.5"

    data_tbhdu.header['TELAPSE'] = str(tstop-tstart)
    data_tbhdu.header['ONTIME'] = str(tstop-tstart)
    data_tbhdu.header['LIVETIME'] = str(tstop-tstart)
    data_tbhdu.header['DEADC'] = "1"
    data_tbhdu.header['TIMEDEL'] = "1"

    data_tbhdu.header['RA_PNT'] = obs_ra
    data_tbhdu.header['DEC_PNT'] = obs_dec

    # CREATE GTI data table HDU

    gti_tstart = np.array([tstart])
    gti_tstop = np.array([tstop])
    c1 = Column(name='START', format='1D', array=gti_tstart)
    c2 = Column(name='STOP', format='1D', array=gti_tstop)
    coldefs = pyfits.ColDefs([c1, c2])

    gti_tbhdu = pyfits.BinTableHDU.from_columns(coldefs)
    gti_tbhdu.header = hdulist[2].header

    thdulist = pyfits.HDUList([primary_hdu,data_tbhdu,gti_tbhdu])

    if os.path.exists(filename):
        os.unlink(filename)
    thdulist.writeto(filename)

    hdulist_new = pyfits.open(filename)

    #print hdulist_new[2].header

    hdulist_new.close()


if __name__ == '__main__':

    # crete the XML for the specific observation
    tstart = sys.argv[1]
    tstop = sys.argv[2]
    observationid = sys.argv[3]
    filename = sys.argv[4]


    write_fits(tstart,tstop,observationid,filename)

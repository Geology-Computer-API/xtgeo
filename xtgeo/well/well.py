"""XTGeo Well class"""

# #############################################################################
#
# NAME:
#    well.py
#
# AUTHOR(S):
#    Jan C. Rivenaes
#
# DESCRIPTION:
#    Class for a well. A well has some fixed metadata + a set of logs. The logs
#    are stored her as Python PANDAS dataframe
#    Note that trajecory is hardcoded to X_UTME, Y_UTMN, Z_TVDSS
#
# TODO/ISSUES/BUGS:
#
# LICENCE:
#    Statoil property
# #############################################################################

from __future__ import print_function

import sys
import numpy as np
import pandas as pd
import os.path
import csv
import logging

import cxtgeo.cxtgeo as _cxtgeo
from xtgeo.common import XTGeoDialog
from xtgeo.xyz import Points


class Well(object):
    """
    Class for a well in the xtgeo framework.

    The well logs are stored as Pandas dataframe, which make manipulation
    easy and fast.
    """

    def __init__(self, *args, **kwargs):

        """The __init__ (constructor) method.

        The instance can be made either from file or by a spesification::

        >>> x1 = Well('somefilename')  # assume RMS ascii well
        >>> x2 = Well('somefilename', fformat='rms_ascii')
        >>> x4 = Well()
        >>> x4.from_file('somefilename', fformat='rms_ascii')
        >>> x5 = Well(...)

        Args:
            xxx (nn): to come


        """

        clsname = "{}.{}".format(type(self).__module__, type(self).__name__)
        self.logger = logging.getLogger(clsname)
        self.logger.addHandler(logging.NullHandler())

        self._xtg = XTGeoDialog()
        self._undef = _cxtgeo.UNDEF
        self._undef_limit = _cxtgeo.UNDEF_LIMIT

        if args:
            # make instance from file import
            wfile = args[0]
            fformat = kwargs.get('fformat', 'rms_ascii')
            self.from_file(wfile, fformat=fformat)

        else:
            # make instance by kw spesification
            self._xx = kwargs.get('xx', 0.0)

            values = kwargs.get('values', None)

        self.logger.debug('Ran __init__ method for RegularSurface object')

    # =========================================================================
    # Import and export
    # =========================================================================

    def from_file(self, wfile, fformat="rms_ascii"):
        """
        Import well from file.

        Args:
            wfile (str): Name of file
            fformat (str): File format, rms_ascii (rms well) is
                currently supported and defualt format.

        Returns:
            Object instance, optionally

        Example:
            Here the from_file method is used to initiate the object
            directly::

            >>> mymapobject = RegularSurface().from_file('myfile.x')


        """
        if (os.path.isfile(wfile)):
            pass
        else:
            self.logger.critical("Not OK file")
            raise os.error

        if (fformat is None or fformat == "rms_ascii"):
            self._import_rms_ascii(wfile)
        else:
            self.logger.error("Invalid file format")

        return self

    def to_file(self, wfile, fformat="rms_ascii"):
        """
        Export well to file

        Args:
            wfile (str): Name of file
            fformat (str): File format

        Example::

            >>> x = Well()

        """
        if (fformat is None or fformat == "rms_ascii"):
            self._export_rms_ascii(wfile)

    # =========================================================================
    # Get and Set properties (tend to pythonic properties; not javaic get
    # & set syntax, if possible)
    # =========================================================================

    @property
    def rkb(self):
        """ Returns RKB height for the well."""
        return self._rkb

    @property
    def xpos(self):
        """ Returns well header X position."""
        return self._xpos

    @property
    def ypos(self):
        """ Returns well header Y position."""
        return self._ypos

    @property
    def wellname(self):
        """ Returns well name."""
        return self._wname

    @property
    def xwellname(self):
        """
        Returns well name on a file syntax safe form (/ and space replaced
        with _).
        """
        x = self._wname
        x = x.replace("/", "_")
        x = x.replace(" ", "_")
        return x

    @property
    def truewellname(self):
        """
        Returns well name on the assummed form aka '31/2-E-4 AH2'.
        """
        x = self.xwellname
        x = x.replace("_", "/", 1)
        x = x.replace("_", " ")
        return x

    @property
    def nlogs(self):
        """ Returns number of well logs (not including X Y TVD)."""
        return self._nlogs

    @property
    def dataframe(self):
        """ Returns or set the Pandas dataframe object for all logs."""
        return self._df

    @dataframe.setter
    def dataframe(self, df):
        self._df = df.copy()

    @property
    def nrows(self):
        """ Returns the Pandas dataframe object number of rows"""
        return len(self._df.index)

    @property
    def ncolumns(self):
        """ Returns the Pandas dataframe object number of columns"""
        return len(self._df.columns)

    @property
    def nlogs(self):
        """ Returns the Pandas dataframe object number of columns"""
        return len(self._df.columns) - 3

    @property
    def lognames_all(self):
        """ Returns the Pandas dataframe column names as list (incl X Y TVD)"""
        return list(self._df)

    @property
    def lognames(self):
        """ Returns the Pandas dataframe column as list (excl X Y TVD)"""
        return list(self._df)[3:]

    def get_logtype(self, lname):
        """ Returns the type of a give log (e.g. DISC). None if not exists."""
        if lname in self._wlogtype:
            return self._wlogtype[lname]
        else:
            return None

    def get_logrecord(self, lname):
        """ Returns the record of a give log. None if not exists"""
        if lname in self._wlogtype:
            return self._wlogrecord[lname]
        else:
            return None

    def get_logrecord_codename(self, lname, key):
        """ Returns the name entry of a log record, for a given key"""
        zlogdict = self.get_logrecord(lname)
        try:
            name = zlogdict[key]
        except:
            return None
        else:
            return name

    def get_carray(self, lname):
        """
        Returns the C array pointer (via SWIG) for a given log.

        Type conversion is double if float64, int32 if DISC log.
        Returns None of log does not exist.
        """
        try:
            np_array = self._df[lname].values
        except:
            return None

        if self.get_logtype(lname) == "DISC":
            carr = self._convert_np_carr_int(np_array)
        else:
            carr = self._convert_np_carr_double(np_array)

        return carr

    def create_relative_hlen(self):
        """
        Make a relative length of a well, as a log.

        The first well og entry defines zero, then the horisontal length
        is computed relative to that by simple geometric methods.
        """

        # need to call the C function...
        _cxtgeo.xtg_verbose_file("NONE")
        xtg_verbose_level = self._xtg.syslevel

        # extract numpies from XYZ trajetory logs
        ptr_xv = self.get_carray('X_UTME')
        ptr_yv = self.get_carray('Y_UTMN')
        ptr_zv = self.get_carray('Z_TVDSS')

        # get number of rows in pandas
        nlen = self.nrows

        ptr_hlen = _cxtgeo.new_doublearray(nlen)

        ier = _cxtgeo.pol_geometrics(nlen, ptr_xv, ptr_yv, ptr_zv, ptr_hlen,
                                     xtg_verbose_level)

        if ier != 0:
            sys.exit(-9)

        dnumpy = self._convert_carr_double_np(ptr_hlen)
        self._df['R_HLEN'] = pd.Series(dnumpy, index=self._df.index)

        # delete tmp pointers
        _cxtgeo.delete_doublearray(ptr_xv)
        _cxtgeo.delete_doublearray(ptr_yv)
        _cxtgeo.delete_doublearray(ptr_zv)
        _cxtgeo.delete_doublearray(ptr_hlen)

    def geometrics(self):
        """Compute some well geometrical arrays MD and INCL, as logs.

        These are kind of quasi measurements hence the logs will named
        with a Q in front as Q_MDEPTH and Q_INCL.

        These logs will be added to the dataframe
        """

        # need to call the C function...
        _cxtgeo.xtg_verbose_file("NONE")
        xtg_verbose_level = self._xtg.syslevel

        # extract numpies from XYZ trajetory logs
        ptr_xv = self.get_carray('X_UTME')
        ptr_yv = self.get_carray('Y_UTMN')
        ptr_zv = self.get_carray('Z_TVDSS')

        # get number of rows in pandas
        nlen = self.nrows

        ptr_md = _cxtgeo.new_doublearray(nlen)
        ptr_incl = _cxtgeo.new_doublearray(nlen)

        ier = _cxtgeo.well_geometrics(nlen, ptr_xv, ptr_yv, ptr_zv, ptr_md,
                                      ptr_incl, 0, xtg_verbose_level)

        if ier != 0:
            sys.exit(-9)

        dnumpy = self._convert_carr_double_np(ptr_md)
        self._df['Q_MDEPTH'] = pd.Series(dnumpy, index=self._df.index)

        dnumpy = self._convert_carr_double_np(ptr_incl)
        self._df['Q_INCL'] = pd.Series(dnumpy, index=self._df.index)

        # delete tmp pointers
        _cxtgeo.delete_doublearray(ptr_xv)
        _cxtgeo.delete_doublearray(ptr_yv)
        _cxtgeo.delete_doublearray(ptr_zv)
        _cxtgeo.delete_doublearray(ptr_md)
        _cxtgeo.delete_doublearray(ptr_incl)

    def get_fence_polyline(self, sampling=20, extend=2, tvdmin=None):
        """
        Return a fence polyline as a numpy array.

        (Perhaps this should belong to a polygon class?)
        """

        # need to call the C function...
        _cxtgeo.xtg_verbose_file("NONE")
        xtg_verbose_level = self._xtg.syslevel

        df = self._df

        if tvdmin is not None:
            self._df = df[df['Z_TVDSS'] > tvdmin]

        ptr_xv = self.get_carray('X_UTME')
        ptr_yv = self.get_carray('Y_UTMN')
        ptr_zv = self.get_carray('Z_TVDSS')

        nbuf = 1000000
        ptr_xov = _cxtgeo.new_doublearray(nbuf)
        ptr_yov = _cxtgeo.new_doublearray(nbuf)
        ptr_zov = _cxtgeo.new_doublearray(nbuf)
        ptr_hlv = _cxtgeo.new_doublearray(nbuf)

        ptr_nlen = _cxtgeo.new_intpointer()

        ier = _cxtgeo.pol_resample(self.nrows, ptr_xv, ptr_yv, ptr_zv,
                                   sampling, extend, nbuf, ptr_nlen,
                                   ptr_xov, ptr_yov, ptr_zov, ptr_hlv,
                                   0, xtg_verbose_level)

        if ier != 0:
            sys.exit(-2)

        nlen = _cxtgeo.intpointer_value(ptr_nlen)

        npxarr = self._convert_carr_double_np(ptr_xov, nlen=nlen)
        npyarr = self._convert_carr_double_np(ptr_yov, nlen=nlen)
        npzarr = self._convert_carr_double_np(ptr_zov, nlen=nlen)
        npharr = self._convert_carr_double_np(ptr_hlv, nlen=nlen)
        npharr = npharr - sampling * extend

        x = np.concatenate((npxarr, npyarr, npzarr, npharr), axis=0)
        x = np.reshape(x, (nlen, 4), order='F')

        _cxtgeo.delete_doublearray(ptr_xov)
        _cxtgeo.delete_doublearray(ptr_yov)
        _cxtgeo.delete_doublearray(ptr_zov)
        _cxtgeo.delete_doublearray(ptr_hlv)

        return x

    def report_zonation_holes(self, zonelogname=None, threshold=5,
                              mdlogname=None):
        """
        Reports if well has holes in the zonation, less or equal to N samples.

        Zonation may have holes due to various reasons, and
        usually a few undef samples indicates that something is wrong.
        This method reports well and start interval of the "holes"

        Args:
            zonelogname (str): name of Zonelog to be applied
            threshold (int): Number of samples (max.) that defines a hole, e.g.
                5 means that undef samples in the range [1, 5] (including 5) is
                applied

        Returns:
            A Pandas dataframe as report. None if no list is made.
        """

        wellreport = []

        try:
            zlog = self._df[zonelogname].values
        except Exception:
            self.logger.warning("Cannot get zonelog")
            return None

        mdlog = None
        if mdlogname is not None:
            mdlog = self._df[mdlogname].values

        x = self._df['X_UTME'].values
        y = self._df['Y_UTMN'].values
        z = self._df['Z_TVDSS'].values
        zlog[np.isnan(zlog)] = -999

        nc = 0
        first = True
        hole = False
        for ind, zone in np.ndenumerate(zlog):
            i = ind[0]
            if zone == -999 and first:
                continue

            if zone != -999 and first:
                first = False
                continue

            if zone == -999:
                nc += 1
                hole = True

            if zone == -999 and nc > threshold:
                self.logger.info("Restart first (bigger hole)")
                hole = False
                first = True
                nc = 0
                continue

            if hole and zone != -999 and nc <= threshold:
                # here we have a hole that fits criteria
                if mdlog is not None:
                    entry = (i, x[i], y[i], z[i], int(zone), self.xwellname,
                             mdlog[i])
                else:
                    entry = (i, x[i], y[i], z[i], int(zone), self.xwellname)

                wellreport.append(entry)

                # retstart count
                hole = False
                nc = 0

            if hole and zone != -999 and nc > threshold:
                hole = False
                nc = 0

        if len(wellreport) == 0:
            return None
        else:
            if mdlog is not None:
                clm = ['INDEX', 'X', 'Y', 'Z', 'Zone', 'Well', 'MD']
            else:
                clm = ['INDEX', 'X', 'Y', 'Z', 'Zone', 'Well']

            df = pd.DataFrame(wellreport, columns=clm)
            return df

    def get_zonation_points(self, zonelogname=None, tops=True,
                            incl_limit=80, top_prefix='Top',
                            zonelist=None):

        """Extract zonation points from Zonelog and make a marker list.

        Currently it is either 'Tops' or 'Zone' (thicknesses); default
        is tops (i.e. tops=True).

        Args:
            zonelogname (str): name of Zonelog to be applied
            tops (bool): If True then compute tops, else (thickness) points.
            incl_limit (float): If given, and usezone is True, the max
                angle of inclination to be  used as input to zonation points.
            top_prefix (str): As well logs usually have isochore (zone) name,
                this prefix could be Top, e.g. 'SO43' --> 'TopSO43'

        Returns:
            A pandas dataframe (ready for the xyz/Points class)
        """

        zlist = []
        # get the relevant logs:

        self.geometrics()

        zlog = self._df[zonelogname].values
        xv = self._df['X_UTME'].values
        yv = self._df['Y_UTMN'].values
        zv = self._df['Z_TVDSS'].values
        incl = self._df['Q_INCL'].values
        md = self._df['Q_MDEPTH'].values

        zlog[np.isnan(zlog)] = -999

        self.logger.info("\n")
        self.logger.info(zlog)
        self.logger.info(xv)
        self.logger.info(zv)

        self.logger.info(self.get_logrecord(zonelogname))
        if zonelist is None:
            zonelist = self.get_logrecord(zonelogname).keys()

        self.logger.info("Find values for {}".format(zonelist))

        ztops, ztopnames, zisos, zisonames = (
            self._extract_ztops(zonelist, xv, yv, zv, zlog, md, incl,
                                zonelogname, tops=tops,
                                incl_limit=incl_limit,
                                prefix=top_prefix))

        if tops:
            zlist = ztops
        else:
            zlist = zisos

        self.logger.debug(zlist)

        if tops:
            df = pd.DataFrame(zlist, columns=ztopnames)
        else:
            df = pd.DataFrame(zlist, columns=zisonames)

        self.logger.info(df)

        return df

    # =========================================================================
    # PRIVATE METHODS
    # should not be applied outside the class
    # =========================================================================

    # -------------------------------------------------------------------------
    # Import/Export methods for various formats
    # -------------------------------------------------------------------------

    # Import RMS ascii
    # -------------------------------------------------------------------------
    def _import_rms_ascii(self, wfile):

        self._wlogtype = dict()
        self._wlogrecord = dict()

        self._lognames_all = ['X_UTME', 'Y_UTMN', 'Z_TVDSS'];
        self._lognames = [];

        lnum = 1
        with open(wfile, 'r') as f:
            for line in f:
                if lnum == 1:
                    self._ffver = line.strip()
                elif lnum == 2:
                    self._wtype = line.strip()
                elif lnum == 3:
                    row = line.strip().split()
                    self._rkb = float(row[-1])
                    self._ypos = float(row[-2])
                    self._xpos = float(row[-3])
                    self._wname = row[-4]

                elif lnum == 4:
                    self._nlogs = int(line)
                    nlogread = 1

                else:
                    row = line.strip().split()
                    lname = row[0]
                    ltype = row[1].upper()

                    rx = row[2:]

                    self._lognames_all.append(lname)
                    self._lognames.append(lname)

                    self._wlogtype[lname] = ltype

                    if ltype == 'DISC':
                        xdict = {int(rx[i]): rx[i + 1] for i in
                                 range(0, len(rx), 2)}
                        self._wlogrecord[lname] = xdict
                    else:
                        self._wlogrecord[lname] = rx

                    nlogread += 1

                    if nlogread > self._nlogs:
                        break

                lnum += 1

        # now import all logs as pandas framework

        self._df = pd.read_csv(wfile, delim_whitespace=True, skiprows=lnum,
                               header=None, names=self._lognames_all,
                               dtype=np.float64, na_values=-999)

        self.logger.debug(self._df.head())


    # Export RMS ascii
    #---------------------------------------------------------------------------
    def _export_rms_ascii(self, wfile):

        with open(wfile, 'w') as f:
            print("{}".format(self._ffver), file=f)
            print("{}".format(self._wtype), file=f)
            print("{} {} {} {}".format(self._wname, self._xpos, self._ypos,
                                       self._rkb), file=f)
            for lname in self.lognames:
                wrec = []
                if type(self._wlogrecord[lname]) is dict:
                    for key in self._wlogrecord[lname]:
                        wrec.append(key)
                        wrec.append(self._wlogrecord[lname][key])

                else:
                    wrec = self._wlogrecord[lname]

                wrec = ' '.join(str(x) for x in wrec)
                print(wrec)

                print("{} {} {}".format(lname, self._wlogtype[lname],
                                        wrec), file=f)

        # now export all logs as pandas framework
        tmpdf = self._df.copy()
        tmpdf.fillna(value=-999, inplace=True)

        # make the disc as is np.int
        for lname in self._wlogtype:
            if self._wlogtype[lname] == 'DISC':
                tmpdf[[lname]] = tmpdf[[lname]].astype(int)

        tmpdf.to_csv(wfile, sep=' ', header=False, index=False,
                     float_format='%-14.3f', quoting=csv.QUOTE_NONE,
                     escapechar=" ", mode='a')

    # -------------------------------------------------------------------------
    # Various private methods
    # -------------------------------------------------------------------------

    def _extract_ztops(self, keylist, x, y, z, zlog, md, incl, zlogname,
                       tops=True, incl_limit=80, prefix='Top'):
        """Extract a list of tops for a zone.

        Args:
            keylist (list): The zonelog list number to apply
            x (np): X Position numpy array
            y (np): Y Position numpy array
            z (np): Z Position numpy array
            zlog (np): Zonelog array
            md (np): MDepth log numpy array
            incl (np): Inclination log numpy array
            zlogname (str): Name of zonation log
            tops (bool): Compute tops or thickness (zone) points (default True)
            incl_limit (float): Limitation of zone computation (angle, degrees)
        """

        # The wellpoints will be a list of tuples (one tuple per hit)
        # Tuple: (X Y Z DZ ZONEKEY ZONENAME WELLNAME)
        wpts = []

        self.logger.debug(zlog)

        if not tops and incl_limit is None:
            incl_limit = 80

        azi = -999.0  # tmp so far

        for key in keylist:
            for ind, zone in np.ndenumerate(zlog):
                i = ind[0]
                if i == 0:
                    continue

                # look at the previous values
                pzone = zlog[i - 1]

                self.logger.debug("PZONE is {} and zone is {}"
                                  .format(pzone, zone))

                if (pzone == -999 or zone == -999):
                    continue

                if pzone != zone:
                    self.logger.info("FOUND")
                    if zone == key and pzone < zone:
                        self.logger.info("FOUND MATCH")
                        zname = self.get_logrecord_codename(zlogname, key)
                        zname = prefix + zname
                        ztop = (x[i], y[i], z[i], md[i], incl[i], azi,
                                key, zname, self.xwellname)
                        wpts.append(ztop)
                        if pzone == key and pzone > zone:
                            self.logger.info("FOUND MATCH")
                            key2 = int(pzone)
                            zname = self.get_logrecord_codename(zlogname, key2)
                            zname = prefix + zname
                            ztop = (x[i - 1], y[i - 1], z[i - 1], md[i - 1],
                                    incl[i - 1], azi, key2, zname,
                                    self.xwellname)
                            wpts.append(ztop)

        wpts_names = ['X', 'Y', 'Z', 'QMD', 'QINCL', 'QAZI', 'Zone', 'TopName',
                      'WellName']

        if tops:
            return wpts, wpts_names, None, None

        # next get a MIDPOINT zthickness (DZ)
        llen = len(wpts) - 1

        zwpts_names = ['X', 'Y', 'Z', 'QMD_AVG', 'QMD1', 'QMD2', 'QINCL',
                       'QAZI', 'Zone', 'ZoneName', 'WellName']

        zwpts = []
        for i in range(llen):
            i1 = i
            i2 = i + 1
            xx1, yy1, zz1, md1, incl1, azi1, zk1, zn1, wn1 = wpts[i1]
            xx2, yy2, zz2, md2, incl2, azi2, zk2, zn2, wn2 = wpts[i2]

            # mid point
            xx_avg = (xx1 + xx2) / 2
            yy_avg = (yy1 + yy2) / 2
            md_avg = (md1 + md2) / 2
            incl_avg = (incl1 + incl2) / 2

            azi_avg = -999.0  # to be fixed later

            zzp = round(abs(zz2 - zz1), 4)

            useok = False

            if incl_avg < incl_limit:
                useok = True

            if useok and zk2 != zk1:
                self.logger.debug(" -- Zone {} {} ---> {}"
                                  .format(zk1, zk2, zzp))
                usezk = zk1
                usezn = zn1
                if zk1 > zk2:
                    usezk = zk2
                    usezn = zn2
                usezn = usezn[len(prefix):]

                zzone = (xx_avg, yy_avg, zzp, md_avg, md1, md2, incl_avg,
                         azi_avg, usezk, usezn, wn1)
                zwpts.append(zzone)

        return wpts, wpts_names, zwpts, zwpts_names

    # -------------------------------------------------------------------------
    # Special methods for nerds
    # -------------------------------------------------------------------------

    def _convert_np_carr_int(self, np_array):
        """
        Convert numpy 1D array to C array, assuming int type. The numpy
        is always a double (float64), so need to convert first
        """
        carr = _cxtgeo.new_intarray(self.nrows)

        np_array = np_array.astype(np.int32)

        _cxtgeo.swig_numpy_to_carr_i1d(np_array, carr)

        return carr

    def _convert_np_carr_double(self, np_array):
        """
        Convert numpy 1D array to C array, assuming double type
        """
        carr = _cxtgeo.new_doublearray(self.nrows)

        _cxtgeo.swig_numpy_to_carr_1d(np_array, carr)

        return carr

    def _convert_carr_double_np(self, carray, nlen=None):
        """
        Convert a C array to numpy, assuming double type.
        """
        if nlen is None:
            nlen = len(self._df.index)

        nparray = _cxtgeo.swig_carr_to_numpy_1d(nlen, carray)

        return nparray

"""Import tasks for the spectra collected by the Superfit software package.
"""
import os
import re
from glob import glob

from astropy.time import Time as astrotime


from astrocats.catalog.utils import pbar
from cdecimal import Decimal


def do_superfit_spectra(catalog):
    superfit_url = 'http://www.dahowell.com/superfit.html'
    current_task = catalog.get_current_task_str()
    sfdirs = list(glob(os.path.join(catalog.get_current_task_repo(), 'superfit/*')))
    for sfdir in pbar(sfdirs, desc=current_task):
        sffiles = sorted(glob(sfdir + '/*.dat'))
        lastname = ''
        oldname = ''
        for sffile in pbar(sffiles, desc=current_task):
            basename = os.path.basename(sffile)
            name = basename.split('.')[0]
            if name.startswith('sn'):
                name = 'SN' + name[2:]
                if len(name) == 7:
                    name = name[:6] + name[6].upper()
            elif name.startswith('ptf'):
                name = 'PTF' + name[3:]

            if 'theory' in name:
                continue
            if catalog.event_exists(name):
                prefname = catalog.get_preferred_name(name)
                if ('spectra' in catalog.entries[prefname] and
                        lastname != prefname):
                    continue
            if oldname and name != oldname:
                catalog.journal_entries()
            oldname = name
            name = catalog.add_entry(name)
            epoch = basename.split('.')[1]
            (mldt, mlmag, mlband, mlsource) = catalog.get_max_light(name)
            if mldt:
                if epoch == 'max':
                    epoff = Decimal(0.0)
                elif epoch[0] == 'p':
                    epoff = Decimal(epoch[1:])
                else:
                    epoff = -Decimal(epoch[1:])
            else:
                epoff = ''

            source = catalog.entries[name].add_source(
                srcname='Superfit', url=superfit_url, secondary=True)
            catalog.entries[name].add_quantity('alias', oldname, source)

            with open(sffile) as ff:
                rows = ff.read().splitlines()
            specdata = []
            for row in rows:
                if row.strip():
                    specdata.append(
                        list(filter(None, re.split('\t+|\s+', row,
                                                   maxsplit=0))))
            specdata = [[xx.replace('D', 'E') for xx in list(ii)]
                        for ii in zip(*specdata)]
            wavelengths = specdata[0]
            fluxes = specdata[1]

            if epoff != '':
                mlmjd = astrotime(
                    '-'.join([str(mldt.year), str(mldt.month),
                              str(mldt.day)])).mjd
                mlmjd = str(Decimal(mlmjd) + epoff)
            else:
                mlmjd = ''
            catalog.entries[name].add_spectrum(
                'Angstrom', 'Uncalibrated', u_time='MJD' if mlmjd else '',
                time=mlmjd, wavelengths=wavelengths, fluxes=fluxes,
                source=source)

            lastname = name

        catalog.journal_entries()
    return

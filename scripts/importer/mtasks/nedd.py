import csv
import os
from collections import OrderedDict
from html import unescape

from astropy import units as un
from astropy.cosmology import Planck15 as cosmo
from astropy.cosmology import z_at_value

from cdecimal import Decimal
from scripts import PATH

from .. import Events
from ...utils import is_number, pbar
from ..funcs import get_sig_digits, host_clean, name_clean, pretty_num, uniq_cdl


def do_nedd(catalog):
    current_task = 'NED-D'
    nedd_path = os.path.join(
        PATH.REPO_EXTERNAL, 'NED26.05.1-D-12.1.0-20160501.csv')

    f = open(nedd_path, 'r')

    data = sorted(list(csv.reader(f, delimiter=',', quotechar='"'))[
                  13:], key=lambda x: (x[9], x[3]))
    reference = "NED-D"
    refurl = "http://ned.ipac.caltech.edu/Library/Distances/"
    nedd_dict = OrderedDict()
    olddistname = ''
    for r, row in enumerate(pbar(data, current_task)):
        if r <= 12:
            continue
        distname = row[3]
        name = name_clean(distname)
        # distmod = row[4]
        # moderr = row[5]
        dist = row[6]
        bibcode = unescape(row[8])
        snname = name_clean(row[9])
        redshift = row[10]
        cleanhost = ''
        if name != snname and (name + ' HOST' != snname):
            cleanhost = host_clean(distname)
            if cleanhost.endswith(' HOST'):
                cleanhost = ''
            if not is_number(dist):
                print(dist)
            if dist:
                nedd_dict.setdefault(cleanhost, []).append(Decimal(dist))
        if snname and 'HOST' not in snname:
            events, snname, secondarysource = Events.new_event(
                tasks, args, events, snname, log,
                srcname=reference, url=refurl, secondary=True)
            if bibcode:
                source = events[snname].add_source(bibcode=bibcode)
                sources = uniq_cdl([source, secondarysource])
            else:
                sources = secondarysource
            if name == snname:
                if redshift:
                    events[snname].add_quantity(
                        'redshift', redshift, sources)
                if dist:
                    events[snname].add_quantity(
                        'comovingdist', dist, sources)
                    if not redshift:
                        try:
                            zatval = z_at_value(cosmo.comoving_distance,
                                                float(dist) * un.Mpc, zmax=5.0)
                            sigd = get_sig_digits(str(dist))
                            redshift = pretty_num(zatval, sig=sigd)
                        except (KeyboardInterrupt, SystemExit):
                            raise
                        except:
                            pass
                        else:
                            cosmosource = catalog.events[name].add_source(
                                bibcode='2015arXiv150201589P')
                            combsources = uniq_cdl(sources.split(',') +
                                                   [cosmosource])
                            events[snname].add_quantity('redshift', redshift,
                                                        combsources)
            if cleanhost:
                events[snname].add_quantity('host', cleanhost, sources)
            if args.update and olddistname != distname:
                events = Events.journal_events(
                    tasks, args, events, log)
        olddistname = distname
    events = Events.journal_events(tasks, args, events, log)

    f.close()

    return events

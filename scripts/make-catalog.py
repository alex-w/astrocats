#!/usr/local/bin/python3.5

import csv
import glob
import sys
import os
import re
import operator
import json
import argparse
import hashlib
import numpy
import shutil
import gzip
import requests
import urllib.request
import urllib.parse
import filecmp
from datetime import datetime
from astropy.time import Time as astrotime
from astropy.coordinates import SkyCoord as coord
from astropy import units as un
#from colorpy.ciexyz import xyz_from_wavelength
#from colorpy.colormodels import irgb_string_from_xyz
from copy import deepcopy
from random import shuffle, seed
from collections import OrderedDict
from bokeh.plotting import Figure, show, save, reset_output
from bokeh.models import HoverTool, CustomJS, Slider, ColumnDataSource, HBox, VBox, Range1d, LinearAxis
from bokeh.resources import CDN, INLINE
from bokeh.embed import file_html, components
from palettable import cubehelix
from bs4 import BeautifulSoup, Tag, NavigableString
from math import isnan, floor

parser = argparse.ArgumentParser(description='Generate a catalog JSON file and plot HTML files from SNE data.')
parser.add_argument('--no-write-catalog', '-nwc', dest='writecatalog', help='Don\'t write catalog file',         default=True, action='store_false')
parser.add_argument('--no-write-html', '-nwh',    dest='writehtml',    help='Don\'t write html plot files',      default=True, action='store_false')
parser.add_argument('--no-collect-hosts', '-nch', dest='collecthosts', help='Don\'t collect host galaxy images', default=True, action='store_false')
parser.add_argument('--force-html', '-fh',        dest='forcehtml',    help='Force write html plot files',       default=False, action='store_true')
parser.add_argument('--event-list', '-el',        dest='eventlist',    help='Process a list of events',          default=[], type=str, nargs='+')
parser.add_argument('--test', '-t',               dest='test',         help='Test this script',                  default=False, action='store_true')
args = parser.parse_args()

outdir = "../"

linkdir = "https://sne.space/sne/"

testsuffix = '.test' if args.test else ''

mycolors = cubehelix.perceptual_rainbow_16.hex_colors[:14]

columnkey = [
    "check",
    "name",
    "aliases",
    "discoverdate",
    "maxdate",
    "maxappmag",
    "maxabsmag",
    "host",
    "ra",
    "dec",
    "instruments",
    "redshift",
    "hvel",
    "lumdist",
    "claimedtype",
    "photolink",
    "spectralink",
    "references",
    "download",
    "responsive"
]

eventignorekey = [
    "download"
]

header = [
    "",
    "Name",
    "Aliases",
    "Disc. Date",
    "Max Date",
    r"<em>m</em><sub>max</sub>",
    r"<em>M</em><sub>max</sub>",
    "Host Name",
    "R.A. (h:m:s)",
    "Dec. (d:m:s)",
    "Instruments/Bands",
    r"<em>z</em>",
    r"<em>v</em><sub>&#9737;</sub> (km/s)",
    r"<em>d</em><sub>L</sub> (Mpc)",
    "Claimed Type",
    "Phot.",
    "Spec.",
    "References",
    "",
    ""
]

eventpageheader = [
    "",
    "Name",
    "Aliases",
    "Discovery Date",
    "Date of Maximum",
    r"<em>m</em><sub>max</sub>",
    r"<em>M</em><sub>max</sub>",
    "Host Name",
    "R.A. (h:m:s)",
    "Dec. (d:m:s)",
    "Instruments/Bands",
    r"<em>z</em>",
    r"<em>v</em><sub>&#9737;</sub> (km/s)",
    r"<em>d</em><sub>L</sub> (Mpc)",
    "Claimed Type",
    "# Phot. Obs.",
    "# Spectra",
    "References",
    "",
    ""
]

titles = [
    "",
    "Name (IAU name preferred)",
    "Aliases",
    "Discovey Date (year-month-day)",
    "Date of Maximum (year-month-day)",
    "Maximum apparent AB magnitude",
    "Maximum absolute AB magnitude",
    "Host Name",
    "J2000 Right Ascension (h:m:s)",
    "J2000 Declination (d:m:s)",
    "List of Instruments and Bands",
    "Redshift",
    "Heliocentric velocity (km/s)",
    "Luminosity distance (Mpc)",
    "Claimed Type",
    "Photometry",
    "Spectra",
    "Download",
    "Bibcodes of references with most data on event",
    ""
]

photokeys = [
    'timeunit',
    'time',
    'band',
    'instrument',
    'magnitude',
    'aberr',
    'upperlimit',
    'source'
]

sourcekeys = [
    'name',
    'alias',
    'secondary'
]

with open('rep-folders.txt', 'r') as f:
    repfolders = f.read().splitlines()

repyears = [int(repfolders[x][-4:]) for x in range(len(repfolders))]
repyears[0] -= 1

if len(columnkey) != len(header):
    print('Error: Header not same length as key list.')
    sys.exit(0)

if len(columnkey) != len(eventpageheader):
    print('Error: Event page header not same length as key list.')
    sys.exit(0)

dataavaillink = "<a href='https://bitbucket.org/Guillochon/sne'>Y</a>"

header = OrderedDict(list(zip(columnkey,header)))
eventpageheader = OrderedDict(list(zip(columnkey,eventpageheader)))
titles = OrderedDict(list(zip(columnkey,titles)))

bandcodes = [
    "u",
    "g",
    "r",
    "i",
    "z",
    "u'",
    "g'",
    "r'",
    "i'",
    "z'",
    "u_SDSS",
    "g_SDSS",
    "r_SDSS",
    "i_SDSS",
    "z_SDSS",
    "U",
    "B",
    "V",
    "R",
    "I",
    "G",
    "Y",
    "J",
    "H",
    "K",
    "C",
    "CR",
    "CV",
    "uvm2",
    "uvw1",
    "uvw2",
    "pg",
    "Mp"
]

bandaliases = OrderedDict([
    ("u_SDSS", "u (SDSS)"),
    ("g_SDSS", "g (SDSS)"),
    ("r_SDSS", "r (SDSS)"),
    ("i_SDSS", "i (SDSS)"),
    ("z_SDSS", "z (SDSS)"),
    ("uvm2"  , "M2 (UVOT)"),
    ("uvw1"  , "W1 (UVOT)"),
    ("uvw2"  , "W2 (UVOT)"),
])

bandshortaliases = OrderedDict([
    ("u_SDSS", "u"),
    ("g_SDSS", "g"),
    ("r_SDSS", "r"),
    ("i_SDSS", "i"),
    ("z_SDSS", "z"),
    ("G"     , "" )
])

bandwavelengths = {
    "u"      : 354.,
    "g"      : 475.,
    "r"      : 622.,
    "i"      : 763.,
    "z"      : 905.,
    "u'"     : 354.,
    "g'"     : 475.,
    "r'"     : 622.,
    "i'"     : 763.,
    "z'"     : 905.,
    "u_SDSS" : 354.3,
    "g_SDSS" : 477.0,
    "r_SDSS" : 623.1,
    "i_SDSS" : 762.5,
    "z_SDSS" : 913.4,
    "U"      : 365.,
    "B"      : 445.,
    "V"      : 551.,
    "R"      : 658.,
    "I"      : 806.,
    "Y"      : 1020.,
    "J"      : 1220.,
    "H"      : 1630.,
    "K"      : 2190.,
    "uvm2"   : 260.,
    "uvw1"   : 224.6,
    "uvw2"   : 192.8
}

wavedict = dict(list(zip(bandcodes,bandwavelengths)))

seed(101)
#bandcolors = ["#%06x" % round(float(x)/float(len(bandcodes))*0xFFFEFF) for x in range(len(bandcodes))]
bandcolors = cubehelix.cubehelix1_16.hex_colors[2:14] + cubehelix.cubehelix2_16.hex_colors[2:14] + cubehelix.cubehelix3_16.hex_colors[2:14]
shuffle(bandcolors)

def event_filename(name):
    return(name.replace('/', '_'))

# Replace bands with real colors, if possible.
#for b, code in enumerate(bandcodes):
#    if (code in bandwavelengths):
#        hexstr = irgb_string_from_xyz(xyz_from_wavelength(bandwavelengths[code]))
#        if (hexstr != "#000000"):
#            bandcolors[b] = hexstr

bandcolordict = dict(list(zip(bandcodes,bandcolors)))

coldict = dict(list(zip(list(range(len(columnkey))),columnkey)))

def bandcolorf(color):
    if (color in bandcolordict):
        return bandcolordict[color]
    return 'black'

def bandaliasf(code):
    if (code in bandaliases):
        return bandaliases[code]
    return code

def bandshortaliasf(code):
    if (code in bandshortaliases):
        return bandshortaliases[code]
    return code

def bandwavef(code):
    if (code in bandwavelengths):
        return bandwavelengths[code]
    return 0.

def utf8(x):
    return str(x, 'utf-8')

def get_rep_folder(entry):
    if 'discoverdate' not in entry:
        return repfolders[0]
    if not is_number(entry['discoverdate'][0]['value'].split('/')[0]):
        print ('Error, discovery year is not a number!')
        sys.exit()
    for r, repyear in enumerate(repyears):
        if int(entry['discoverdate'][0]['value'].split('/')[0]) <= repyear:
            return repfolders[r]
    return repfolders[0]

def is_number(s):
    try:
        float(s)
        return True
    except ValueError:
        return False

def label_format(label):
    newlabel = label.replace('Angstrom', 'Å')
    newlabel = newlabel.replace('^2', '²')
    return newlabel

def is_valid_link(url):
    response = requests.get(url)
    try:
        response.raise_for_status()
    except:
        return False
    return True

catalog = OrderedDict()
catalogcopy = OrderedDict()
snepages = []
sourcedict = {}
nophoto = []
nospectra = []
totalphoto = 0
totalspectra = 0

hostimgs = []
if os.path.isfile(outdir + 'hostimgs.json'):
    with open(outdir + 'hostimgs.json', 'r') as f:
        filetext = f.read()
    oldhostimgs = json.loads(filetext)
    oldhostimgs = [list(i) for i in zip(*oldhostimgs)]
    hostimgdict = dict(list(zip(oldhostimgs[0], oldhostimgs[1])))
else:
    hostimgdict = {}

files = []
for rep in repfolders:
    files += glob.glob('../' + rep + "/*.json")

md5s = []
md5 = hashlib.md5
if os.path.isfile(outdir + 'md5s.json'):
    with open(outdir + 'md5s.json', 'r') as f:
        filetext = f.read()
    oldmd5s = json.loads(filetext)
    oldmd5s = [list(i) for i in zip(*oldmd5s)]
    md5dict = dict(list(zip(oldmd5s[0], oldmd5s[1])))
else:
    md5dict = {}

for fcnt, eventfile in enumerate(sorted(files, key=lambda s: s.lower())):
    if args.eventlist and os.path.splitext(os.path.basename(eventfile))[0] not in args.eventlist:
        continue

    checksum = md5(open(eventfile, 'rb').read()).hexdigest()
    md5s.append([eventfile, checksum])

    with open(eventfile, 'r') as f:
        filetext = f.read()

    catalog.update(json.loads(filetext, object_pairs_hook=OrderedDict))
    entry = next(reversed(catalog))

    eventname = entry
    fileeventname = os.path.splitext(os.path.basename(eventfile))[0]

    if args.eventlist and eventname not in args.eventlist:
        continue

    print(eventfile + ' [' + checksum + ']')

    repfolder = get_rep_folder(catalog[entry])
    catalog[entry]['name'] = "<a href='https://sne.space/sne/" + fileeventname + "/'>" + catalog[entry]['name'] + "</a>"
    catalog[entry]['download'] = "<a class='dci' title='Download Data' href='" + linkdir + fileeventname + ".json' download></a>"
    if 'discoverdate' in catalog[entry]:
        for d, date in enumerate(catalog[entry]['discoverdate']):
            catalog[entry]['discoverdate'][d]['value'] = catalog[entry]['discoverdate'][d]['value'].split('.')[0]
    if 'maxdate' in catalog[entry]:
        for d, date in enumerate(catalog[entry]['maxdate']):
            catalog[entry]['maxdate'][d]['value'] = catalog[entry]['maxdate'][d]['value'].split('.')[0]

    photoavail = 'photometry' in catalog[entry]
    numphoto = len([x for x in catalog[entry]['photometry'] if 'upperlimit' not in x]) if photoavail else 0
    catalog[entry]['numphoto'] = numphoto
    if photoavail:
        plotlink = "sne/" + fileeventname + "/"
        catalog[entry]['photoplot'] = plotlink
        plotlink = "<a class='lci' href='" + plotlink + "' target='_blank'></a> "
        catalog[entry]['photolink'] = plotlink + str(numphoto)
    spectraavail = 'spectra' in catalog[entry]
    catalog[entry]['numspectra'] = len(catalog[entry]['spectra']) if spectraavail else 0
    if spectraavail:
        plotlink = "sne/" + fileeventname + "/"
        catalog[entry]['spectraplot'] = plotlink
        plotlink = "<a class='sci' href='" + plotlink + "' target='_blank'></a> "
        catalog[entry]['spectralink'] = plotlink + str(len(catalog[entry]['spectra']))

    prange = list(range(len(catalog[entry]['photometry']))) if 'photometry' in catalog[entry] else []
    
    instrulist = sorted([_f for _f in list({catalog[entry]['photometry'][x]['instrument'] if 'instrument' in catalog[entry]['photometry'][x] else None for x in prange}) if _f])
    if len(instrulist) > 0:
        instruments = ''
        for i, instru in enumerate(instrulist):
            instruments += instru
            bandlist = sorted([_f for _f in list({bandshortaliasf(catalog[entry]['photometry'][x]['band'] if 'band' in catalog[entry]['photometry'][x] else '')
                if 'instrument' in catalog[entry]['photometry'][x] and catalog[entry]['photometry'][x]['instrument'] == instru else "" for x in prange}) if _f], key=lambda y: (bandwavef(y), y))
            if bandlist:
                instruments += ' (' + ", ".join(bandlist) + ')'
            if i < len(instrulist) - 1:
                instruments += ', '

        catalog[entry]['instruments'] = instruments
    else:
        bandlist = sorted([_f for _f in list({bandshortaliasf(catalog[entry]['photometry'][x]['band']
            if 'band' in catalog[entry]['photometry'][x] else '') for x in prange}) if _f], key=lambda y: (bandwavef(y), y))
        if len(bandlist) > 0:
            catalog[entry]['instruments'] = ", ".join(bandlist)

    tools = "pan,wheel_zoom,box_zoom,save,crosshair,reset,resize"

    # Check file modification times before constructing .html files, which is expensive
    dohtml = True
    if not args.forcehtml:
        if os.path.isfile(outdir + fileeventname + ".html"):
            if eventfile in md5dict and checksum == md5dict[eventfile]:
                dohtml = False

    # Copy JSON files up a directory if they've changed
    if dohtml:
        shutil.copy2(eventfile, '../' + os.path.basename(eventfile))

    if photoavail and dohtml and args.writehtml:
        phototime = [float(x['time']) for x in catalog[entry]['photometry'] if 'magnitude' in x]
        phototimelowererrs = [float(x['e_lower_time']) if ('e_lower_time' in x and 'e_upper_time' in x)
            else (float(x['e_time']) if 'e_time' in x else 0.) for x in catalog[entry]['photometry'] if 'magnitude' in x]
        phototimeuppererrs = [float(x['e_upper_time']) if ('e_lower_time' in x and 'e_upper_time' in x) in x
            else (float(x['e_time']) if 'e_time' in x else 0.) for x in catalog[entry]['photometry'] if 'magnitude' in x]
        photoAB = [float(x['magnitude']) for x in catalog[entry]['photometry'] if 'magnitude' in x]
        photoABerrs = [(float(x['e_magnitude']) if 'e_magnitude' in x else 0.) for x in catalog[entry]['photometry'] if 'magnitude' in x]
        photoband = [(x['band'] if 'band' in x else '') for x in catalog[entry]['photometry'] if 'magnitude' in x]
        photoinstru = [(x['instrument'] if 'instrument' in x else '') for x in catalog[entry]['photometry'] if 'magnitude' in x]
        photosource = [', '.join(str(j) for j in sorted(int(i) for i in catalog[entry]['photometry'][x]['source'].split(','))) for x in prange]
        phototype = [(x['upperlimit'] if 'upperlimit' in x else False) for x in catalog[entry]['photometry'] if 'magnitude' in x]

        x_buffer = 0.1*(max(phototime) - min(phototime)) if len(phototime) > 1 else 1.0

        tt = [  
                ("Source ID", "@src"),
                ("Epoch (" + catalog[entry]['photometry'][0]['timeunit'] + ")", "@x{1.11}"),
                ("Magnitude", "@y{1.111}"),
                ("Error", "@err{1.111}"),
                ("Band", "@desc")
             ]
        if len(list(filter(None, photoinstru))):
            tt += [("Instrument", "@instr")]
        hover = HoverTool(tooltips = tt)

        p1 = Figure(title='Photometry for ' + eventname, x_axis_label='Time (' + catalog[entry]['photometry'][0]['timeunit'] + ')',
            y_axis_label='AB Magnitude', tools = tools, 
            x_range = (x_buffer + max([x + y for x, y in list(zip(phototime, phototimelowererrs))]), -x_buffer + min([x - y for x, y in list(zip(phototime, phototimeuppererrs))])),
            y_range = (0.5 + max([x + y for x, y in list(zip(photoAB, photoABerrs))]), -0.5 + min([x - y for x, y in list(zip(photoAB, photoABerrs))])))
        p1.add_tools(hover)

        err_xs = []
        err_ys = []

        for x, y, xlowerr, xupperr, yerr in list(zip(phototime, photoAB, phototimelowererrs, phototimeuppererrs, photoABerrs)):
            err_xs.append((x - xlowerr, x + xupperr))
            err_ys.append((y - yerr, y + yerr))

        bandset = set(photoband)
        bandset = [i for (j, i) in sorted(list(zip(list(map(bandaliasf, bandset)), bandset)))]

        for band in bandset:
            bandname = bandaliasf(band)
            indb = [i for i, j in enumerate(photoband) if j == band]
            indt = [i for i, j in enumerate(phototype) if not j]
            # Should always have upper error if have lower error.
            indnex = [i for i, j in enumerate(phototimelowererrs) if j == 0.]
            indyex = [i for i, j in enumerate(phototimelowererrs) if j > 0.]
            indney = [i for i, j in enumerate(photoABerrs) if j == 0.]
            indyey = [i for i, j in enumerate(photoABerrs) if j > 0.]
            indne = set(indb).intersection(indt).intersection(indney).intersection(indnex)
            indye = set(indb).intersection(indt).intersection(set(indyey).union(indnex))

            noerrorlegend = bandname if len(indne) == 0 else ''

            source = ColumnDataSource(
                data = dict(
                    x = [phototime[i] for i in indne],
                    y = [photoAB[i] for i in indne],
                    err = [photoABerrs[i] for i in indne],
                    desc = [photoband[i] for i in indne],
                    instr = [photoinstru[i] for i in indne],
                    src = [photosource[i] for i in indne]
                )
            )
            p1.circle('x', 'y', source = source, color=bandcolorf(band), fill_color="white", legend=noerrorlegend, size=4)

            source = ColumnDataSource(
                data = dict(
                    x = [phototime[i] for i in indye],
                    y = [photoAB[i] for i in indye],
                    err = [photoABerrs[i] for i in indye],
                    desc = [photoband[i] for i in indye],
                    instr = [photoinstru[i] for i in indye],
                    src = [photosource[i] for i in indye]
                )
            )
            p1.multi_line([err_xs[x] for x in indye], [err_ys[x] for x in indye], color=bandcolorf(band))
            p1.circle('x', 'y', source = source, color=bandcolorf(band), legend=bandname, size=4)

            upplimlegend = bandname if len(indye) == 0 and len(indne) == 0 else ''

            indt = [i for i, j in enumerate(phototype) if j]
            ind = set(indb).intersection(indt)
            p1.inverted_triangle([phototime[x] for x in ind], [photoAB[x] for x in ind],
                color=bandcolorf(band), legend=upplimlegend, size=7)

    if spectraavail and dohtml and args.writehtml:
        spectrumwave = []
        spectrumflux = []
        spectrumerrs = []
        spectrummjdmax = []
        hasepoch = False
        hasmjdmax = False
        if 'redshift' in catalog[entry]:
            z = float(catalog[entry]['redshift'][0]['value'])
        for spectrum in catalog[entry]['spectra']:
            spectrumdata = deepcopy(spectrum['data'])
            spectrumdata = [x for x in spectrumdata if is_number(x[1]) and not isnan(float(x[1]))]
            specrange = range(len(spectrumdata))

            if 'deredshifted' in spectrum and spectrum['deredshifted'] and 'redshift' in catalog[entry]:
                spectrumwave.append([float(spectrumdata[x][0])*(1.0 + z) for x in specrange])
            else:
                spectrumwave.append([float(spectrumdata[x][0]) for x in specrange])

            spectrumflux.append([float(spectrumdata[x][1]) for x in specrange])
            if 'errorunit' in spectrum:
                spectrumerrs.append([float(spectrumdata[x][2]) for x in specrange])
                spectrumerrs[-1] = [x if is_number(x) and not isnan(float(x)) else 0. for x in spectrumerrs[-1]]

            if 'timeunit' in spectrum and 'time' in spectrum:
                hasepoch = True

            mjdmax = ''
            if spectrum['timeunit'] == 'MJD' and 'redshift' in catalog[entry]:
                if 'maxdate' in catalog[entry]:
                    mjdmax = astrotime(catalog[entry]['maxdate'][0]['value'].replace('/', '-')).mjd
                if mjdmax:
                    hasmjdmax = True
                    mjdmax = (float(spectrum['time']) - mjdmax) / (1.0 + float(catalog[entry]['redshift'][0]['value']))
                    spectrummjdmax.append(mjdmax)

        nspec = len(catalog[entry]['spectra'])
        
        spectrumscaled = deepcopy(spectrumflux)
        for f, flux in enumerate(spectrumscaled):
            mean = numpy.std(flux)
            spectrumscaled[f] = [x/mean for x in flux]

        y_height = 0.
        y_offsets = [0. for x in range(nspec)]
        for i in reversed(range(nspec)):
            y_offsets[i] = y_height
            if (i-1 >= 0 and 'time' in catalog[entry]['spectra'][i] and 'time' in catalog[entry]['spectra'][i-1]
                and catalog[entry]['spectra'][i]['time'] == catalog[entry]['spectra'][i-1]['time']):
                    ydiff = 0
            else:
                ydiff = max(spectrumscaled[i]) - min(spectrumscaled[i])
            spectrumscaled[i] = [j + y_height for j in spectrumscaled[i]]
            y_height += ydiff

        maxsw = max(map(max, spectrumwave))
        minsw = min(map(min, spectrumwave))
        maxfl = max(map(max, spectrumscaled))
        minfl = min(map(min, spectrumscaled))
        maxfldiff = max(map(operator.sub, list(map(max, spectrumscaled)), list(map(min, spectrumscaled))))
        x_buffer = 0.0 #0.1*(maxsw - minsw)
        x_range = [-x_buffer + minsw, x_buffer + maxsw]
        y_buffer = 0.1*maxfldiff
        y_range = [-y_buffer + minfl, y_buffer + maxfl]

        for f, flux in enumerate(spectrumscaled):
            spectrumscaled[f] = [x - y_offsets[f] for x in flux]

        tt2 = []
        if 'redshift' in catalog[entry]:
            tt2 += [ ("λ (rest)", "@xrest{1.1} Å") ]
        tt2 += [
                ("λ (obs)", "@x{1.1} Å"),
                ("Flux", "@yorig"),
                ("Flux unit", "@fluxunit")
               ]

        if hasepoch:
            tt2 += [ ("Epoch (" + spectrum['timeunit'] + ")", "@epoch{1.11}") ]

        if hasmjdmax:
            tt2 += [ ("Rest days to max", "@mjdmax{1.11}") ]

        tt2 += [ ("Source", "@src") ]
        hover2 = HoverTool(tooltips = tt2)

        p2 = Figure(title='Spectra for ' + eventname, x_axis_label=label_format('Observed Wavelength (Å)'),
            y_axis_label=label_format('Flux (scaled)' + (' + offset'
            if (nspec > 1) else '')), x_range = x_range, tools = tools, 
            y_range = y_range)
        p2.add_tools(hover2)

        sources = []
        for i in range(len(spectrumwave)):
            sl = len(spectrumscaled[i])

            data = dict(
                x0 = spectrumwave[i],
                y0 = spectrumscaled[i],
                yorig = spectrumflux[i],
                fluxunit = [label_format(catalog[entry]['spectra'][i]['fluxunit'])]*sl,
                x = spectrumwave[i],
                y = [y_offsets[i] + j for j in spectrumscaled[i]],
                src = [catalog[entry]['spectra'][i]['source']]*sl
            )
            if 'redshift' in catalog[entry]:
                data['xrest'] = [x/(1.0 + z) for x in spectrumwave[i]]
            if hasepoch:
                data['epoch'] = [catalog[entry]['spectra'][i]['time'] for j in spectrumscaled[i]]
            if hasmjdmax:
                data['mjdmax'] = [spectrummjdmax[i] for j in spectrumscaled[i]]
            sources.append(ColumnDataSource(data))
            p2.line('x', 'y', source=sources[i], color=mycolors[i % len(mycolors)], line_width=2)

        if 'redshift' in catalog[entry]:
            minredw = minsw/(1.0 + z)
            maxredw = maxsw/(1.0 + z)
            p2.extra_x_ranges = {"other wavelength": Range1d(start=minredw, end=maxredw)}
            p2.add_layout(LinearAxis(axis_label ="Restframe Wavelength (Å)", x_range_name="other wavelength"), 'above')

        sdicts = dict(zip(['s'+str(x) for x in range(len(sources))], sources))
        callback = CustomJS(args=sdicts, code="""
            var yoffs = [""" + ','.join([str(x) for x in y_offsets]) + """];
            for (s = 0; s < """ + str(len(sources)) + """; s++) {
                var data = eval('s'+s).get('data');
                var redshift = """ + str(z if 'redshift' in catalog[entry] else 0.) + """;
                if (!('binsize' in data)) {
                    data['binsize'] = 1.0
                }
                if (!('spacing' in data)) {
                    data['spacing'] = 1.0
                }
                if (cb_obj.get('title') == 'Spacing') {
                    data['spacing'] = cb_obj.get('value');
                } else {
                    data['binsize'] = cb_obj.get('value');
                }
                var f = data['binsize']
                var space = data['spacing']
                var x0 = data['x0'];
                var y0 = data['y0'];
                var dx0 = x0[1] - x0[0];
                var yoff = space*yoffs[s];
                data['x'] = [x0[0] - 0.5*Math.max(0., f - dx0)];
                data['xrest'] = [(x0[0] - 0.5*Math.max(0., f - dx0))/(1.0 + redshift)];
                data['y'] = [y0[0] + yoff];
                var xaccum = 0.;
                var yaccum = 0.;
                for (i = 0; i < x0.length; i++) {
                    var dx;
                    if (i == 0) {
                        dx = x0[i+1] - x0[i];
                    } else {
                        dx = x0[i] - x0[i-1];
                    }
                    xaccum += dx;
                    yaccum += y0[i]*dx;
                    if (xaccum >= f) {
                        data['x'].push(data['x'][data['x'].length-1] + xaccum);
                        data['xrest'].push(data['x'][data['x'].length-1]/(1.0 + redshift));
                        data['y'].push(yaccum/xaccum + yoff);
                        xaccum = 0.;
                        yaccum = 0.;
                    }
                }
                eval('s'+s).trigger('change');
            }
        """)

        binslider = Slider(start=0, end=20, value=1, step=0.5, title=label_format("Bin size (Angstrom)"), callback=callback)
        spacingslider = Slider(start=0, end=2, value=1, step=0.02, title=label_format("Spacing"), callback=callback)

    hasimage = False
    skyhtml = ''
    if 'ra' in catalog[entry] and 'dec' in catalog[entry] and args.collecthosts:
        snra = catalog[entry]['ra'][0]['value']
        sndec = catalog[entry]['dec'][0]['value']
        c = coord(ra=snra, dec=sndec, unit=(un.hourangle, un.deg))

        if 'lumdist' in catalog[entry] and float(catalog[entry]['lumdist'][0]['value']) > 0.:
            if 'host' in catalog[entry] and catalog[entry]['host'][0]['value'] == 'Milky Way':
                sdssimagescale = max(0.05,0.04125/float(catalog[entry]['lumdist'][0]['value']))
            else:
                sdssimagescale = max(0.05,20.6265/float(catalog[entry]['lumdist'][0]['value']))
        else:
            if 'host' in catalog[entry] and catalog[entry]['host'][0]['value'] == 'Milky Way':
                sdssimagescale = 0.0006
            else:
                sdssimagescale = 0.3
        dssimagescale = 0.13889*sdssimagescale
        #At the moment, no way to check if host is in SDSS footprint without comparing to empty image, which is only possible at fixed angular resolution.
        sdssimagescale = 0.3

        imgsrc = ''
        hasimage = True
        if eventname in hostimgdict:
            imgsrc = hostimgdict[eventname]
        else:
            try:
                response = urllib.request.urlopen('http://skyservice.pha.jhu.edu/DR12/ImgCutout/getjpeg.aspx?ra='
                    + str(c.ra.deg) + '&dec=' + str(c.dec.deg) + '&scale=' + sdssimagescale + '&width=500&height=500&opt=G')
            except:
                hasimage = False
            else:
                with open(outdir + fileeventname + '-host.jpg', 'wb') as f:
                    f.write(response.read())
                imgsrc = 'SDSS'

            if hasimage and filecmp.cmp(outdir + fileeventname + '-host.jpg', outdir + 'missing.jpg'):
                hasimage = False

            if not hasimage:
                hasimage = True
                url = ("http://skyview.gsfc.nasa.gov/current/cgi/runquery.pl?Position=" + str(urllib.parse.quote_plus(snra + " " + sndec)) +
                       "&coordinates=J2000&coordinates=&projection=Tan&pixels=500&size=" + dssimagescale + "&float=on&scaling=Log&resolver=SIMBAD-NED" +
                       "&Sampler=_skip_&Deedger=_skip_&rotation=&Smooth=&lut=colortables%2Fb-w-linear.bin&PlotColor=&grid=_skip_&gridlabels=1" +
                       "&catalogurl=&CatalogIDs=on&RGB=1&survey=DSS2+IR&survey=DSS2+Red&survey=DSS2+Blue&IOSmooth=&contour=&contourSmooth=&ebins=null")

                response = urllib.request.urlopen(url)
                bandsoup = BeautifulSoup(response, "html5lib")
                images = bandsoup.findAll('img')
                imgname = ''
                for image in images:
                    if "Quicklook RGB image" in image.get('alt', ''):
                        imgname = image.get('src', '').split('/')[-1]

                if imgname:
                    try:
                        response = urllib.request.urlopen('http://skyview.gsfc.nasa.gov/tempspace/fits/' + imgname)
                    except:
                        hasimage = False
                    else:
                        with open(outdir + fileeventname + '-host.jpg', 'wb') as f:
                            f.write(response.read())
                        imgsrc = 'DSS'
                else:
                    hasimage = False

        if hasimage:
            if imgsrc == 'SDSS':
                hostimgs.append([eventname, 'SDSS'])
                skyhtml = ('<a href="http://skyserver.sdss.org/DR12/en/tools/chart/navi.aspx?opt=G&ra='
                    + str(c.ra.deg) + '&dec=' + str(c.dec.deg) + '&scale=0.15"><img style="margin:5px;" src="' + fileeventname + '-host.jpg" width=250></a>')
            elif imgsrc == 'DSS':
                hostimgs.append([eventname, 'DSS'])
                url = ("http://skyview.gsfc.nasa.gov/current/cgi/runquery.pl?Position=" + str(urllib.parse.quote_plus(snra + " " + sndec)) +
                       "&coordinates=J2000&coordinates=&projection=Tan&pixels=500&size=0.041666&float=on&scaling=Log&resolver=SIMBAD-NED" +
                       "&Sampler=_skip_&Deedger=_skip_&rotation=&Smooth=&lut=colortables%2Fb-w-linear.bin&PlotColor=&grid=_skip_&gridlabels=1" +
                       "&catalogurl=&CatalogIDs=on&RGB=1&survey=DSS2+IR&survey=DSS2+Red&survey=DSS2+Blue&IOSmooth=&contour=&contourSmooth=&ebins=null")
                skyhtml = ('<a href="' + url + '"><img style="margin:5px;" src="' + fileeventname + '-host.jpg" width=250></a>')
        else:
            hostimgs.append([eventname, 'None'])

    plotlink = "sne/" + fileeventname + "/"
    if hasimage:
        hostlink = "<a class='hhi' href='" + plotlink + "' target='_blank'></a>"
    else:
        hostlink = "<a class='nhi' href='" + plotlink + "' target='_blank'></a>"

    if 'host' not in catalog[entry]:
        if hasimage:
            catalog[entry]['host'] = [{'value':hostlink}]
    else:
        catalog[entry]['host'][0]['value'] = hostlink + " " + catalog[entry]['host'][0]['value']

    if dohtml and args.writehtml:
    #if (photoavail and spectraavail) and dohtml and args.writehtml:
        if photoavail and spectraavail:
            p = VBox(HBox(p1),HBox(p2,VBox(binslider,spacingslider)), width=900)
        elif photoavail:
            p = p1
        elif spectraavail:
            p = VBox(HBox(p2,VBox(binslider,spacingslider)), width=900)

        if photoavail or spectraavail:
            html = file_html(p, CDN, eventname)
        else:
            html = '<html><title></title><body></body></html>'

        #script, div = components(p)
        #with open(outdir + eventname + "-script.js", "w") as fff:
        #    script = '\n'.join(script.splitlines()[2:-1])
        #    fff.write(script)
        #with open(outdir + eventname + "-div.html", "w") as fff:
        #    fff.write(div)
        html = re.sub(r'(\<\/title\>)', r'''\1\n
            <base target="_parent" />\n
            <link rel="stylesheet" href="event.css" type="text/css">\n
            <script type="text/javascript">\n
                if(top==self)\n
                this.location="''' + eventname + '''"\n
            </script>'''
            , html)

        repfolder = get_rep_folder(catalog[entry])
        html = re.sub(r'(\<\/body\>)', '<div style="width:100%; text-align:center;">' + r'<a class="event-download" href="' +
            linkdir + fileeventname + r'.json" download>' + r'&#11015; Download all event data &#11015;' +
            r'</a></div>\n\1', html)

        newhtml = r'<div class="event-tab-div"><h3 class="event-tab-title">Event metadata</h3><table class="event-table"><tr><th width=100px class="event-cell">Quantity</th><th class="event-cell">Value<sup>sources</sup></th></tr>\n'
        for key in columnkey:
            if key in catalog[entry] and key not in eventignorekey and len(catalog[entry][key]) > 0:
                newhtml = newhtml + r'<tr><td class="event-cell">' + eventpageheader[key] + r'</td><td width=250px class="event-cell">'
                
                if isinstance(catalog[entry][key], str):
                    newhtml = newhtml + re.sub('<[^<]+?>', '', catalog[entry][key])
                else:
                    for r, row in enumerate(catalog[entry][key]):
                        if 'value' in row and 'source' in row:
                            sources = row['source'].split(',')
                            sourcehtml = ''
                            for s, source in enumerate(sources):
                                if source == 'D':
                                    sourcehtml = sourcehtml + (',' if s > 0 else '') + source
                                else:
                                    sourcehtml = sourcehtml + (',' if s > 0 else '') + r'<a href="#source' + source + r'">' + source + r'</a>'
                            newhtml = newhtml + (r'<br>' if r > 0 else '') + row['value'] + r'<sup>' + sourcehtml + r'</sup>'
                        elif isinstance(row, str):
                            newhtml = newhtml + (r'<br>' if r > 0 else '') + row.strip()

                newhtml = newhtml + r'</td></tr>\n'
        newhtml = newhtml + r'</table><em>D = Derived value</em></div>\n\1'
        html = re.sub(r'(\<\/body\>)', newhtml, html)

        if 'sources' in catalog[entry] and len(catalog[entry]['sources']):
            newhtml = r'<div class="event-tab-div"><h3 class="event-tab-title">Sources of data</h3><table class="event-table"><tr><th width=30px class="event-cell">ID</th><th class="event-cell">Source</th></tr>\n'
            for source in catalog[entry]['sources']:
                newhtml = (newhtml + r'<tr><td class="event-cell" id="source' + source['alias'] + '">' + source['alias'] +
                    r'</td><td width=250px class="event-cell">' + (('<a href="' + source['url'] + '">') if 'url' in source else '') +
                    source['name'].encode('ascii', 'xmlcharrefreplace').decode("utf-8") +
                    (r'</a>' if 'url' in source else '') +
                    r'</td></tr>\n')
            newhtml = newhtml + r'</table></div>'

            if hasimage:
                newhtml = newhtml + '<div class="event-tab-div"><h3 class="event-tab-title">Host Image</h3>' + skyhtml + '</div>'

        newhtml = newhtml + r'\n\1'

        html = re.sub(r'(\<\/body\>)', newhtml, html)

        with open(outdir + fileeventname + ".html", "w") as fff:
            fff.write(html)

    # Necessary to clear Bokeh state
    reset_output()

    #if spectraavail and dohtml:
    #    sys.exit()

    #if fcnt > 100:
    #    sys.exit()

    # Save this stuff because next line will delete it.
    if args.writecatalog:
        if 'photoplot' in catalog[entry]:
            snepages.append(catalog[entry]['aliases'] + ['https://sne.space/' + catalog[entry]['photoplot']])

        if 'sources' in catalog[entry]:
            lsourcedict = {}
            for sourcerow in catalog[entry]['sources']:
                strippedname = re.sub('<[^<]+?>', '', sourcerow['name'].encode('ascii','xmlcharrefreplace').decode("utf-8"))
                alias = sourcerow['alias']
                if 'bibcode' in sourcerow and 'secondary' not in sourcerow:
                    lsourcedict[alias] = {'bibcode':sourcerow['bibcode'], 'count':0}
                if strippedname in sourcedict:
                    sourcedict[strippedname] += 1
                else:
                    sourcedict[strippedname] = 1

            for key in catalog[entry].keys():
                if isinstance(catalog[entry][key], list):
                    for row in catalog[entry][key]:
                        if 'source' in row:
                            for lsource in lsourcedict:
                                if lsource in row['source'].split(','):
                                    if key == 'spectra':
                                        lsourcedict[lsource]['count'] += 10
                                    else:
                                        lsourcedict[lsource]['count'] += 1

            ssources = sorted(list(lsourcedict.values()), key=lambda x: x['count'], reverse=True)
            if ssources:
                seemorelink = ''
                if len(ssources) > 3:
                    seemorelink = "<br><a href='sne/" + fileeventname + "/'>(See full list)</a>"
                catalog[entry]['references'] = ', '.join(["<a href='http://adsabs.harvard.edu/abs/" + y['bibcode'] + "'>" + y['bibcode'] + "</a>"
                    for y in ssources[:3]]) + seemorelink

        nophoto.append(catalog[entry]['numphoto'] < 3)

        nospectra.append(catalog[entry]['numspectra'] == 0)

        totalphoto += catalog[entry]['numphoto']
        totalspectra += catalog[entry]['numspectra']

        # Delete unneeded data from catalog, add blank entries when data missing.
        catalogcopy[entry] = OrderedDict()
        for col in columnkey:
            if col in catalog[entry]:
                catalogcopy[entry][col] = catalog[entry][col]
            else:
                catalogcopy[entry][col] = None

        del catalog[entry]

    if args.test and spectraavail and photoavail:
        break

# Write it all out at the end
if args.writecatalog and not args.eventlist:
    catalog = catalogcopy

    #Write the MD5 checksums
    jsonstring = json.dumps(md5s, separators=(',',':'))
    with open(outdir + 'md5s.json' + testsuffix, 'w') as f:
        f.write(jsonstring)

    #Write the host image info
    jsonstring = json.dumps(hostimgs, separators=(',',':'))
    with open(outdir + 'hostimgs.json' + testsuffix, 'w') as f:
        f.write(jsonstring)

    # Make a few small files for generating charts
    with open(outdir + 'snepages.csv' + testsuffix, 'w') as f:
        csvout = csv.writer(f, quotechar='"', quoting=csv.QUOTE_ALL)
        for row in snepages:
            csvout.writerow(row)

    with open(outdir + 'sources.csv' + testsuffix, 'w') as f:
        sortedsources = sorted(list(sourcedict.items()), key=operator.itemgetter(1), reverse=True)
        csvout = csv.writer(f)
        csvout.writerow(['Source','Number'])
        for source in sortedsources:
            csvout.writerow(source)

    nophoto = sum(nophoto)
    hasphoto = len(catalog) - nophoto
    with open(outdir + 'pie.csv' + testsuffix, 'w') as f:
        csvout = csv.writer(f)
        csvout.writerow(['Category','Number'])
        csvout.writerow(['Has light curve', hasphoto])
        csvout.writerow(['No light curve', nophoto])

    nospectra = sum(nospectra)
    hasspectra = len(catalog) - nospectra
    with open(outdir + 'spectra-pie.csv' + testsuffix, 'w') as f:
        csvout = csv.writer(f)
        csvout.writerow(['Category','Number'])
        csvout.writerow(['Has spectra', hasspectra])
        csvout.writerow(['No spectra', nospectra])

    with open(outdir + 'hasphoto.html' + testsuffix, 'w') as f:
        f.write("{:,}".format(hasphoto))
    with open(outdir + 'hasspectra.html' + testsuffix, 'w') as f:
        f.write("{:,}".format(hasspectra))
    with open(outdir + 'snecount.html' + testsuffix, 'w') as f:
        f.write("{:,}".format(len(catalog)))
    with open(outdir + 'photocount.html' + testsuffix, 'w') as f:
        f.write("{:,}".format(totalphoto))
    with open(outdir + 'spectracount.html' + testsuffix, 'w') as f:
        f.write("{:,}".format(totalspectra))

    ctypedict = dict()
    for entry in catalog:
        cleanedtype = ''
        if 'claimedtype' in catalog[entry] and catalog[entry]['claimedtype']:
            maxsources = 0
            for ct in catalog[entry]['claimedtype']:
                sourcecount = len(ct['source'].split(','))
                if sourcecount > maxsources:
                    maxsources = sourcecount
                    cleanedtype = ct['value'].strip('?* ')
        if not cleanedtype:
            cleanedtype = 'Unknown'
        if cleanedtype in ctypedict:
            ctypedict[cleanedtype] += 1
        else:
            ctypedict[cleanedtype] = 1
    sortedctypes = sorted(list(ctypedict.items()), key=operator.itemgetter(1), reverse=True)
    with open(outdir + 'types.csv' + testsuffix, 'w') as f:
        csvout = csv.writer(f)
        csvout.writerow(['Type','Number'])
        for ctype in sortedctypes:
            csvout.writerow(ctype)

    # Convert to array since that's what datatables expects
    catalog = list(catalog.values())

    jsonstring = json.dumps(catalog, separators=(',',':'))
    with open(outdir + 'catalog.min.json' + testsuffix, 'w') as f:
        f.write(jsonstring)

    jsonstring = json.dumps(catalog, indent='\t', separators=(',',':'))
    with open(outdir + 'catalog.json' + testsuffix, 'w') as f:
        f.write(jsonstring)

    with open(outdir + 'catalog.html' + testsuffix, 'w') as f:
        f.write('<table id="example" class="display" cellspacing="0" width="100%">\n')
        f.write('\t<thead>\n')
        f.write('\t\t<tr>\n')
        for h in header:
            f.write('\t\t\t<th class="' + h + '" title="' + titles[h] + '">' + header[h] + '</th>\n')
        f.write('\t\t</tr>\n')
        f.write('\t</thead>\n')
        f.write('\t<tfoot>\n')
        f.write('\t\t<tr>\n')
        for h in header:
            f.write('\t\t\t<th class="' + h + '" title="' + titles[h] + '">' + header[h] + '</th>\n')
        f.write('\t\t</tr>\n')
        f.write('\t</thead>\n')
        f.write('</table>\n')

    with open(outdir + 'catalog.min.json', 'rb') as f_in, gzip.open(outdir + 'catalog.min.json.gz', 'wb') as f_out:
        shutil.copyfileobj(f_in, f_out)

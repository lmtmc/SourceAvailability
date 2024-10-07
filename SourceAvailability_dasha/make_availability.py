import datetime
import os
import pickle
import re
import sys
import time
import pickletools
from collections import OrderedDict
import numpy as np
from astropy import units as u
from astropy.coordinates import AltAz, SkyCoord
from astropy.coordinates import EarthLocation
from astropy.time import Time, TimeDelta
import plotly.express as px
import plotly.graph_objects as go
from .color_constants import colors


# a source class
class Source:
    astroTime = []
    altAz = 0
    day_start = 0
    day_end = 0
    day_names = []

    def __init__(self, name, ra, dec, coordsys, pid, pin, instrument, itime, rank):
        self.lstup = None
        self.name = name
        self.ra = ra
        self.dec = dec
        self.coordsys = coordsys
        self.pId = pid
        self.piName = pin
        self.instrument = instrument
        self.integTime = itime
        self.rank = rank
        if coordsys == 'Galactic':
            self.coord = SkyCoord(self.ra, self.dec, unit='deg', frame='galactic')
        else:
            self.coord = SkyCoord(self.ra, self.dec, unit='deg')
        self.az = 0.
        self.el = 0.
        self.up = 0

    def __str__(self):
        return self.pId + ',' + self.piName + ',' + self.name + ',' + self.ra + ',' + self.dec

    def __repr__(self):
        return self.pId + ',' + self.piName + ',' + self.name + ',' + self.ra + ',' + self.dec

    def createUptimes(self):
        nx = Source.astroTime.shape[0]
        ny = Source.astroTime.shape[1]
        self.az = np.zeros((nx, ny))
        self.el = np.zeros((nx, ny))
        self.up = np.zeros((nx, ny), dtype='int')
        self.az = self.az.flatten()
        self.el = self.el.flatten()
        self.up = self.up.flatten()
        bb = self.coord.transform_to(Source.altAz)
        self.az = bb.az.deg
        self.el = bb.alt.deg
        w = np.where(np.logical_and(self.el >= 25., self.el <= 80))[0]
        self.up[w] = 1
        self.lstup = np.zeros(24)
        if self.up.any():
            at = Source.astroTime.flatten()
            lst = (at[w].sidereal_time('mean').hour % 24.).astype(int)
            unique, counts = np.unique(lst, return_counts=True)
            self.lstup[unique] = 0.25 * counts
        # print self.lstup
        self.az = self.az.reshape(nx, ny)
        self.el = self.el.reshape(nx, ny)
        self.up = self.up.reshape(nx, ny)


# a project class
class Project:
    def __init__(self, pId):
        self.pId = pId
        self.sourceList = []
        self.uberUp = 0

    def __str__(self):
        return self.pId

    def __repr__(self):
        return self.pId + ' ' + str(self.sourceList)

    def listSources(self):
        print('')
        print((len(self.sourceList), 'Sources for Project:', self.pId))
        for i, s in enumerate(self.sourceList):
            print(('  ', s.name, s.ra, s.dec, s.coord.to_string('hmsdms'), s.pId))
        print('')

    # this method uses the Source class to generate the el and up
    # arrays for each source in the project
    def createUptimes(self):
        for i, s in enumerate(self.sourceList):
            print(("PID:" + str(self.pId) +
                   " - Creating uptimes for source " + str(i + 1) +
                   " of " + str(len(self.sourceList)) + "\r"))
            s.createUptimes()

    def createUberUp(self, astroTime):
        nx = astroTime.shape[0]
        ny = astroTime.shape[1]
        self.uberUp = np.zeros((nx, ny), dtype='int')
        for s in self.sourceList:
            self.uberUp += s.up[:, 0:ny]

    # make a classical uptimes plot for all the sources in the project
    def plotUptimes(self, astroTime, day_names, day, source_range):
        fig = go.Figure()
        date = day_names[day]
        hour_length = len(astroTime[:, day])
        hour_range = (astroTime[hour_length - 1, day].jd - astroTime[0, day].jd) * 24

        ut = astroTime[:, day].sidereal_time('mean').hour
        w = np.where(ut > ut[-1])[0]
        ut[w] = ut[w] - 24.
        ut_range = [ut.min(), ut.max()]
        title = (date + ' - ' + self.pId)

        for i, s in enumerate(self.sourceList[source_range[0]:source_range[1]]):
            fig.add_trace(go.Scatter(x=ut, y=s.el[:, day], name=s.name))

        # draw a fill shading in above 80 and below 25 deg
        fig.add_trace(go.Scatter(x=ut_range, y=[80, 80], fill=None, line_color='lightyellow', showlegend=False))
        fig.add_trace(go.Scatter(x=ut_range, y=[90, 90], fill='tonexty', line_color='lightyellow', showlegend=False))

        fig.add_trace(go.Scatter(x=ut_range, y=[25, 25], fill=None, line_color='lightyellow', showlegend=False))
        fig.add_trace(go.Scatter(x=ut_range, y=[0, 0], fill='tonexty', line_color='lightyellow', showlegend=False))

        fig.update_layout(title=title,
                          xaxis=dict(title='LST', range=ut_range),
                          yaxis=dict(title='Source Elevation [deg.] -- Sources ' + str(source_range[0] + 1)
                                           + ' to ' + str(source_range[1]),
                                     range=[0, 90]),
                          legend_title='Source Name',
                          height=600, )

        return fig

    def plotUberUp(self, astroTime, day_names, day_start, day_end):
        if isinstance(self.uberUp, int):
            self.createUberUp(astroTime)
        title = self.pId
        hour_range = len(astroTime[:, 0]) / 4
        t00 = astroTime[0, 0]
        s00 = t00.value
        t00 = int(s00.split('T')[1].split(':')[0])
        y_val = np.linspace(0, len(astroTime[:, 0]), 10)
        y_text = np.linspace(0 + t00, hour_range + t00, 10).astype(int)
        
        uberUp = self.uberUp[:, day_start:day_end]

        fig = px.imshow(uberUp, aspect='auto')
        l = day_end - day_start + 1
        ll = [day_start + i * int(l / 6.) for i in range(7)]
        fig.update_layout(title=title,
                          xaxis=dict(tickmode='array',
                                     tickvals=ll,
                                     ticktext=[day_names[i] for i in ll],
                                     tickfont=dict(size=18)),
                          yaxis=dict(tickmode='array',
                                     tickvals=y_val,
                                     ticktext=y_text,
                                     title_text='UT'),
                          height=600)
        return fig


def makeAstroTime(ymd0, ymd1, nhours=13, nsubhours=4, ut0=" 00:00:0", debug=True):
    # convert year at midnight UT to unix time
    # step by 1 day across for 181 days (1 for ncols)
    # step by 1/4 hour down for 13 hours (1/rowed for nrows)
    t0 = time.mktime(datetime.datetime.strptime(ymd0 + ut0, "%Y/%m/%d %H:%M:%S").timetuple())
    t1 = time.mktime(datetime.datetime.strptime(ymd1 + ut0, "%Y/%m/%d %H:%M:%S").timetuple())
    ndays = int((t1 - t0) / 24 / 3600)
    ncols = ndays
    nrows = nhours
    rowd = nsubhours
    if debug:
        print(('start time at', datetime.datetime.fromtimestamp(t0).isoformat(), 'for', ncols, 'days', nrows,
               'hours per day every', 1. / float(rowd), 'hour'))

    tm0 = datetime.datetime.fromtimestamp(t0).isoformat()
    ot0 = Time(tm0, format='isot', scale='utc', location=getLMT())
    dt = TimeDelta(3600 / rowd, format='sec')
    obstime = ot0 + dt * np.linspace(0, 24 * rowd * ncols - 1, 24 * rowd * ncols)
    obstime = obstime.reshape(ncols, 24 * rowd)
    obstime = obstime[:, 0:nrows * rowd].transpose()
    if debug:
        print(('obs time from', str(obstime[0][0]), 'to', str(obstime[-1][-1])))
    return obstime


# sets the LMT as an EarthLocation object
def getLMT():
    lat = 18.986111 * u.deg
    lon = -97.31458333 * u.deg
    height = 4640. * u.m
    return EarthLocation(lat=lat, lon=lon, height=height)


def populateProjects(LMT, astroTime, projectsFile='', targetsFile='targets.csv', debug=True):
    # set the Source global variables
    Source.astroTime = astroTime
    at = astroTime.flatten()
    Source.altAz = AltAz(location=LMT, obstime=at)
    Source.day_start = 0
    Source.day_end = len(Source.astroTime[0, :]) - 1

    # read targets file
    if debug:
        print('read targets file', targetsFile)
    try:
        # skip the first row

        if np.lib.NumpyVersion(np.version.version) >= '1.14.0':
            filedata = np.recfromcsv(targetsFile, names=True, autostrip=True, dtype=None, skip_header=0,
                                     encoding='latin_1')
        else:
            filedata = np.recfromcsv(targetsFile, names=True, autostrip=True, dtype=None, skip_header=0, unpack=True)
        proposalId = filedata['proposal_id']
    
        if 'ranking' in filedata.dtype.fields:
            print('rank from ranking')
            ranking = filedata['ranking']
        elif 'rank' in filedata.dtype.fields:
            print('rank from rank')
            ranking = filedata['rank']
        else:
            print('rank from none')
            ranking = np.array(['A'] * len(proposalId))
        piName = filedata['name_pi']
        sourceName = filedata['source']
        sourceRa = filedata['ra']
        sourceDec = filedata['dec']
        sourceSys = filedata['system']
        instrument = filedata['instrument']
        integTime = filedata['time']
        priority = filedata['priority']
    except Exception as e:
        print(e)
    # prepend 0 to single digit proporsal num
    for i, p in enumerate(proposalId):
        mo = re.search('(?<=-)\d+', p)
        if mo and mo.start(0) > 0:
            if len(mo.group(0)) == 1:
                p = p[:mo.start(0)] + '0' + mo.group(0)
            else:
                p = p[:mo.start(0)] + mo.group(0)
            proposalId[i] = p
    # create projects
    projects = [Project(pid) for pid in list(OrderedDict.fromkeys(proposalId))]
    # create sources
    sources = [Source(name, ra, dec, coordsys, pid, pin, inst, itime, rank) for name, ra, dec, coordsys, pid, pin, inst, itime, rank in
               zip(sourceName, sourceRa, sourceDec, sourceSys, proposalId, piName, instrument, integTime, ranking)]

    # assign sources to projects
    for p in projects:
        p.sourceList = [s for s in sources if s.pId == p.pId]
        # print('sourcelist:', p.listSources())
    # generate uptimes or read sources pickle
    if (len(projectsFile) == 0) or not os.path.isfile(projectsFile):

        # loop through sources and generate uptimes matrices
        for i, s in enumerate(sources):
            print(('process source', i + 1, 'of', len(sources)))
            s.createUptimes()

        # pickle the list of projects
        with open(projectsFile, 'wb') as output:
            try:
                pickle.dump(projects, output, pickle.HIGHEST_PROTOCOL, encoding='latin_1')
            except:
                pickle.dump(projects, output, pickle.HIGHEST_PROTOCOL)

    else:
        # read projects file
        if debug:
            print(('read projects file', projectsFile))
        with open(projectsFile, 'rb') as input:
            op, fst, snd = next(pickletools.genops(input))
            if op.name == 'PROTO':
                proto = fst
            else:
                proto = 2
            if debug:
                print(('pickle proto', proto))
            if sys.version_info.major <= 2 and proto >= 5:
                print('incompatible pickle proto', proto)
                print('remove pickle file and regenerate')
                sys.exit(-1)
            try:
                projects = pickle.load(input, encoding='latin1')
            except:
                projects = pickle.load(input)
            # sys.version_info.major = 3
            if sys.version_info.major > 2 and proto < 5:
                for p in projects:
                    p.pId = p.pId.decode()
                    for i, s in enumerate(p.sourceList):
                        p.sourceList[i].name = s.name.decode()
                        p.sourceList[i].pId = s.pId.decode()
                        p.sourceList[i].piName = s.piName.decode()
                        p.sourceList[i].instrument = s.instrument.decode()
                        p.sourceList[i].rank = s.rank.decode()
                        

    return projects, sources


def createSeasonPlot(astroTime, day_names, projects, day_start, day_end):
    # create the vector of date values
    dTime = astroTime[0, day_start:day_end]
    date = []
    for i in np.arange(len(dTime)):
        date.append(dTime[i].value[:10])
    nDates = len(date)
    nProjects = len(projects)
    seasonData = np.zeros((nProjects, nDates))
    yl = []
    for i, p in enumerate(projects):
        p.createUberUp(astroTime)
        up = p.uberUp[:, day_start:day_end]
        timeUp = np.zeros(nDates)
        for j in np.arange(nDates):
            timeUp[j] = np.count_nonzero(up[:, j]) / float(len(up[:, j]))
        seasonData[i, :] = timeUp
        yl.append(p.pId)
    title = str(astroTime[0, day_start])[:10] + " -- " + str(astroTime[-1, day_end])[:10]
    fig = px.imshow(seasonData, aspect='auto')
    l = len(day_names[day_start:day_end + 1])
    ll = [day_start + i * int(l / 6.) for i in range(7)]
    fig.update_layout(title=title,
                      xaxis=dict(tickmode='array',
                                 tickvals=ll,
                                 ticktext=[day_names[i] for i in ll],
                                 # tickangle=45,
                                 tickfont=dict(size=18)),
                      yaxis=dict(tickmode='array',
                                 tickvals=(np.arange(nProjects)),
                                 tickformat='.3f',
                                 ticktext=yl,
                                 ),
                      height=600)
    return fig


def createPressurePlot(projects, ranks, prjs, prjs_dict,day_start, day_end):
    # prjs: csv files
    # prjs_dict
    # projects: distinct projects' name
    index = {'RSR': 0, 'SEQUOIA': 1, 'MSIP1': 2, 'B4R': 3, 'TolTEC': 4}
    factor = {'RSR': 1.0, 'SEQUOIA': 1.0, 'MSIP1': 1.0, 'B4R': 1.0, 'TolTEC': 1.0}
    allranks = ['A', 'B', 'C', 'D']
    tot = 0
    itime = np.zeros((len(index), len(allranks), 24))  # 4x4x24
    for prj in prjs:
        for k in list(prjs_dict.keys()):
            # k in ['UM','US','MX','TOT']
            if k in prj[0:2].upper():
                tot += prjs_dict[k]
    mult = tot * prjs_dict['TOT']

    for i, p in enumerate(projects):
        for j, s in enumerate(p.sourceList):
            for rank in ranks:
                if s.rank == rank:
                    sum = np.sum(s.lstup)
                    if sum != 0:

                        ss = s.lstup * s.integTime * factor[s.instrument] / sum
                        #print (s.integTime * factor[s.instrument], sum, np.sum(ss))

                        inst = index[s.instrument]
                        itime[inst][allranks.index(rank)] += ss

    title = str(Source.astroTime[0, day_start])[:10] + " -- " + str(Source.astroTime[-1, day_end])[:10]

    fig = go.Figure(data=[go.Scatter(x=[], y=[])])

    cols = [
        [   
            colors['red1'],
            colors['red2'],
            colors['red3'],
            colors['red4'],
        ],
        [
            colors['green1'],
            colors['green2'],
            colors['green3'],
            colors['green4'],
        ],
        [
            colors['blue1'],
            colors['blue2'],
            colors['blue3'],
            colors['blue4'],
        ],
        [
            colors['orange1'],
            colors['orange2'],
            colors['orange3'],
            colors['orange4'],
        ],
        [
            colors['orchid1'],
            colors['orchid2'],
            colors['orchid3'],
            colors['orchid4'],
        ]
    ]
          
    
    ra = np.arange(24)  # ra = [0,...23]
    bot = np.zeros(24)
    for item, i in sorted(list(index.items()), key=lambda x: x[1]):
        # item=[RSR,SEQUOIA, MSIP1, B4R],i=[0,1,2,3]a
        for j, rank in enumerate(allranks):
            # j=[0,1,2,3], rank =[A,B,C,D]
            if itime[i][j].any():
                label = str(list(index.keys())[i]) + '-' + str(allranks[j])
                #label = item
                if factor[item] > 1.0:
                    label = label + ' * ' + str(factor[item])
                if j == 0:
                    fig.add_bar(y=itime[i][j], name=label, marker={'color': 24*[cols[i][j]]})
                else:
                    fig.add_bar(y=itime[i][j], name=label, marker={'color': 24*[cols[i][j]]}) #showlegend=False)
                bot = bot + itime[i][j]
    lstup = np.zeros(24)
    at = Source.astroTime[:, day_start: day_end + 1].flatten()
    lst = (at.sidereal_time('mean').hour % 24.).astype(int)
    unique, counts = np.unique(lst, return_counts=True)
    lstup[unique] = 0.25 * counts

    fig.add_trace(go.Scatter(x=ra + 0.5, y=mult * lstup, mode='lines', marker={'color': 'cyan'},
                             name='UPTIME (%.2f %%) \n efficiency (%.2f %%)' % (tot* 100.0, 100.* prjs_dict['TOT'])))
    fig.update_layout(title=title,
                      barmode='stack',
                      xaxis=dict(title='LST [hours]', tickmode='linear', tick0=0, dtick=6),
                      yaxis=dict(title='Integration Time [hours]'),
                      height=600)
    return fig
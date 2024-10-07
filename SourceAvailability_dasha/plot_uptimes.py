import dash_bootstrap_components as dbc
from dash import html, dcc, Output, Input, ctx
from dash_component_template import ComponentTemplate
import plotly.graph_objs as go
import os
import yaml
from .make_availability import getLMT, makeAstroTime, populateProjects, createPressurePlot, createSeasonPlot

# run dasha -e source_availability_web
# reading the start and end date from yaml file

config_file = os.environ.get('SOURCE_CONFIG_PATH', None)
if config_file is None:
    print('please setup config_file')
else:
    with open(config_file, 'r') as fo:
        config = yaml.safe_load(fo)

start_date = config['date']['start_date']
end_date = config['date']['end_date']
nhours = config['date']['nhours']
nsubhours = config['date']['nsubhours']
prjs = config['project']['prjs']
filename_dict = config['project']['filename_dict']
semester = config['date']['semester']
# set up LMT
LMT = getLMT()

title = html.H1('LMT Source Availability 2025-S1', className='mb-3 mt-2', style={'text-align': 'center'})
# start date, end date, nhours: how many hours a day, nsubhours: how many per hour, ut0: start time

astroTime = makeAstroTime(start_date, end_date, nhours, nsubhours, ut0=" 03:00:0")

day_names = [str(a)[:10] for a in astroTime[0, :]]
days = len(day_names)
efficiency = 0.5
prjs_dict = {'UM': 0.15, 'US': 0.15, 'MX': 0.7, 'TOT': efficiency}
# source_range to show and the total sources number for each project
global source_range, source_len

nsources = 6
source_range = [0, nsources]
source_len = nsources
# populate the projects list

projects = []
sources = []


def make_project(prjs):
    projects = []
    sources = []
    for prj in prjs:
        prj = prj.upper()
        if prj in filename_dict:
            targetsFile = filename_dict[prj]
            projectsFile = targetsFile.split('.')[0] + '.pkl'
            print(('targetsFile', targetsFile, 'projectsFile', projectsFile))
            projects_, sources_ = populateProjects(LMT, astroTime, projectsFile=projectsFile, targetsFile=targetsFile,
                                                   debug=True)
            projects += projects_
            sources += sources_
    return projects, sources


prjs = ['MX', 'US', 'UM']
projects, sources = make_project(prjs)


# # get unique project name
# master_projects = projects


class ControlContent(ComponentTemplate):
    class Meta:
        component_cls = dbc.Container

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    source_select = [
        dbc.Label('Select source:', size='md'),
        html.Div('Sources:', id='sources'),
        dbc.ButtonGroup(
            [
                dbc.Button('All ', id='btn-all', n_clicks=0, className='me-2 mt-2', color="secondary"),
                dbc.Button('Prev 6', id='btn-prev', n_clicks=0, className='me-2 mt-2', color="secondary"),
                dbc.Button('Next 6', id='btn-next', n_clicks=0, className='me-2 mt-2', color="secondary")
            ],
            # vertical=True
        )

    ]
    date_select = [
        dbc.Label('Select start and end date :', size='md'),
        dbc.InputGroup(
            [
                dbc.InputGroupText('Start Day ', style={'font-size': 14, 'width': 100}),
                dbc.Select(options=[
                    {'label': day_names[i], 'value': i} for i in range(days)
                ], id='start_day', placeholder=day_names[0], value=0)
            ]),
        dbc.InputGroup(
            [
                dbc.InputGroupText('End Day', style={'font-size': 14, 'width': 100}),
                dbc.Select(options=[
                    {'label': day_names[i], 'value': i} for i in range(days)
                ], id='end_day', placeholder=day_names[days - 1], value=days - 1)
            ])
    ]
    project_select = [
        dbc.Label('Select date:', size='md'),
        dbc.InputGroup(
            [
                dbc.InputGroupText('Date', style={'font-size': 14, 'width': 100}),
                dbc.Select(options=[
                    {'label': day_names[i], 'value': i} for i in range(days)
                ], id='day', placeholder=day_names[0], value=0)
            ]),
        dbc.Label('Select project name:', size='md'),
        dcc.Dropdown(options=[
            {'label': str(projects[i]), 'value': i} for i in range(len(projects))
        ], id='project_select', placeholder=str(projects[0]), value=0),

    ]
    project_ranks = [
        dbc.Label('Select project file:', id='file_label', size='md'),
        dbc.Checklist(
            options=[
                {'label': 'UM', 'value': 'UM'},
                {'label': 'US', 'value': 'US'},
                {'label': 'MX', 'value': 'MX'},
                # {'label': 'MX-MX9', 'value': 'MX-MX9'},
            ],
            id='file-list-input',
            value=['UM', 'US', 'MX'],
            inline=True
        ),
        dbc.Label('Select project rank:', id='rank_label', size='md'),
        dbc.Checklist(
            options=[
                {'label': 'A', 'value': 'A'},
                {'label': 'B', 'value': 'B'},
                {'label': 'C', 'value': 'C'},
                {'label': 'D', 'value': 'D'},
            ],
            id='rank-list-input',
            value=['A'],
            inline=True
        )
    ]


control = dbc.Row([dbc.CardGroup(
    [
        dbc.Card(dbc.Collapse(dbc.CardBody(ControlContent.date_select),
                              id='is_date', is_open=True, ), color='white', outline=True),
        dbc.Card(dbc.Collapse(dbc.CardBody(ControlContent.project_ranks),
                              id='is_rank', is_open=True), color='white', outline=True),
        dbc.Card(dbc.Collapse(dbc.CardBody(ControlContent.project_select),
                              id='is_project', is_open=False), color='white', outline=True),
        dbc.Card(dbc.Collapse(dbc.CardBody(ControlContent.source_select),
                              id='is_source', is_open=False), color='white', outline=True)
    ], className='mb-3', )], )


class SourceAvailability(ComponentTemplate):
    class Meta:
        component_cls = dbc.Container

    def __init__(self, *args, **kwargs):
        # self.projects = master_projects
        self.ranks = ['A']
        super().__init__(*args, **kwargs)

    def setup_layout(self, app):
        container = self
        # header, control part and plot display part
        header_container, body_container = container.grid(2, 1)
        # header part
        header_container.child(title)
        body_container.child(dbc.Label('Click the tab to view different plots:', size='lg'))
        body_container.child(
            dbc.Tabs(
                [
                    dbc.Tab(label='Pressure Plot', tab_id='pressure', activeTabClassName='text-success'),
                    dbc.Tab(label='Season Plot', tab_id='season', activeTabClassName='text-success'),
                    dbc.Tab(label='Up times', tab_id='upTimes', activeTabClassName='text-success'),
                    dbc.Tab(label='Uber up', tab_id='uberUp', activeTabClassName='text-success'),
                ], id='tabs', active_tab='pressure', className='mt-2 mb-2', )
        )
        body_container.child(html.Div(control, id='control-content'))
        body_container.child(html.Div(id='tab-content'))

        # select the source range
        @app.callback(
            Output('sources', 'children'),
            Input('btn-all', 'n_clicks'),
            Input('btn-prev', 'n_clicks'),
            Input('btn-next', 'n_clicks')
        )
        def source_select(all, prev, next):
            global source_range, source_len
            message = f'Source {source_range[0] + 1} to {source_range[1]}'
            if 'btn-all' == ctx.triggered_id:
                source_range = [0, source_len]
                message = f'Total source(s): {source_len}'
            elif source_len < nsources:
                message = f'source {1} to {source_len}'
            elif 'btn-prev' == ctx.triggered_id:
                if source_range[0] <= 0:
                    source_range[0] = 0
                    source_range[1] = nsources
                else:
                    source_range[0] = max(0, source_range[0] - nsources)
                    source_range[1] = source_range[1] - nsources
                message = f'Source {source_range[0] + 1} to {source_range[1]}'
            elif 'btn-next' == ctx.triggered_id:
                if source_range[1] >= source_len - nsources:
                    source_range[0] = source_len - nsources
                    source_range[1] = source_len
                else:
                    source_range[0] = source_range[0] + nsources
                    source_range[1] = source_range[1] + nsources

                message = f'Source {source_range[0] + 1} to {source_range[1]}'

            return message

        # select the start and end day to plot
        @app.callback(
            Output('end_day', 'options'),
            Input('start_day', 'value')
        )
        def set_day(start_day):
            end_day_options = [
                {'label': day_names[i], 'value': i} for i in range(int(start_day) + 1, days)
            ]
            return end_day_options

        # select the rank and tab output: the project_name and tab-content
        @app.callback(
            Output('project_select', 'options'),
            # Output('control-content', 'children'),
            Output('is_date', 'is_open'),
            Output('is_rank', 'is_open'),
            Output('is_project', 'is_open'),
            Output('is_source', 'is_open'),
            Output('tab-content', 'children'),
            [Input('rank-list-input', 'value'),
             Input('file-list-input', 'value'),
             Input('day', 'value'),
             Input('start_day', 'value'),
             Input('end_day', 'value'),
             Input('project_select', 'value'),
             Input('tabs', 'active_tab'),
             Input('btn-all', 'n_clicks'),
             Input('btn-prev', 'n_clicks'),
             Input('btn-next', 'n_clicks')
             ]
        )
        def plot_select(selected_ranks, prjs, day, start, end, project_index, at, all, prev, next):
            global source_range, source_len

            figure_plot = go.Figure()
            projects, sources = make_project(prjs)
            selected_projects = [p for p in projects if p.sourceList[0].rank in selected_ranks]

            projects_options = [
                {'label': str(selected_projects[i]), 'value': i} for i in range(len(selected_projects))
            ]
            if selected_projects:
                source_len = len(selected_projects[project_index].sourceList)
            else:
                figure_plot = go.Figure(data=[go.Scatter(x=[], y=[])])

            if at == 'pressure':
                is_date = True
                is_rank = True
                is_project = False
                is_source = False
                figure_plot = createPressurePlot(selected_projects, selected_ranks, prjs, prjs_dict, int(start),
                                                 int(end))
            elif at == 'season':
                is_date = False
                is_rank = True
                is_project = False
                is_source = False
                figure_plot = createSeasonPlot(astroTime, day_names, selected_projects, int(start), int(end))
            elif at == 'upTimes':
                is_date = False
                is_rank = True
                is_project = True
                is_source = True
                figure_plot = selected_projects[project_index].plotUptimes(astroTime, day_names, int(day), source_range)
            elif at == 'uberUp':
                is_date = True
                is_rank = True
                is_project = True
                is_source = False
                figure_plot = selected_projects[project_index].plotUberUp(astroTime, day_names, int(start), int(end))

            return projects_options, is_date, is_rank, is_project, is_source, dcc.Graph(figure=figure_plot)


def DASHA_SITE():
    return {
        'extensions': [

            {
                'module': 'dasha.web.extensions.dasha',

                'config': {
                    #'DEBUG': True,
                    'THEME': dbc.themes.YETI,
                    'template': SourceAvailability,
                }

            }

        ]

    }
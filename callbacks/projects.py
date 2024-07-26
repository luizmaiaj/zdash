import logging
from dash.dependencies import Input, Output
import plotly.graph_objs as go
import pandas as pd

from data_management import DataManager

def register_portfolio_callbacks(app, data_manager: DataManager):
    @app.callback(
        [Output('portfolio-hours-chart', 'figure'),
         Output('portfolio-tasks-chart', 'figure')],
        [Input('date-range', 'start_date'),
         Input('date-range', 'end_date'),
         Input('project-filter', 'value'),
         Input('portfolio-hours-height', 'value')]
    )
    def update_portfolio(start_date, end_date, selected_projects, chart_height):
        start_date = pd.to_datetime(start_date)
        end_date = pd.to_datetime(end_date)
        
        filtered_timesheet = data_manager.df_timesheet[
            (data_manager.df_timesheet['date'] >= start_date) &
            (data_manager.df_timesheet['date'] <= end_date)
        ]
        
        filtered_tasks = data_manager.df_tasks[
            (data_manager.df_tasks['create_date'] >= start_date) &
            (data_manager.df_tasks['create_date'] <= end_date)
        ]
        
        if selected_projects:
            filtered_timesheet = filtered_timesheet[filtered_timesheet['project_name'].isin(selected_projects)]
            filtered_tasks = filtered_tasks[filtered_tasks['project_name'].isin(selected_projects)]
        
        # Hours spent per project
        hours_per_project = filtered_timesheet.groupby('project_name')['unit_amount'].sum().reset_index()
        hours_per_project = hours_per_project[hours_per_project['unit_amount'] > 0]
        hours_per_project = hours_per_project.sort_values('unit_amount', ascending=False)
        hours_per_project['unit_amount'] = hours_per_project['unit_amount'].round().astype(int)
        
        fig_hours = go.Figure(go.Bar(
            x=hours_per_project['project_name'],
            y=hours_per_project['unit_amount'],
            text=hours_per_project['unit_amount'],
            textposition='auto'
        ))
        fig_hours.update_layout(
            title='Hours Spent per Project',
            xaxis_title='Project',
            yaxis_title='Hours',
            height=chart_height
        )
        
        # Tasks opened and closed
        tasks_opened = filtered_tasks.groupby('project_name').size().reset_index(name='opened')
        tasks_closed = filtered_tasks[filtered_tasks['date_end'].notna()].groupby('project_name').size().reset_index(name='closed')
        tasks_stats = pd.merge(tasks_opened, tasks_closed, on='project_name', how='outer').fillna(0)
        tasks_stats['total'] = tasks_stats['opened'] + tasks_stats['closed']
        tasks_stats = tasks_stats.sort_values('total', ascending=False)
        
        fig_tasks = go.Figure()
        fig_tasks.add_trace(go.Bar(
            x=tasks_stats['project_name'],
            y=tasks_stats['opened'],
            name='Opened',
            text=tasks_stats['opened'],
            textposition='auto'
        ))
        fig_tasks.add_trace(go.Bar(
            x=tasks_stats['project_name'],
            y=tasks_stats['closed'],
            name='Closed',
            text=tasks_stats['closed'],
            textposition='auto'
        ))
        fig_tasks.update_layout(
            barmode='stack',
            title='Tasks Opened and Closed per Project',
            xaxis_title='Project',
            yaxis_title='Number of Tasks'
        )
        fig_tasks.update_traces(
            hovertemplate='<b>%{x}</b><br>%{y} tasks<extra></extra>',
            hoverlabel=dict(bgcolor="white", font_size=16, font_family="Rockwell")
        )
        
        return fig_hours, fig_tasks

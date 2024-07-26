import logging
from dash.dependencies import Input, Output
import plotly.graph_objs as go
import pandas as pd

from data_management import DataManager

def register_global_kpi_callbacks(app, data_manager: DataManager):
    @app.callback(
        [Output('global-map', 'figure'),
        Output('global-kpi-chart', 'figure')],
        [Input('date-range', 'start_date'),
        Input('date-range', 'end_date'),
        Input('project-filter', 'value')]
    )
    def update_global_kpi(start_date, end_date, selected_projects):
        start_date = pd.to_datetime(start_date)
        end_date = pd.to_datetime(end_date)
        
        filtered_projects = data_manager.df_portfolio.copy()
        if 'date_start' in data_manager.df_portfolio.columns:
            filtered_projects = filtered_projects[
                (filtered_projects['date_start'] >= start_date) &
                (filtered_projects['date_start'] <= end_date)
            ]
        if selected_projects and 'name' in filtered_projects.columns:
            filtered_projects = filtered_projects[filtered_projects['name'].isin(selected_projects)]
        
        if filtered_projects.empty:
            return go.Figure(), go.Figure()
        
        # Create map figure
        fig_map = go.Figure()
        if 'partner_id' in filtered_projects.columns and 'name' in filtered_projects.columns:
            fig_map.add_trace(go.Scattergeo(
                locations=filtered_projects['partner_id'],
                text=filtered_projects['name'],
                mode='markers',
                marker=dict(
                    size=10,
                    color='blue',
                    line=dict(width=3, color='rgba(68, 68, 68, 0)')
                )
            ))
        fig_map.update_layout(
            title='Project Locations',
            geo=dict(
                showland=True,
                showcountries=True,
                showocean=True,
                countrywidth=0.5,
                landcolor='rgb(243, 243, 243)',
                oceancolor='rgb(208, 242, 255)',
                projection=dict(type='natural earth')
            )
        )
        
        # Create KPI chart
        fig_kpi = go.Figure()
        if 'date_start' in filtered_projects.columns:
            project_counts = filtered_projects.groupby(filtered_projects['date_start'].dt.to_period('M')).size().reset_index(name='count')
            project_counts['date_start'] = project_counts['date_start'].astype(str)
            fig_kpi.add_trace(go.Bar(x=project_counts['date_start'], y=project_counts['count']))
            fig_kpi.update_layout(title='Projects by Month', xaxis_title='Month', yaxis_title='Number of Projects')
        
        return fig_map, fig_kpi

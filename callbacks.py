from dash.dependencies import Input, Output, State
from dash import html
import plotly.graph_objs as go
import pandas as pd
from datetime import datetime
from llm_integration import generate_llm_report

def register_callbacks(app, df_projects, df_employees, df_sales, df_financials, df_timesheet, df_tasks):
    
    @app.callback(
        [Output('global-map', 'figure'),
         Output('global-kpi-chart', 'figure')],
        [Input('date-range', 'start_date'),
         Input('date-range', 'end_date'),
         Input('project-filter', 'value'),
         Input('employee-filter', 'value')]
    )
    def update_global_kpi(start_date, end_date, selected_projects, selected_employees):
        start_date = pd.to_datetime(start_date)
        end_date = pd.to_datetime(end_date)
        
        filtered_projects = df_projects[
            (df_projects['date_start'] >= start_date) &
            (df_projects['date_start'] <= end_date)
        ]
        if selected_projects:
            filtered_projects = filtered_projects[filtered_projects['name'].isin(selected_projects)]
        
        if filtered_projects.empty:
            return go.Figure(), go.Figure()
        
        fig_map = go.Figure(go.Scattergeo(
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
        
        project_counts = filtered_projects.groupby(filtered_projects['date_start'].dt.to_period('M')).size().reset_index(name='count')
        project_counts['date_start'] = project_counts['date_start'].astype(str)
        
        fig_kpi = go.Figure(go.Bar(x=project_counts['date_start'], y=project_counts['count']))
        fig_kpi.update_layout(title='Projects by Month', xaxis_title='Month', yaxis_title='Number of Projects')
        
        return fig_map, fig_kpi

    @app.callback(
        Output('financials-chart', 'figure'),
        [Input('date-range', 'start_date'),
         Input('date-range', 'end_date')]
    )
    def update_financials(start_date, end_date):
        start_date = pd.to_datetime(start_date)
        end_date = pd.to_datetime(end_date)
        
        filtered_financials = df_financials[
            (df_financials['date'] >= start_date) &
            (df_financials['date'] <= end_date)
        ]
        
        if filtered_financials.empty:
            return go.Figure()
        
        daily_financials = filtered_financials.groupby('date')['amount_total'].sum().reset_index()
        fig = go.Figure(go.Scatter(x=daily_financials['date'], y=daily_financials['amount_total'], mode='lines'))
        fig.update_layout(title='Daily Financial Summary')
        return fig

    @app.callback(
        [Output('projects-hours-chart', 'figure'),
         Output('projects-tasks-chart', 'figure')],
        [Input('date-range', 'start_date'),
         Input('date-range', 'end_date'),
         Input('project-filter', 'value'),
         Input('projects-hours-height', 'value')]
    )
    def update_projects(start_date, end_date, selected_projects, chart_height):
        start_date = pd.to_datetime(start_date)
        end_date = pd.to_datetime(end_date)
        
        filtered_timesheet = df_timesheet[
            (df_timesheet['date'] >= start_date) &
            (df_timesheet['date'] <= end_date)
        ]
        
        filtered_tasks = df_tasks[
            (df_tasks['create_date'] >= start_date) &
            (df_tasks['create_date'] <= end_date)
        ]
        
        if selected_projects:
            filtered_timesheet = filtered_timesheet[filtered_timesheet['project_name'].isin(selected_projects)]
            filtered_tasks = filtered_tasks[filtered_tasks['project_name'].isin(selected_projects)]
        
        # Hours spent per project
        hours_per_project = filtered_timesheet.groupby('project_name')['unit_amount'].sum().reset_index()
        hours_per_project = hours_per_project[hours_per_project['unit_amount'] > 0]  # Remove projects with no hours
        hours_per_project = hours_per_project.sort_values('unit_amount', ascending=False)
        hours_per_project['unit_amount'] = hours_per_project['unit_amount'].round().astype(int)  # Round to integers
        
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

    @app.callback(
        [Output('employee-hours-chart', 'figure'),
        Output('total-hours', 'children')],
        [Input('date-range', 'start_date'),
        Input('date-range', 'end_date'),
        Input('project-filter', 'value'),
        Input('employee-filter', 'value'),
        Input('employee-chart-height', 'value')]
    )
    def update_employee_hours(start_date, end_date, selected_projects, selected_employees, chart_height):
        start_date = pd.to_datetime(start_date)
        end_date = pd.to_datetime(end_date)
        
        filtered_timesheet = df_timesheet[
            (df_timesheet['date'] >= start_date) &
            (df_timesheet['date'] <= end_date)
        ]
        
        if selected_projects:
            filtered_timesheet = filtered_timesheet[filtered_timesheet['project_name'].isin(selected_projects)]
        
        if selected_employees:
            filtered_timesheet = filtered_timesheet[filtered_timesheet['employee_name'].isin(selected_employees)]
        
        employee_hours = filtered_timesheet.groupby(['employee_name', 'project_name'])['unit_amount'].sum().reset_index()
        employee_hours['unit_amount'] = employee_hours['unit_amount'].round().astype(int)  # Round to integers
        
        total_hours = employee_hours['unit_amount'].sum()
        
        fig = go.Figure()
        for project in employee_hours['project_name'].unique():
            project_data = employee_hours[employee_hours['project_name'] == project]
            fig.add_trace(go.Bar(
                x=project_data['employee_name'],
                y=project_data['unit_amount'],
                name=project,
                text=project_data['unit_amount'],
                textposition='auto',
                hovertemplate='<b>Employee:</b> %{x}<br><b>Project:</b> ' + project + '<br><b>Hours:</b> %{y}<extra></extra>'
            ))
        
        fig.update_layout(
            barmode='stack',
            title='Employee Hours per Project',
            xaxis_title='Employee',
            yaxis_title='Hours',
            height=chart_height,
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=-0.5,
                xanchor="center",
                x=0.5
            ),
            margin=dict(b=150)  # Increase bottom margin to accommodate the legend
        )
        
        return fig, f"Total Hours Worked: {total_hours}"

    @app.callback(
        Output('sales-chart', 'figure'),
        [Input('date-range', 'start_date'),
         Input('date-range', 'end_date'),
         Input('apply-sales-filter', 'n_clicks')],
        [State('sales-task-filter', 'value')]
    )
    def update_sales(start_date, end_date, n_clicks, task_filter):
        start_date = pd.to_datetime(start_date)
        end_date = pd.to_datetime(end_date)
        
        filtered_sales = df_sales[
            (df_sales['date_order'] >= start_date) &
            (df_sales['date_order'] <= end_date)
        ]
        
        filtered_tasks = df_tasks[
            (df_tasks['create_date'] >= start_date) &
            (df_tasks['create_date'] <= end_date)
        ]
        
        if task_filter:
            keywords = [keyword.strip().lower() for keyword in task_filter.split(',')]
            filtered_tasks = filtered_tasks[filtered_tasks['name'].str.lower().str.contains('|'.join(keywords))]
        
        if filtered_sales.empty and filtered_tasks.empty:
            return go.Figure()
        
        daily_sales = filtered_sales.groupby('date_order')['amount_total'].sum().reset_index()
        daily_tasks = filtered_tasks.groupby('create_date').size().reset_index(name='task_count')
        
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=daily_sales['date_order'], y=daily_sales['amount_total'], name='Sales', mode='lines'))
        fig.add_trace(go.Scatter(x=daily_tasks['create_date'], y=daily_tasks['task_count'], name='Tasks', mode='lines', yaxis='y2'))
        
        fig.update_layout(
            title='Sales and Tasks Over Time',
            xaxis_title='Date',
            yaxis_title='Sales Amount',
            yaxis2=dict(title='Number of Tasks', overlaying='y', side='right')
        )
        
        return fig

    @app.callback(
        Output('data-quality-report', 'children'),
        [Input('date-range', 'start_date'),
        Input('date-range', 'end_date')]
    )
    def update_data_quality_report(start_date, end_date):
        start_date = pd.to_datetime(start_date)
        end_date = pd.to_datetime(end_date)
        
        report = []
        
        # Check for projects with no hours logged
        projects_without_hours = set(df_projects['name']) - set(df_timesheet['project_name'])
        
        # Check for employees with no hours logged
        employees_without_hours = set(df_employees['name']) - set(df_timesheet['employee_name'])
        
        # Create side-by-side scrollable lists
        report.append(html.Div([
            html.Div([
                html.H4("Projects with no hours logged:"),
                html.Div([
                    html.Ul([html.Li(project) for project in projects_without_hours], style={'column-count': 2})
                ], style={'height': '400px', 'overflow': 'auto', 'border': '1px solid #ddd', 'padding': '10px'})
            ], style={'width': '48%', 'display': 'inline-block', 'vertical-align': 'top'}),
            
            html.Div([
                html.H4("Employees with no hours logged:"),
                html.Div([
                    html.Ul([html.Li(employee) for employee in employees_without_hours], style={'column-count': 2})
                ], style={'height': '400px', 'overflow': 'auto', 'border': '1px solid #ddd', 'padding': '10px'})
            ], style={'width': '48%', 'display': 'inline-block', 'vertical-align': 'top', 'margin-left': '4%'})
        ]))
        
        # Check for inconsistent project status (closed projects with open tasks)
        closed_projects = df_projects[df_projects['active'] == False]['name']
        open_tasks = df_tasks[df_tasks['date_end'].isna()]['project_name']
        inconsistent_projects = set(closed_projects) & set(open_tasks)
        if inconsistent_projects:
            report.append(html.P(f"Closed projects with open tasks: {', '.join(inconsistent_projects)}"))
        
        # Suggestions for improvement
        report.append(html.H4("Suggestions for improvement:"))
        report.append(html.Ul([
            html.Li("Add a burndown chart for each project to track progress"),
            html.Li("Include a resource allocation view to optimize employee workload"),
            html.Li("Implement a customer satisfaction metric for completed projects"),
            html.Li("Add a risk assessment indicator for ongoing projects"),
            html.Li("Include a profitability analysis comparing estimated vs. actual hours")
        ]))
        
        return report

    @app.callback(
        Output('llm-report-output', 'children'),
        Input('generate-llm-report', 'n_clicks'),
        prevent_initial_call=True
    )
    def update_llm_report(n_clicks):
        if n_clicks > 0:
            report = generate_llm_report(df_projects, df_employees, df_sales, df_financials, df_timesheet, df_tasks)
            if report.startswith("Error:"):
                return html.Div([
                    html.H4("Error Generating LLM Report"),
                    html.P(report, style={'color': 'red'})
                ])
            else:
                return html.Div([
                    html.H4("LLM Generated Report"),
                    html.Pre(report, style={'white-space': 'pre-wrap', 'word-break': 'break-word'})
                ])
        return ""

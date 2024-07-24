from dash.dependencies import Input, Output, State
from dash import html, dash_table
import plotly.graph_objs as go
import ast
import dash
import pandas as pd
from datetime import datetime
from llm_integration import generate_llm_report
from data_management import save_job_costs, load_or_fetch_data, serialize_dataframes, deserialize_dataframes

def register_callbacks(app, df_projects, df_employees, df_sales, df_financials, df_timesheet, df_tasks):

    @app.callback(
        [Output('data-store', 'data'),
        Output('last-update-time', 'children')],
        [Input('refresh-data', 'n_clicks')],
        [State('data-store', 'data')]
    )
    def refresh_dashboard_data(n_clicks, current_data):
        ctx = dash.callback_context
        if not ctx.triggered:
            # Initial load
            data, last_updated = load_or_fetch_data(force=False)
        else:
            # Button click, force refresh
            data, last_updated = load_or_fetch_data(force=True)
        
        if data:
            serialized_data = serialize_dataframes(data)
            return serialized_data, f"Last updated: {last_updated.strftime('%Y-%m-%d %H:%M:%S')}"
        else:
            # If refresh failed and we don't have current data, return empty DataFrames
            empty_data = [pd.DataFrame() for _ in range(6)]
            serialized_empty_data = serialize_dataframes(empty_data)
            return serialized_empty_data, "Failed to update data"

    @app.callback(
        [Output('project-filter', 'options'),
         Output('employee-filter', 'options')],
        [Input('data-store', 'data')]
    )
    def update_filter_options(serialized_data):
        if serialized_data is None:
            return [], []
        data = deserialize_dataframes(serialized_data)
        df_projects, df_employees = data[:2]
        project_options = [{'label': i, 'value': i} for i in df_projects['name'].unique() if pd.notna(i)]
        employee_options = [{'label': i, 'value': i} for i in df_employees['name'].unique() if pd.notna(i)]
        return project_options, employee_options

    @app.callback(
        Output('llm-report-output', 'children'),
        [Input('generate-llm-report', 'n_clicks')],
        [State('model-selection', 'value'),
         State('data-store', 'data')],
        prevent_initial_call=True
    )
    def update_llm_report(n_clicks, selected_model, serialized_data):
        if n_clicks > 0 and selected_model and serialized_data:
            data = deserialize_dataframes(serialized_data)
            df_projects, df_employees, df_sales, df_financials, df_timesheet, df_tasks = data
            report = generate_llm_report(df_projects, df_employees, df_sales, df_financials, df_timesheet, df_tasks, selected_model)
            if report.startswith("Error:"):
                return html.Div([
                    html.H4("Error Generating LLM Report"),
                    html.P(report, style={'color': 'red'})
                ])
            else:
                return html.Div([
                    html.H4(f"LLM Generated Report (Model: {selected_model})"),
                    html.Pre(report, style={'white-space': 'pre-wrap', 'word-break': 'break-word'})
                ])
        return ""

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
        
        filtered_projects = df_projects.copy()
        if 'date_start' in df_projects.columns:
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

    @app.callback(
        Output('financials-chart', 'figure'),
        [Input('date-range', 'start_date'),
         Input('date-range', 'end_date')]
    )
    def update_financials(start_date, end_date):
        start_date = pd.to_datetime(start_date)
        end_date = pd.to_datetime(end_date)
        
        print("Financials columns:", df_financials.columns)

        # Check if 'date' column exists, if not, try to find an alternative
        date_column = 'date'
        if date_column not in df_financials.columns:
            date_columns = [col for col in df_financials.columns if 'date' in col.lower()]
            if date_columns:
                date_column = date_columns[0]
            else:
                return go.Figure()  # Return empty figure if no suitable date column found
        
        filtered_financials = df_financials[
            (df_financials[date_column] >= start_date) &
            (df_financials[date_column] <= end_date)
        ]
        
        if filtered_financials.empty:
            return go.Figure()
        
        daily_financials = filtered_financials.groupby(date_column)['amount_total'].sum().reset_index()
        fig = go.Figure(go.Scatter(x=daily_financials[date_column], y=daily_financials['amount_total'], mode='lines'))
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
        
        # Sort employees alphabetically
        sorted_employees = sorted(employee_hours['employee_name'].unique())
        
        fig = go.Figure()
        for project in employee_hours['project_name'].unique():
            project_data = employee_hours[employee_hours['project_name'] == project]
            
            # Create a full dataset with all employees, fill missing values with 0
            full_data = pd.DataFrame({'employee_name': sorted_employees})
            full_data = full_data.merge(project_data, on='employee_name', how='left')
            full_data['unit_amount'] = full_data['unit_amount'].fillna(0)
            
            fig.add_trace(go.Bar(
                x=full_data['employee_name'],
                y=full_data['unit_amount'],
                name=project,
                text=full_data['unit_amount'],
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
                orientation="v",
                yanchor="top",
                y=1,
                xanchor="left",
                x=1.02,
                bgcolor="rgba(255, 255, 255, 0.5)",
                bordercolor="rgba(0, 0, 0, 0.2)",
                borderwidth=1,
                itemwidth=30,
            ),
            margin=dict(r=250, b=100, t=50, l=50),
            xaxis=dict(
                tickangle=45,
                automargin=True,
                categoryorder='array',
                categoryarray=sorted_employees
            )
        )
        
        # Make the chart horizontally scrollable
        fig.update_layout(
            xaxis=dict(
                rangeslider=dict(visible=False),
                range=[0, 20],  # Show first 20 employees initially
                automargin=True
            ),
            updatemenus=[
                dict(
                    type="buttons",
                    direction="left",
                    buttons=[
                        dict(args=[{"xaxis.range": [0, 20]}], label="Reset View", method="relayout"),
                    ],
                    pad={"r": 10, "t": 10},
                    showactive=False,
                    x=0.01,
                    xanchor="left",
                    y=1.1,
                    yanchor="top"
                ),
            ]
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
        
        print("Sales columns:", df_sales.columns)

        # Check if 'date_order' column exists, if not, try to find an alternative
        date_column = 'date_order'
        if date_column not in df_sales.columns:
            date_columns = [col for col in df_sales.columns if 'date' in col.lower()]
            if date_columns:
                date_column = date_columns[0]
            else:
                return go.Figure()  # Return empty figure if no suitable date column found
        
        filtered_sales = df_sales[
            (df_sales[date_column] >= start_date) &
            (df_sales[date_column] <= end_date)
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
        
        daily_sales = filtered_sales.groupby(date_column)['amount_total'].sum().reset_index()
        daily_tasks = filtered_tasks.groupby('create_date').size().reset_index(name='task_count')
        
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=daily_sales[date_column], y=daily_sales['amount_total'], name='Sales', mode='lines'))
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
        if 'name' in df_projects.columns and 'project_name' in df_timesheet.columns:
            projects_without_hours = set(df_projects['name']) - set(df_timesheet['project_name'])
        else:
            projects_without_hours = set()
        
        # Check for employees with no hours logged
        if 'name' in df_employees.columns and 'employee_name' in df_timesheet.columns:
            employees_without_hours = set(df_employees['name']) - set(df_timesheet['employee_name'])
        else:
            employees_without_hours = set()
        
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
        if 'active' in df_projects.columns and 'name' in df_projects.columns and 'date_end' in df_tasks.columns and 'project_name' in df_tasks.columns:
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
        Output('project-filter', 'disabled'),
        [Input('tabs', 'value')]
    )
    def disable_project_filter(tab):
        return tab == 'project-tab'

    @app.callback(
        Output('project-tasks-employees-chart', 'figure'),
        [Input('project-selector', 'value'),
        Input('date-range', 'start_date'),
        Input('date-range', 'end_date'),
        Input('employee-filter', 'value')]
    )
    def update_project_tasks_employees_chart(selected_project, start_date, end_date, selected_employees):
        if not selected_project:
            return go.Figure()

        start_date = pd.to_datetime(start_date)
        end_date = pd.to_datetime(end_date)

        # Filter data based on date range
        project_timesheet = df_timesheet[
            (df_timesheet['project_name'] == selected_project) &
            (df_timesheet['date'] >= start_date) &
            (df_timesheet['date'] <= end_date)
        ].copy()

        if project_timesheet.empty:
            return go.Figure()

        # Filter by selected employees if any
        if selected_employees:
            project_timesheet = project_timesheet[project_timesheet['employee_name'].isin(selected_employees)]

        # Convert 'task_id' to string
        project_timesheet['task_id_str'] = project_timesheet['task_id'].astype(str)
        df_tasks['id_str'] = df_tasks['id'].astype(str)

        # Merge timesheet data with tasks to get task names
        merged_data = pd.merge(project_timesheet, df_tasks[['id_str', 'name']], 
                            left_on='task_id_str', right_on='id_str', how='left')

        merged_data['task_name'] = merged_data['name'].fillna(merged_data['task_id_str']).fillna('Unknown Task')

        # Group by task and employee, summing the hours
        task_employee_hours = merged_data.groupby(['task_name', 'employee_name'])['unit_amount'].sum().unstack(fill_value=0)

        # Sort tasks by total hours in descending order
        task_employee_hours['total'] = task_employee_hours.sum(axis=1)
        task_employee_hours = task_employee_hours.sort_values('total', ascending=False).drop('total', axis=1)

        # Create the stacked bar chart
        fig = go.Figure()

        for employee in task_employee_hours.columns:
            fig.add_trace(go.Bar(
                name=employee,
                x=task_employee_hours.index,
                y=task_employee_hours[employee],
                text=task_employee_hours[employee].round().astype(int),
                textposition='auto',
                hovertemplate='<b>%{x}</b><br>' +
                            f'<b>{employee}</b>: ' +
                            '%{text} hours<extra></extra>'
            ))

        fig.update_layout(
            barmode='stack',
            title=f'Tasks and Employee Hours for {selected_project}',
            xaxis_title='Tasks',
            yaxis_title='Hours',
            legend_title='Employees',
            legend=dict(
                orientation="v",
                yanchor="top",
                y=1,
                xanchor="left",
                x=1.02
            ),
            height=600,
            margin=dict(r=200, b=100, t=50),
            xaxis=dict(
                tickangle=45,
                tickmode='array',
                tickvals=list(range(len(task_employee_hours.index))),
                ticktext=task_employee_hours.index
            )
        )

        return fig

    @app.callback(
        Output('long-tasks-list', 'children'),
        [Input('date-range', 'start_date'),
        Input('date-range', 'end_date')]
    )
    def update_long_tasks_list(start_date, end_date):
        start_date = pd.to_datetime(start_date)
        end_date = pd.to_datetime(end_date)

        # Filter timesheet data based on date range
        filtered_timesheet = df_timesheet[
            (df_timesheet['date'] >= start_date) &
            (df_timesheet['date'] <= end_date)
        ].copy()

        # Filter timesheets longer than 8 hours
        long_timesheets = filtered_timesheet[filtered_timesheet['unit_amount'] > 8]

        # Sort by hours descending
        long_timesheets = long_timesheets.sort_values('unit_amount', ascending=False)

        # Merge with tasks to get task names
        long_timesheets['task_id'] = long_timesheets['task_id'].astype(str)
        df_tasks['id'] = df_tasks['id'].astype(str)
        merged_data = pd.merge(long_timesheets, df_tasks[['id', 'name']], left_on='task_id', right_on='id', how='left')

        # Function to safely extract task name
        def extract_task_name(task_id):
            try:
                return ast.literal_eval(task_id)[1] if isinstance(task_id, str) and task_id.startswith('[') else task_id
            except:
                return task_id

        # Prepare the data for the table
        table_data = merged_data[['employee_name', 'project_name', 'task_id', 'name', 'date', 'unit_amount']].rename(columns={
            'name': 'task_name',
            'date': 'created_on',
            'unit_amount': 'duration'
        })

        # Extract task name from task_id if necessary
        table_data['task_name'] = table_data['task_name'].fillna(table_data['task_id'].apply(extract_task_name))
        table_data['task_id'] = table_data['task_id'].apply(lambda x: ast.literal_eval(x)[0] if isinstance(x, str) and x.startswith('[') else x)

        # Round duration to 2 decimal places
        table_data['duration'] = table_data['duration'].round(2)

        if table_data.empty:
            return html.Div("No timesheets longer than 8 hours found in the selected date range.")

        # Create the sortable table
        return html.Div([
            html.H4("Timesheets Longer Than 8 Hours:"),
            dash_table.DataTable(
                id='long-timesheets-table',
                columns=[
                    {"name": "Employee Name", "id": "employee_name"},
                    {"name": "Project Name", "id": "project_name"},
                    {"name": "Task Id", "id": "task_id"},
                    {"name": "Task Name", "id": "task_name"},
                    {"name": "Created On", "id": "created_on"},
                    {"name": "Duration (Hours)", "id": "duration"}
                ],
                data=table_data.to_dict('records'),
                sort_action='native',
                sort_mode='multi',
                style_table={'height': '400px', 'overflowY': 'auto'},
                style_cell={'textAlign': 'left', 'padding': '10px'},
                style_header={
                    'backgroundColor': 'rgb(230, 230, 230)',
                    'fontWeight': 'bold'
                },
                style_data_conditional=[
                    {
                        'if': {'row_index': 'odd'},
                        'backgroundColor': 'rgb(248, 248, 248)'
                    }
                ]
            )
        ])

    @app.callback(
        Output('job-costs-table', 'data'),
        Input('add-job-title', 'n_clicks'),
        State('job-costs-table', 'data'),
        prevent_initial_call=True
    )
    def add_job_title(n_clicks, rows):
        if n_clicks > 0:
            rows.append({'job_title': '', 'cost': '', 'revenue': ''})
        return rows

    @app.callback(
        Output('job-costs-save-status', 'children'),
        Input('save-job-costs', 'n_clicks'),
        State('job-costs-table', 'data'),
        prevent_initial_call=True
    )
    def save_job_costs_callback(n_clicks, rows):
        if n_clicks > 0:
            job_costs = {row['job_title']: {'cost': row['cost'], 'revenue': row['revenue']} for row in rows if row['job_title']}
            save_job_costs(job_costs)
            return "Job costs saved successfully!"
        return ""

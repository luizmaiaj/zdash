from dash.dependencies import Input, Output
import plotly.graph_objs as go
import pandas as pd

def register_employees_callbacks(app, df_timesheet):
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
        employee_hours['unit_amount'] = employee_hours['unit_amount'].round().astype(int)
        
        total_hours = employee_hours['unit_amount'].sum()
        
        sorted_employees = sorted(employee_hours['employee_name'].unique())
        
        fig = go.Figure()
        for project in employee_hours['project_name'].unique():
            project_data = employee_hours[employee_hours['project_name'] == project]
            
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
        
        fig.update_layout(
            xaxis=dict(
                rangeslider=dict(visible=False),
                range=[0, 20],
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

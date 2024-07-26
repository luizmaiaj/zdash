import pandas as pd
import plotly.graph_objs as go
from datetime import datetime
import logging

from data_management import DataManager

logger = logging.getLogger(__name__)

class FinancialCalculator:
    def __init__(self, data_manager: DataManager):
        self.data_manager = data_manager

    def calculate_all_financials(self, start_date, end_date):
        logger.info("Calculating all financials")
        
        financials_data = {}
        
        date_column = next((col for col in self.data_manager.df_timesheet.columns if 'date' in col.lower()), None)
        if not date_column:
            logger.error("No date column found in timesheet data")
            return financials_data
        
        try:
            self.data_manager.df_timesheet[date_column] = pd.to_datetime(self.data_manager.df_timesheet[date_column], errors='coerce')
            self.data_manager.df_timesheet = self.data_manager.df_timesheet.dropna(subset=[date_column])
        except Exception as e:
            logger.error(f"Error converting date column to datetime: {str(e)}")
            return financials_data
        
        for _, project in self.data_manager.df_portfolio.iterrows():
            project_name = project['name']
            logger.info(f"Calculating financials for project: {project_name}")
            project_timesheet = self.data_manager.df_timesheet[
                (self.data_manager.df_timesheet['project_name'] == project_name) &
                (self.data_manager.df_timesheet[date_column] >= start_date) &
                (self.data_manager.df_timesheet[date_column] <= end_date)
            ].copy()
            
            if project_timesheet.empty:
                logger.warning(f"No timesheet data for project: {project_name}")
                continue
            
            project_revenue = self.calculate_project_revenue(project_timesheet, self.data_manager.df_employees, self.data_manager.job_costs)
            project_hours = project_timesheet['unit_amount'].sum()
            
            project_timesheet['task_id_str'] = project_timesheet['task_id'].astype(str)
            
            daily_data = project_timesheet.groupby(date_column).agg({
                'unit_amount': 'sum',
                'employee_name': lambda x: x.unique().tolist(),
                'task_id_str': lambda x: x.unique().tolist()
            }).reset_index()
            
            daily_data = daily_data.rename(columns={'task_id_str': 'task_id'})
            
            project_financials = {
                'total_revenue': project_revenue,
                'total_hours': project_hours,
                'daily_data': daily_data.to_dict('records')
            }
            
            financials_data[project_name] = project_financials
        
        logger.info(f"Financials calculated for {len(financials_data)} projects")
        return financials_data

    def calculate_project_revenue(self, timesheet_data, employees_data, job_costs):
        revenue = 0
        for _, row in timesheet_data.iterrows():
            employee_data = employees_data[employees_data['name'] == row['employee_name']]
            if employee_data.empty:
                logger.warning(f"Employee {row['employee_name']} not found in employees data")
                continue
            
            employee = employee_data.iloc[0]
            job_title = self.extract_job_title(employee)
            
            job_cost_data = job_costs.get(job_title, {})
            
            try:
                daily_revenue = float(job_cost_data.get('revenue') or 0)
            except (ValueError, AttributeError):
                logger.warning(f"Invalid revenue data for job title: {job_title}")
                daily_revenue = 0
            
            entry_revenue = (row['unit_amount'] / 8) * daily_revenue
            revenue += entry_revenue
        return revenue

    def create_financials_chart(self, financials_data):
        logger.info("Creating financials chart")
        fig = go.Figure()
        
        all_daily_data = []
        
        for project, data in financials_data.items():
            daily_data = pd.DataFrame(data['daily_data'])
            if daily_data.empty:
                logger.warning(f"No daily data for project: {project}")
                continue
            
            if 'revenue' not in daily_data.columns:
                logger.info(f"Calculating daily revenue for project: {project}")
                daily_data['revenue'] = daily_data.apply(
                    lambda row: self.calculate_project_revenue(
                        self.data_manager.df_timesheet[
                            (self.data_manager.df_timesheet['project_name'] == project) &
                            (self.data_manager.df_timesheet['date'] == row['date'])
                        ],
                        self.data_manager.df_employees,
                        self.data_manager.job_costs
                    ),
                    axis=1
                )
            
            logger.debug(f"Daily revenue for {project}: {daily_data['revenue'].sum()}")
            
            daily_data['project'] = project
            all_daily_data.append(daily_data)
        
        if not all_daily_data:
            logger.warning("No daily data available for any project")
            return fig
        
        all_daily_data = pd.concat(all_daily_data)
        logger.info(f"Total daily data rows: {len(all_daily_data)}")
        
        pivoted_data = all_daily_data.pivot(index='date', columns='project', values='revenue').fillna(0)
        logger.info(f"Pivoted data shape: {pivoted_data.shape}")

        for project in pivoted_data.columns:
            project_revenue = pivoted_data[project].sum()
            logger.info(f"Total revenue for {project}: {project_revenue}")
            fig.add_trace(go.Bar(
                x=pivoted_data.index,
                y=pivoted_data[project],
                name=project,
                hoverinfo='none',
                hovertemplate=None
            ))
        
        fig.update_layout(
            title='Daily Revenue by Project',
            xaxis_title='Date',
            yaxis_title='Revenue',
            barmode='stack',
            hovermode='closest',
            hoverlabel=dict(
                bgcolor="white",
                font_size=12,
                font_family="Rockwell"
            )
        )

        fig.update_traces(
            hovertemplate='<b>%{fullData.name}</b>Revenue: $%{y:,.2f}<extra></extra>'
        )
        
        return fig

    def create_hours_chart(self, financials_data):
        logger.info("Creating hours chart")
        fig = go.Figure()
        
        for project, data in financials_data.items():
            daily_data = pd.DataFrame(data['daily_data'])
            if daily_data.empty:
                logger.warning(f"No daily data for project: {project}")
                continue
            
            date_column = daily_data.columns[0]
            
            fig.add_trace(go.Bar(
                x=daily_data[date_column],
                y=daily_data['unit_amount'],
                name=project
            ))
        
        fig.update_layout(
            title='Daily Hours by Project',
            xaxis_title='Date',
            yaxis_title='Hours',
            barmode='stack'
        )
        
        logger.info("Hours chart created")
        return fig

    def create_revenue_chart(self, financials_data):
        logger.info("Creating revenue chart")
        fig = go.Figure()
        
        projects = list(financials_data.keys())
        revenues = [data['total_revenue'] for data in financials_data.values()]
        
        logger.info(f"Projects: {projects}")
        logger.info(f"Revenues: {revenues}")
        
        fig.add_trace(go.Bar(
            x=projects,
            y=revenues,
            text=revenues,
            textposition='auto'
        ))
        
        fig.update_layout(
            title='Total Revenue by Project',
            xaxis_title='Project',
            yaxis_title='Revenue',
            yaxis_tickformat='$,.0f',
            barmode='stack'
        )
        
        logger.info("Revenue chart created")
        return fig

    @staticmethod
    def extract_job_title(employee):
        if 'job_id' in employee and isinstance(employee['job_id'], str):
            try:
                job_id_list = ast.literal_eval(employee['job_id'])
                return job_id_list[1] if len(job_id_list) > 1 else 'Unknown'
            except (ValueError, SyntaxError, IndexError) as e:
                logger.error(f"Job title not found: {e}")
                return 'Unknown'
        elif 'job_title' in employee:
            return employee['job_title']
        else:
            logger.warning(f"Job title not found: {employee}")
            return 'Unknown'

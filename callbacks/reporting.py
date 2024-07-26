from dash.dependencies import Input, Output

from data_management import DataManager
from data_quality_reporter import DataQualityReporter

def register_reporting_callback(app, data_manager: DataManager):
    data_quality_reporter = DataQualityReporter(data_manager)

    @app.callback(
        Output('data-quality-report', 'children'),
        [Input('date-range', 'start_date'),
        Input('date-range', 'end_date')]
    )
    def update_data_quality_report(start_date, end_date):
        return data_quality_reporter.generate_data_quality_report(start_date, end_date)

    @app.callback(
        Output('long-tasks-list', 'children'),
        [Input('date-range', 'start_date'),
        Input('date-range', 'end_date')]
    )
    def update_long_tasks_list(start_date, end_date):
        return data_quality_reporter.generate_long_tasks_list(start_date, end_date)

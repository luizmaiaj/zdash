import os
import xmlrpc.client
import pandas as pd

# Odoo API connection
url = os.getenv('ODOO_URL')
db = os.getenv('ODOO_DB')
username = os.getenv('ODOO_USERNAME')
api_key = os.getenv('ODOO_API_KEY')

# Create XML-RPC client with allow_none=True
common = xmlrpc.client.ServerProxy(f'{url}/xmlrpc/2/common', allow_none=True)
uid = common.authenticate(db, username, api_key, {})
models = xmlrpc.client.ServerProxy(f'{url}/xmlrpc/2/object', allow_none=True)

def fetch_odoo_data(model, fields, domain=[], limit=None):
    try:
        result = models.execute_kw(db, uid, api_key, model, 'search_read', [domain, fields], {'limit': limit})
        cleaned_result = [{k: v for k, v in record.items() if v is not None} for record in result]
        return cleaned_result
    except Exception as err:
        print(f"Error fetching data from Odoo, model {model}, fields {fields}, domain {domain}, limit {limit}: {err}")
        return []

def validate_dataframe(df, required_columns):
    for col in required_columns:
        if col not in df.columns:
            df[col] = None
    return df

def extract_id(x):
    if isinstance(x, (list, tuple)) and len(x) > 0:
        return x[0]
    return x

def fetch_and_process_data(last_update=None):
    try:
        # Prepare the domain for fetching only new or updated data
        if last_update:
            base_domain = [('write_date', '>', last_update.isoformat())]
        else:
            base_domain = []

        # Fetch necessary data
        projects = fetch_odoo_data('project.project', ['id', 'name', 'partner_id', 'user_id', 'date_start', 'date', 'active'], domain=base_domain)
        employees = fetch_odoo_data('hr.employee', ['id', 'name', 'department_id', 'job_id', 'job_title'], domain=base_domain)
        sales = fetch_odoo_data('sale.order', ['name', 'partner_id', 'amount_total', 'date_order'], domain=base_domain)
        financials = fetch_odoo_data('account.move', ['name', 'move_type', 'amount_total', 'date'], domain=base_domain)
        timesheet_entries = fetch_odoo_data('account.analytic.line', ['employee_id', 'task_id', 'project_id', 'unit_amount', 'date'], domain=base_domain)
        tasks = fetch_odoo_data('project.task', ['id', 'project_id', 'stage_id', 'name', 'create_date', 'date_end'], domain=base_domain)

        # Convert to pandas DataFrames with data validation
        df_projects = validate_dataframe(pd.DataFrame(projects), ['id', 'name', 'partner_id', 'user_id', 'date_start', 'date', 'active'])
        df_employees = validate_dataframe(pd.DataFrame(employees), ['id', 'name', 'department_id', 'job_id', 'job_title'])
        df_sales = validate_dataframe(pd.DataFrame(sales), ['name', 'partner_id', 'amount_total', 'date_order'])
        df_financials = validate_dataframe(pd.DataFrame(financials), ['name', 'move_type', 'amount_total', 'date'])
        df_timesheet = validate_dataframe(pd.DataFrame(timesheet_entries), ['employee_id', 'project_id', 'unit_amount', 'date'])
        df_tasks = validate_dataframe(pd.DataFrame(tasks), ['project_id', 'stage_id', 'create_date', 'date_end'])

        # Print column names for debugging
        print("df_projects columns:", df_projects.columns)
        print("df_employees columns:", df_employees.columns)
        print("df_sales columns:", df_sales.columns)
        print("df_financials columns:", df_financials.columns)
        print("df_timesheet columns:", df_timesheet.columns)
        print("df_tasks columns:", df_tasks.columns)

        # Convert date columns to datetime
        date_columns = {
            'df_projects': ['date_start', 'date'],
            'df_sales': ['date_order'],
            'df_financials': ['date'],
            'df_timesheet': ['date'],
            'df_tasks': ['create_date', 'date_end']
        }

        for df_name, columns in date_columns.items():
            df = locals()[df_name]
            for col in columns:
                if col in df.columns:
                    df[col] = pd.to_datetime(df[col], errors='coerce')

        # Apply extract_id function to relevant columns
        df_timesheet['project_id'] = df_timesheet['project_id'].apply(extract_id)
        df_timesheet['employee_id'] = df_timesheet['employee_id'].apply(extract_id)
        df_tasks['project_id'] = df_tasks['project_id'].apply(extract_id)

        # Create dictionaries to map IDs to names
        project_id_to_name = dict(zip(df_projects['id'], df_projects['name'])) if 'id' in df_projects.columns and 'name' in df_projects.columns else {}
        employee_id_to_name = dict(zip(df_employees['id'], df_employees['name'])) if 'id' in df_employees.columns and 'name' in df_employees.columns else {}

        # Map IDs to names in timesheet and tasks DataFrames
        if 'project_id' in df_timesheet.columns:
            df_timesheet['project_name'] = df_timesheet['project_id'].map(project_id_to_name)
        if 'employee_id' in df_timesheet.columns:
            df_timesheet['employee_name'] = df_timesheet['employee_id'].map(employee_id_to_name)
        if 'project_id' in df_tasks.columns:
            df_tasks['project_name'] = df_tasks['project_id'].map(project_id_to_name)

        return df_projects, df_employees, df_sales, df_financials, df_timesheet, df_tasks
    except Exception as e:
        print(f"Error in fetch_and_process_data: {e}")
        return None, None, None, None, None, None

if __name__ == "__main__":
    # For testing purposes
    data = fetch_and_process_data()
    for df in data:
        if df is not None:
            print(df.head())
        else:
            print("None")

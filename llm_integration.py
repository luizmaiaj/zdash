import logging
from langchain_community.chat_models import ChatOllama
from langchain.prompts import ChatPromptTemplate
import pandas as pd
import requests
from ollama import Client

def check_ollama_status():
    try:
        client = Client()
        models = client.list()
        return True, models
    except Exception:
        return False, None

def extract_model_names(models_info: list) -> tuple:
    """
    Extracts the model names from the models information.
    :param models_info: A dictionary containing the models' information.
    Return:
    A tuple containing the model names.
    """
    # Filter out multimodal and embedding models
    filtered_models = [
        model for model in models_info['models']
        if not any(keyword in model['name'].lower() for keyword in ['clip', 'vision', 'embed'])
    ]
    return tuple(model["name"] for model in filtered_models)

def prepare_data_summary(df_projects, df_employees, df_sales, df_financials, df_timesheet, df_tasks):
    summary = f"""
    Projects: {len(df_projects)} total
    Employees: {len(df_employees)} total
    """

    # Handle sales data
    if 'amount_total' in df_sales.columns:
        summary += f"Sales: {df_sales['amount_total'].sum():.2f} total\n"
    else:
        numeric_columns = df_sales.select_dtypes(include=['float64', 'int64']).columns
        if len(numeric_columns) > 0:
            summary += f"Sales: {df_sales[numeric_columns[0]].sum():.2f} total (using {numeric_columns[0]} column)\n"
        else:
            summary += "Sales data not available\n"

    # Handle financials data
    if 'amount_total' in df_financials.columns:
        summary += f"Financials: {df_financials['amount_total'].sum():.2f} total\n"
    else:
        numeric_columns = df_financials.select_dtypes(include=['float64', 'int64']).columns
        if len(numeric_columns) > 0:
            summary += f"Financials: {df_financials[numeric_columns[0]].sum():.2f} total (using {numeric_columns[0]} column)\n"
        else:
            summary += "Financial data not available\n"

    summary += f"""
    Timesheet Entries: {len(df_timesheet)} total
    Tasks: {len(df_tasks)} total
    """

    # Handle top projects by hours
    if 'project_name' in df_timesheet.columns and 'unit_amount' in df_timesheet.columns:
        top_projects = df_timesheet.groupby('project_name')['unit_amount'].sum().sort_values(ascending=False).head()
        summary += "\nTop 5 Projects by Hours:\n"
        summary += top_projects.to_string()
    else:
        summary += "\nTop projects by hours data not available"

    # Handle top employees by hours
    if 'employee_name' in df_timesheet.columns and 'unit_amount' in df_timesheet.columns:
        top_employees = df_timesheet.groupby('employee_name')['unit_amount'].sum().sort_values(ascending=False).head()
        summary += "\n\nTop 5 Employees by Hours:\n"
        summary += top_employees.to_string()
    else:
        summary += "\nTop employees by hours data not available"

    # Handle monthly sales trend
    if 'date_order' in df_sales.columns and 'amount_total' in df_sales.columns:
        monthly_sales = df_sales.groupby(df_sales['date_order'].dt.to_period('M'))['amount_total'].sum()
        summary += "\n\nMonthly Sales Trend:\n"
        summary += monthly_sales.to_string()
    else:
        summary += "\nMonthly sales trend data not available"

    return summary

def generate_llm_report(df_projects, df_employees, df_sales, df_financials, df_timesheet, df_tasks, selected_model):
    data_summary = prepare_data_summary(df_projects, df_employees, df_sales, df_financials, df_timesheet, df_tasks)

    ollama_running, available_models = check_ollama_status()
    if not ollama_running:
        return "Error: Ollama is not running. Please start Ollama and try again."

    if selected_model not in extract_model_names(available_models):
        return f"Error: Selected model '{selected_model}' is not available. Please choose an available model."

    prompt = ChatPromptTemplate.from_template("""
    You are an AI assistant tasked with analyzing business data and creating an engaging report in the style of John Oliver's Last Week Tonight. Use the following data summary to generate fun facts, insightful questions, and an entertaining report that highlights key trends and potential areas of improvement for the business.

    Data Summary:
    {data_summary}

    Please provide:
    1. 3-5 fun facts about the data
    2. 3-5 insightful questions that the business should consider
    3. A brief, engaging report (300-500 words) in the style of John Oliver, highlighting key trends and potential areas for improvement

    Be witty, use analogies, and don't shy away from pointing out absurdities or potential issues in the data.
    """)

    try:
        llm = ChatOllama(
            model=selected_model,
            temperature=0.7,
            keep_alive='1h',
            top_p=0.9,
            max_tokens=1000
        )
        
        chain = prompt | llm

        response = chain.invoke({"data_summary": data_summary})

        return response.content
    except Exception as e:
        return f"Error generating report: {str(e)}"

from langchain_community.chat_models import ChatOllama
from langchain.prompts import ChatPromptTemplate
import pandas as pd
import subprocess
import requests

def check_ollama_status():
    try:
        response = requests.get("http://localhost:11434/api/tags")
        if response.status_code == 200:
            return True, response.json()
    except requests.RequestException:
        pass
    return False, None

def prepare_data_summary(df_projects, df_employees, df_sales, df_financials, df_timesheet, df_tasks):
    summary = f"""
    Projects: {len(df_projects)} total
    Employees: {len(df_employees)} total
    Sales: {df_sales['amount_total'].sum():.2f} total
    Financials: {df_financials['amount_total'].sum():.2f} total
    Timesheet Entries: {len(df_timesheet)} total
    Tasks: {len(df_tasks)} total

    Top 5 Projects by Hours:
    {df_timesheet.groupby('project_name')['unit_amount'].sum().sort_values(ascending=False).head().to_string()}

    Top 5 Employees by Hours:
    {df_timesheet.groupby('employee_name')['unit_amount'].sum().sort_values(ascending=False).head().to_string()}

    Monthly Sales Trend:
    {df_sales.groupby(df_sales['date_order'].dt.to_period('M'))['amount_total'].sum().to_string()}
    """
    return summary

def generate_llm_report(df_projects, df_employees, df_sales, df_financials, df_timesheet, df_tasks):
    data_summary = prepare_data_summary(df_projects, df_employees, df_sales, df_financials, df_timesheet, df_tasks)

    ollama_running, available_models = check_ollama_status()
    if not ollama_running:
        return "Error: Ollama is not running. Please start Ollama and try again."

    model_name = "llama2"  # Default to a smaller model
    if any("llama2:70b" in model for model in available_models.get('models', [])):
        model_name = "llama2:70b"
    elif any("llama2" in model for model in available_models.get('models', [])):
        model_name = next(model for model in available_models.get('models', []) if "llama2" in model)
    else:
        try:
            subprocess.run(["ollama", "pull", "llama2"], check=True)
            model_name = "llama3:70B"
        except subprocess.CalledProcessError:
            return "Error: Failed to pull the Llama2 model. Please check your Ollama installation."

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
            model=model_name,
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

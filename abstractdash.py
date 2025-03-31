import streamlit as st
from simple_salesforce import Salesforce
import os
from dotenv import load_dotenv
import plotly.express as px
import pandas as pd
import numpy as np
import pytz
from datetime import datetime, timedelta

# Set page configuration
st.set_page_config(
    page_title="Calls Sentiment Score",
    page_icon="✨",
    layout="wide",  # Use a wide layout for the app
)

# --- Timezone Utility Functions ---
def get_eastern_time_now():
    return datetime.now(pytz.timezone('US/Eastern'))

def convert_to_eastern(dt):
    if dt.tzinfo is None or dt.tzinfo.utcoffset(dt) is None:
        dt = dt.replace(tzinfo=pytz.UTC)
    return dt.astimezone(pytz.timezone('US/Eastern'))

def get_date_range_iso(days=1095):
    eastern_now = get_eastern_time_now()
    end_date = eastern_now
    start_date = eastern_now - timedelta(days=days)
    return start_date.date().isoformat(), end_date.date().isoformat()

def get_date_range(period):
    """Return start and end dates for the selected period."""
    today = get_eastern_time_now()
    
    if period == "Week":
        start_of_period = (today - timedelta(days=today.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_period = start_of_period + timedelta(days=6, hours=23, minutes=59, seconds=59)
    elif period == "Month":
        start_of_period = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        next_month = start_of_period + timedelta(days=31)
        next_month = next_month.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        end_of_period = next_month - timedelta(seconds=1)
    elif period == "Quarter":
        quarter = (today.month - 1) // 3 + 1
        start_of_period = datetime(today.year, 3 * quarter - 2, 1, tzinfo=today.tzinfo)
        if quarter < 4:
            end_of_period = datetime(today.year, 3 * quarter + 1, 1, tzinfo=today.tzinfo) - timedelta(seconds=1)
        else:
            end_of_period = datetime(today.year, 12, 31, 23, 59, 59, tzinfo=today.tzinfo)
    elif period == "7":
        end_of_period = today
        start_of_period = today - timedelta(days=7)
    elif period == "30":
        end_of_period = today
        start_of_period = today - timedelta(days=30)
    elif period == "90":
        end_of_period = today
        start_of_period = today - timedelta(days=90)
    elif period == "1095":
        end_of_period = today
        start_of_period = today - timedelta(days=1095)
    else:
        if isinstance(period, tuple) and len(period) == 2:  # Custom Range
            start_date, end_date = period
            start_of_period = datetime.combine(start_date, datetime.min.time()).replace(tzinfo=today.tzinfo)
            end_of_period = datetime.combine(end_date, datetime.max.time()).replace(tzinfo=today.tzinfo)
        else:
            raise ValueError("Invalid period selected")
    
    return start_of_period.isoformat(), end_of_period.isoformat(), start_of_period, end_of_period

# --- Salesforce Query Function ---
def connect_to_salesforce_and_run_query(start_date=None, end_date=None):
    try:
        sf = Salesforce(
            username=os.getenv("SF_USERNAME_PRO"),
            password=os.getenv("SF_PASSWORD_PRO"),
            security_token=os.getenv("SF_SECURITY_TOKEN_PRO"),
        )
        st.success("Salesforce connection successful!")
        
        # Use default period if dates not provided
        if start_date is None or end_date is None:
            start_date, end_date = get_date_range_iso()
        
        # SOQL query with date filtering (ensure your dates match Salesforce formatting requirements)
        soql_query = f"""
            SELECT Id, Call_Sentiment__c, CreatedDate 
            FROM Abstrakt_Summary__c 
            WHERE CreatedDate >= {start_date} AND CreatedDate <= {end_date}
            AND Call_Sentiment__c IN ('Positive', 'Negative', 'Neutral', 'N/A')
        """
        query_results = sf.query_all(soql_query)
        records = query_results['records']
        if not records:
            return pd.DataFrame(), soql_query
        df = pd.DataFrame(records)
        
        # Convert CreatedDate to datetime and adjust to US/Eastern
        df['CreatedDate'] = pd.to_datetime(df['CreatedDate'], utc=True).dt.tz_convert('US/Eastern')
        df['CreatedDateET'] = df['CreatedDate']
        return df, soql_query
    except Exception as e:
        st.error(f"Error while querying Salesforce: {str(e)}")
        return pd.DataFrame(), None

# --- Load environment variables ---
load_dotenv()

# --- Main Streamlit UI ---
st.title("Abstrakt Summary Sentiment Dashboard")

# Initialize session state
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False
    st.session_state.df = pd.DataFrame()
    st.session_state.query = None
    st.session_state.total_count = 0
    st.session_state.selected_period = "Week"
    st.session_state.period_start = None
    st.session_state.period_end = None

# --- Sidebar: Period Selection & Authentication ---
st.sidebar.header("Dashboard Options")

date_filter_options = {
    "Week": "Current Week",
    "Month": "Current Month", 
    "Quarter": "Current Quarter",
    "7": "Last 7 Days",
    "30": "Last 30 Days",
    "90": "Last 90 Days",
    "1095": "Last 3 Years",
    "custom": "Custom Range"
}

selected_period = st.sidebar.selectbox(
    "Select Period",
    options=list(date_filter_options.keys()),
    format_func=lambda x: date_filter_options[x],
    index=list(date_filter_options.keys()).index(
        st.session_state.selected_period if st.session_state.selected_period in date_filter_options else "Week"
    )
)

custom_start_date = None
custom_end_date = None
if selected_period == "custom":
    col1, col2 = st.sidebar.columns(2)
    with col1:
        custom_start_date = st.date_input("Start Date", value=(get_eastern_time_now() - timedelta(days=90)).date())
    with col2:
        custom_end_date = st.date_input("End Date", value=get_eastern_time_now().date())
    if custom_start_date > custom_end_date:
        st.sidebar.error("Start date must be before end date")

# --- Authentication and Query Execution ---
if not st.session_state.authenticated:
    if st.sidebar.button("Authenticate & Fetch Data"):
        if selected_period == "custom":
            if custom_start_date and custom_end_date and custom_start_date <= custom_end_date:
                period_tuple = (custom_start_date, custom_end_date)
                start_date, end_date, period_start, period_end = get_date_range(period_tuple)
            else:
                st.sidebar.error("Invalid date range")
                start_date, end_date, period_start, period_end = get_date_range("90")
        else:
            start_date, end_date, period_start, period_end = get_date_range(selected_period)
        df, query = connect_to_salesforce_and_run_query(start_date, end_date)
        if not df.empty:
            st.session_state.authenticated = True
            st.session_state.df = df
            st.session_state.query = query
            st.session_state.total_count = len(df)
            st.session_state.selected_period = selected_period
            st.session_state.period_start = period_start
            st.session_state.period_end = period_end
            st.sidebar.success("Authentication successful. Data fetched.")
        else:
            st.error("No data found.")
else:
    st.sidebar.success("Already authenticated. You can view and interact with the data.")
    if selected_period != st.session_state.selected_period or selected_period == "custom":
        if st.sidebar.button("Update Query"):
            if selected_period == "custom":
                if custom_start_date and custom_end_date and custom_start_date <= custom_end_date:
                    period_tuple = (custom_start_date, custom_end_date)
                    start_date, end_date, period_start, period_end = get_date_range(period_tuple)
                else:
                    st.sidebar.error("Invalid date range")
                    start_date, end_date, period_start, period_end = get_date_range(st.session_state.selected_period)
            else:
                start_date, end_date, period_start, period_end = get_date_range(selected_period)
            df, query = connect_to_salesforce_and_run_query(start_date, end_date)
            if not df.empty:
                st.session_state.df = df
                st.session_state.query = query
                st.session_state.total_count = len(df)
                st.session_state.selected_period = selected_period
                st.session_state.period_start = period_start
                st.session_state.period_end = period_end
            else:
                st.error("No data found.")

# --- Main Content ---
if st.session_state.authenticated:
    # Reporting Period Display
    if st.session_state.period_start and st.session_state.period_end:
        st.subheader("Reporting Period")
        if st.session_state.selected_period == "Month":
            period_display = f"{st.session_state.period_start.strftime('%B %Y')}"
        elif st.session_state.selected_period == "Week":
            period_display = f"Week of {st.session_state.period_start.strftime('%B %d, %Y')} to {st.session_state.period_end.strftime('%B %d, %Y')}"
        elif st.session_state.selected_period == "Quarter":
            quarter_num = (st.session_state.period_start.month - 1) // 3 + 1
            period_display = f"Q{quarter_num} {st.session_state.period_start.year}"
        elif st.session_state.selected_period == "custom":
            period_display = f"{st.session_state.period_start.strftime('%B %d, %Y')} to {st.session_state.period_end.strftime('%B %d, %Y')}"
        else:
            period_display = f"{date_filter_options[st.session_state.selected_period]}: {st.session_state.period_start.strftime('%B %d, %Y')} to {st.session_state.period_end.strftime('%B %d, %Y')}"
        st.info(f"**Reporting Period: {period_display}**", icon="📅")
    
    # Sentiment Breakdown
    st.subheader("Sentiment Breakdown")
    df = st.session_state.df.dropna(subset=["Call_Sentiment__c"])
    sentiment_counts = df["Call_Sentiment__c"].value_counts().reset_index()
    sentiment_counts.columns = ["Call Sentiment", "Count"]
    total_count = sentiment_counts["Count"].sum()
    sentiment_counts["Percentage"] = ((sentiment_counts["Count"] / total_count) * 100).round(2)
    st.dataframe(sentiment_counts)
    
    # --- Visualization Section ---
    st.subheader("Visualizations")
    # Chart Type Selection with Debug Output
    chart_type = st.sidebar.selectbox(
        "Select Chart Type",
        options=[
            "Bar Chart", "Pie Chart", "Scatter Plot", "Line Chart",
            "Histogram", "Box Plot", "Sine Wave", "Treemap", "Sunburst", "Funnel Chart", "Area Chart"
        ]
    )
    st.write("Selected chart type:", chart_type)  # Debug info

    with st.expander("Chart Output", expanded=True):
        if chart_type == "Bar Chart":
            fig = px.bar(
                sentiment_counts,
                x="Call Sentiment",
                y="Count",
                text="Percentage",
                title="Sentiment Distribution",
                labels={"Call Sentiment": "Sentiment", "Count": "Number of Records"}
            )
            fig.update_traces(texttemplate="%{text}%", textposition="outside")
            st.plotly_chart(fig)
        elif chart_type == "Pie Chart":
            fig = px.pie(
                sentiment_counts,
                names="Call Sentiment",
                values="Count",
                title="Sentiment Breakdown",
                hover_data=["Percentage"],
                labels={"Percentage": "Percentage (%)"}
            )
            fig.update_traces(textinfo="percent+label", hovertemplate="%{label}: %{value} (%{percent})")
            st.plotly_chart(fig)
        elif chart_type == "Scatter Plot":
            # Now using CreatedDate instead of record Id.
            fig = px.scatter(
                df,
                x="CreatedDate",
                y="Call_Sentiment__c",
                title="Sentiment by Date",
                labels={"CreatedDate": "Date", "Call_Sentiment__c": "Sentiment"}
            )
            st.plotly_chart(fig)
        elif chart_type == "Line Chart":
            fig = px.line(
                sentiment_counts,
                x="Call Sentiment",
                y="Count",
                title="Cumulative Sentiment Trends",
                text="Percentage"
            )
            fig.update_traces(texttemplate="%{text}%", textposition="top center")
            st.plotly_chart(fig)
        elif chart_type == "Histogram":
            fig = px.histogram(
                df,
                x="Call_Sentiment__c",
                title="Histogram of Sentiments",
                labels={"Call_Sentiment__c": "Sentiment"}
            )
            st.plotly_chart(fig)
        elif chart_type == "Box Plot":
            fig = px.box(
                df,
                y="Call_Sentiment__c",
                title="Box Plot of Sentiments",
                labels={"Call_Sentiment__c": "Sentiment"}
            )
            st.plotly_chart(fig)
        elif chart_type == "Sine Wave":
            x = np.linspace(0, 10, 100)
            y = np.sin(x)
            sine_wave_df = pd.DataFrame({"x": x, "y": y})
            fig = px.line(sine_wave_df, x="x", y="y", title="Sine Wave")
            st.plotly_chart(fig)
        elif chart_type == "Treemap":
            fig = px.treemap(
                sentiment_counts,
                path=["Call Sentiment"],
                values="Count",
                title="Treemap of Sentiments",
                hover_data=["Percentage"]
            )
            st.plotly_chart(fig)
        elif chart_type == "Sunburst":
            fig = px.sunburst(
                sentiment_counts,
                path=["Call Sentiment"],
                values="Count",
                title="Sunburst Chart of Sentiments",
                hover_data=["Percentage"]
            )
            st.plotly_chart(fig)
        elif chart_type == "Funnel Chart":
            fig = px.funnel(
                sentiment_counts,
                x="Count",
                y="Call Sentiment",
                title="Funnel Chart of Sentiments",
                text="Percentage"
            )
            fig.update_traces(texttemplate="%{text}%", textposition="inside")
            st.plotly_chart(fig)
        elif chart_type == "Area Chart":
            fig = px.area(
                sentiment_counts,
                x="Call Sentiment",
                y="Count",
                title="Area Chart of Sentiments",
                labels={"Call Sentiment": "Sentiment", "Count": "Number of Records"},
                text="Percentage"
            )
            fig.update_traces(texttemplate="%{text}%", textposition="top center")
            st.plotly_chart(fig)
        else:
            st.error("Selected chart type not recognized.")
    
    # --- Trend Chart Section (without record Ids) ---
    st.subheader("Trend Chart")
    # Use a copy of the dataframe without the "Id" column for trend grouping
    df_trend = st.session_state.df.copy().drop(columns=["Id"], errors="ignore")
    if st.session_state.selected_period in ["Week", "Month", "Quarter"]:
        freq_map = {"Week": "W", "Month": "M", "Quarter": "Q"}
        trend_df = df_trend.groupby(pd.Grouper(key="CreatedDate", freq=freq_map[st.session_state.selected_period])).size().reset_index(name="Count")
    else:
        trend_df = df_trend.groupby(pd.Grouper(key="CreatedDate", freq="D")).size().reset_index(name="Count")
    
    if not trend_df.empty:
        fig_trend = px.line(trend_df, x="CreatedDate", y="Count", title=f"Trends - {date_filter_options[st.session_state.selected_period]}")
        st.plotly_chart(fig_trend)
    else:
        st.info("No trend data available for the selected period.")
else:
    st.warning("Authenticate first to view data and charts.")

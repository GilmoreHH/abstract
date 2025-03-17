import streamlit as st
from simple_salesforce import Salesforce
import os
from dotenv import load_dotenv
import plotly.express as px
import pandas as pd
import numpy as np

# Load environment variables from .env file
load_dotenv()

# Function to connect to Salesforce and execute SOQL query
def connect_to_salesforce_and_run_query():
    """Connect to Salesforce and execute SOQL query for Abstrakt Summary."""
    try:
        # Connect to Salesforce using environment variables
        sf = Salesforce(
            username=os.getenv("SF_USERNAME_PRO"),
            password=os.getenv("SF_PASSWORD_PRO"),
            security_token=os.getenv("SF_SECURITY_TOKEN_PRO"),
        )
        st.success("Salesforce connection successful!")

        # Define the SOQL query to get Abstrakt Summary data
        soql_query = """
            SELECT Id, Call_Sentiment__c 
            FROM Abstrakt_Summary__c 
            WHERE Call_Sentiment__c IN ('Positive', 'Negative', 'Neutral', 'N/A')
        """
        
        # Execute the SOQL query
        query_results = sf.query_all(soql_query)
        
        # Extract and prepare data for visualization
        records = query_results['records']
        df = pd.DataFrame(records)
        
        return df
    except Exception as e:
        st.error(f"Error while querying Salesforce: {str(e)}")
        return None

# Streamlit UI - Dashboard Layout
st.title("Abstrakt Summary Sentiment Dashboard")

# Session state for persistent variables
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False
    st.session_state.df = None

# Sidebar for authentication
st.sidebar.header("Authentication")

# Authenticate only once
if not st.session_state.authenticated:
    if st.sidebar.button("Authenticate & Fetch Data"):
        df = connect_to_salesforce_and_run_query()
        if df is not None:
            st.session_state.authenticated = True
            st.session_state.df = df
else:
    st.sidebar.success("Already authenticated. You can view and interact with the data.")
    
   

# Main content area
if st.session_state.authenticated and st.session_state.df is not None:
    # Original DataFrame
    df = st.session_state.df.dropna(subset=["Call_Sentiment__c"])

    # Sidebar Filter Options
    st.sidebar.header("Filters")
    sentiment_filter = st.sidebar.multiselect(
        "Filter by Sentiment",
        options=df["Call_Sentiment__c"].unique(),
        default=df["Call_Sentiment__c"].unique(),
    )

    # Apply filters to the dataframe
    filtered_df = df[df["Call_Sentiment__c"].isin(sentiment_filter)]

    # Sentiment counts and percentages
    sentiment_counts = filtered_df["Call_Sentiment__c"].value_counts().reset_index()
    sentiment_counts.columns = ["Call Sentiment", "Count"]
    total_count = sentiment_counts["Count"].sum()
    sentiment_counts["Percentage"] = (
        (sentiment_counts["Count"] / total_count) * 100
    ).round(2)

    # Display Sentiment Breakdown
    st.subheader("Sentiment Breakdown")
    st.dataframe(sentiment_counts)

    # Visualization Section
    st.subheader("Visualizations")

     # Chart Type Selection in Sidebar
    chart_type = st.sidebar.selectbox(
        "Select Chart Type",
        options=[
            "Bar Chart", 
            "Pie Chart", 
            "Scatter Plot", 
            "Line Chart", 
            "Histogram", 
            "Box Plot", 
            "Sine Wave", 
            "Treemap", 
            "Sunburst", 
            "Funnel Chart", 
            "Area Chart"
        ]
    )

    # Generate and display charts based on the selected chart type
    if chart_type == "Bar Chart":
        fig = px.bar(
            sentiment_counts,
            x="Call Sentiment", 
            y="Count",
            text="Percentage",
            title="Sentiment Distribution",
            labels={"Call Sentiment": "Sentiment", "Count": "Number of Records"},
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
            labels={"Percentage": "Percentage (%)"},
        )
        fig.update_traces(textinfo="percent+label", hovertemplate="%{label}: %{value} (%{percent})")
        st.plotly_chart(fig)

    elif chart_type == "Scatter Plot":
        fig = px.scatter(
            filtered_df, 
            x="Id", 
            y="Call_Sentiment__c",
            title="Sentiment by ID",
            labels={"Id": "Record ID", "Call_Sentiment__c": "Sentiment"}
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
            filtered_df, 
            x="Call_Sentiment__c",
            title="Histogram of Sentiments",
            labels={"Call_Sentiment__c": "Sentiment"}
        )
        st.plotly_chart(fig)

    elif chart_type == "Box Plot":
        fig = px.box(
            filtered_df, 
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
            hover_data=["Percentage"],
        )
        st.plotly_chart(fig)

    elif chart_type == "Sunburst":
        fig = px.sunburst(
            sentiment_counts,
            path=["Call Sentiment"],
            values="Count",
            title="Sunburst Chart of Sentiments",
            hover_data=["Percentage"],
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
    st.warning("Authenticate first to view data and charts.")
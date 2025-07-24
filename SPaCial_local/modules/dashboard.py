
# =============================================================================
# modules/dashboard.py
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from utils.database import get_db_connection

def app(lang):
    st.title(f"📊 {lang('home')}")
    
    conn = get_db_connection()
    
    # KPIs
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        total_products = pd.read_sql("SELECT COUNT(*) as count FROM products", conn).iloc[0]['count']
        st.metric("Products", total_products)
    
    with col2:
        total_features = pd.read_sql("SELECT COUNT(*) as count FROM features", conn).iloc[0]['count']
        st.metric("Features", total_features)
    
    with col3:
        total_gammas = pd.read_sql("SELECT COUNT(*) as count FROM gammas", conn).iloc[0]['count']
        st.metric("Control Gammas", total_gammas)
        
    with col4:
        total_measurements = pd.read_sql("SELECT COUNT(*) as count FROM measurements", conn).iloc[0]['count']
        st.metric("Measurements", total_measurements)
    
    # Charts
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📈 Measurements Trend")
        df_measurements = pd.read_sql("""
            SELECT DATE(timestamp) as date, COUNT(*) as count 
            FROM measurements 
            GROUP BY DATE(timestamp)
            ORDER BY date DESC LIMIT 30
        """, conn)
        
        if not df_measurements.empty:
            fig = px.line(df_measurements, x='date', y='count', title="Daily Measurements")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No measurement data")
    
    with col2:
        st.subheader("🏷️ Products by Family")
        df_families = pd.read_sql("""
            SELECT f.name, COUNT(p.id) as count 
            FROM families f 
            LEFT JOIN products p ON f.id = p.family_id 
            GROUP BY f.name
        """, conn)
        
        if not df_families.empty:
            fig = px.pie(df_families, values='count', names='name')
            st.plotly_chart(fig, use_container_width=True)
    
    # Recent measurements
    st.subheader("🕒 Recent Measurements")
    recent = pd.read_sql("""
        SELECT p.code as product, f.name as feature, m.value, m.timestamp, m.operator
        FROM measurements m
        JOIN products p ON m.product_id = p.id
        JOIN features f ON m.feature_id = f.id
        ORDER BY m.timestamp DESC LIMIT 10
    """, conn)
    
    if not recent.empty:
        st.dataframe(recent, use_container_width=True)
    
    conn.close()
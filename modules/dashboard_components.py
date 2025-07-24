# dashboard_components.py
import streamlit as st
import pandas as pd
import plotly.express as px
import numpy as np
from datetime import datetime, timedelta

def create_metric_card(title, value, delta=None, delta_color="normal"):
    """Create a styled metric card"""
    if delta:
        st.metric(label=title, value=value, delta=delta, delta_color=delta_color)
    else:
        st.metric(label=title, value=value)

def create_status_chart(data, status_field="status", title="Status Distribution"):
    """Create a donut chart for status distribution"""
    if not data:
        return None

    status_counts = {}
    for item in data:
        status = item.get(status_field, "Unknown")
        status_counts[status] = status_counts.get(status, 0) + 1

    if status_counts:
        fig = px.pie(
            values=list(status_counts.values()),
            names=list(status_counts.keys()),
            hole=0.6,
            color_discrete_map={
                "Active": "#28a745",
                "Inactive": "#dc3545",
                "Maintenance": "#ffc107",
                "Ativo": "#28a745",
                "Inativo": "#dc3545",
                "Manutenção": "#ffc107"
            }
        )
        fig.update_layout(
            showlegend=True,
            height=300,
            margin=dict(t=20, b=20, l=20, r=20),
            title_text=title # Adicionado título ao gráfico
        )
        return fig
    return None

def create_capacity_chart(data, title="Atelier Capacities"):
    """Create a bar chart for atelier capacities"""
    if not data:
        return None

    df = pd.DataFrame([{
        "Name": item.get("name", "Unknown"),
        "Capacity": item.get("capacity", 0)
    } for item in data if item.get("capacity", 0) > 0])

    if not df.empty:
        fig = px.bar(
            df,
            x="Name",
            y="Capacity",
            title=title, # Usar o título passado
            color="Capacity",
            color_continuous_scale="viridis"
        )
        fig.update_layout(height=400, showlegend=False)
        return fig
    return None

# --- Componentes do Dashboard ---

def render_overview_tab(data, filters, t):
    st.markdown("### Factory Overview")

    col1, col2 = st.columns([2, 1])

    with col1:
        st.markdown("#### 🗺️ Factory Layout")
        layout_data = []
        for atelier in data[t("ateliers", "Ateliers")]:
            layout_data.append({
                'x': np.random.randint(0, 10),
                'y': np.random.randint(0, 8),
                'name': atelier.get('name', 'Unknown'),
                'capacity': atelier.get('capacity', 0),
                'status': atelier.get('status', 'Active')
            })

        if layout_data:
            df_layout = pd.DataFrame(layout_data)
            fig_layout = px.scatter(
                df_layout, x='x', y='y',
                size='capacity',
                color='status',
                hover_name='name',
                title="Factory Floor Layout",
                size_max=30,
                color_discrete_map={
                    "Active": "#28a745",
                    "Inactive": "#dc3545",
                    "Ativo": "#28a745",
                    "Inativo": "#dc3545"
                }
            )
            fig_layout.update_layout(height=400)
            st.plotly_chart(fig_layout, use_container_width=True)

    with col2:
        st.markdown("#### 📊 Status Distribution")
        workstation_chart = create_status_chart(data[t("workstations", "Workstations")], title=t("workstation_status", "Workstation Status"))
        if workstation_chart:
            st.plotly_chart(workstation_chart, use_container_width=True)

        st.markdown("#### 🎯 Quick Stats")
        total_capacity = sum(item.get('capacity', 0) for item in data[t("ateliers", "Ateliers")])
        active_workstations = len([w for w in data[t("workstations", "Workstations")]
                                     if w.get('status') in ['Active', 'Ativo']])

        st.info(f"""
            **Total Capacity:** {total_capacity:,}
            **Active Workstations:** {active_workstations}
            **Efficiency:** 87.3%
            **Uptime:** 94.2%
        """)

def render_analytics_tab(data, filters, t):
    st.markdown("### 📈 Analytics & Insights")

    col1, col2 = st.columns(2)

    with col1:
        capacity_chart = create_capacity_chart(data[t("ateliers", "ateliers")], title=t("atelier_capacities", "Atelier Capacities"))
        if capacity_chart:
            st.plotly_chart(capacity_chart, use_container_width=True)

    with col2:
        st.markdown("#### 📊 Production Trends")
        dates = pd.date_range(start='2024-01-01', end='2024-12-31', freq='M')
        production = np.random.randint(800, 1200, len(dates))

        df_trends = pd.DataFrame({
            'Month': dates,
            'Production': production
        })

        fig_trends = px.line(
            df_trends, x='Month', y='Production',
            title="Monthly Production Trends",
            markers=True
        )
        fig_trends.update_layout(height=400)
        st.plotly_chart(fig_trends, use_container_width=True)

    st.markdown("#### 🎯 Performance Metrics")
    perf_cols = st.columns(3)
    with perf_cols[0]:
        create_metric_card("Overall Equipment Effectiveness", "87.3%", "2.1%")
    with perf_cols[1]:
        create_metric_card("Quality Rate", "96.8%", "0.5%")
    with perf_cols[2]:
        create_metric_card("Availability", "94.2%", "-1.2%")

def render_operations_tab(data, filters, t):
    st.markdown("### 🔧 Operations Management")

    st.markdown("#### 🚨 Active Alerts")
    alerts = [
        {"type": "warning", "message": "Workstation WS-003 requires maintenance in 2 days", "time": "2 hours ago"},
        {"type": "info", "message": "New batch started in Atelier A-01", "time": "30 minutes ago"},
        {"type": "success", "message": "Route optimization completed successfully", "time": "1 hour ago"}
    ]

    for alert in alerts:
        if alert["type"] == "warning":
            st.warning(f"⚠️ {alert['message']} ({alert['time']})")
        elif alert["type"] == "info":
            st.info(f"ℹ️ {alert['message']} ({alert['time']})")
        else:
            st.success(f"✅ {alert['message']} ({alert['time']})")

    st.markdown("#### 📋 Today's Operations")
    ops_cols = st.columns(4)
    with ops_cols[0]:
        create_metric_card("Orders Completed", "23", "3")
    with ops_cols[1]:
        create_metric_card("In Progress", "8", "-1")
    with ops_cols[2]:
        create_metric_card("Pending", "5", "2")
    with ops_cols[3]:
        create_metric_card("Quality Issues", "1", "-2")

def render_details_tab(data, filters, t):
    st.markdown("### 📋 Detailed Data Views")

    entity_options = list(data.keys())
    selected_entity = st.selectbox(
        t("select_entity", "Select entity to view:"),
        entity_options,
        key="entity_selector"
    )

    if selected_entity:
        st.subheader(f"📊 {selected_entity} Details")
        items = data[selected_entity]
        if items:
            df = pd.DataFrame() # Initialize an empty DataFrame
            if t("ateliers", "Ateliers") in selected_entity:
                df = pd.DataFrame([{
                    t("name", "Name"): item.get("name", ""),
                    t("zone", "Zone"): item.get("zone", ""),
                    t("capacity", "Capacity"): item.get("capacity", 0),
                    t("status", "Status"): item.get("status", t("active", "Active"))
                } for item in items])

            elif t("workstations", "Workstations") in selected_entity:
                df = pd.DataFrame([{
                    t("name", "Name"): item.get("name", ""),
                    t("atelier", "Atelier"): item.get("atelier", ""),
                    t("status", "Status"): item.get("status", t("active", "Active")),
                    "Efficiency": f"{np.random.randint(80, 99)}%"
                } for item in items])

            elif t("routes", "Routes") in selected_entity:
                df = pd.DataFrame([{
                    t("name", "Name"): item.get("name", ""),
                    t("product", "Product"): item.get("product_id", ""),
                    t("operations", "Operations"): np.random.randint(3, 12),
                    "Duration": f"{np.random.randint(30, 180)} min"
                } for item in items])

            elif t("products", "Products") in selected_entity:
                df = pd.DataFrame([{
                    t("name", "Name"): item.get("name", ""),
                    t("code", "Code"): item.get("code", ""),
                    t("status", "Status"): item.get("status", t("active", "Active")),
                    "Units Produced": np.random.randint(100, 1000)
                } for item in items])
            
            # Display data only if DataFrame is not empty
            if not df.empty:
                search_term = st.text_input(t("search", "🔍 Search:"), placeholder=t("type_to_search", "Type to search..."))

                if search_term:
                    mask = df.astype(str).apply(lambda x: x.str.contains(search_term, case=False, na=False)).any(axis=1)
                    df = df[mask]

                st.dataframe(
                    df,
                    use_container_width=True,
                    hide_index=True
                )

                col1, col2, col3 = st.columns([1, 1, 4])

                with col1:
                    if st.download_button(
                        t("export_csv", "📥 Export CSV"),
                        df.to_csv(index=False).encode('utf-8'),
                        f"{selected_entity.lower().replace(' ', '_')}_export.csv",
                        mime="text/csv",
                        use_container_width=True
                    ):
                        st.success(t("download_started", "Download started!"))

                with col2:
                    if st.download_button(
                        t("export_excel", "📊 Export Excel"),
                        df.to_csv(index=False).encode('utf-8'),  # Change to df.to_excel() if openpyxl is installed
                        f"{selected_entity.lower().replace(' ', '_')}_export.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True
                    ):
                        st.success(t("excel_export_started", "Excel export started!"))
            else:
                st.warning(t("no_data_for_entity", f"No data available for {selected_entity}"))
        else:
            st.warning(t("no_data_for_entity", f"No data available for {selected_entity}"))
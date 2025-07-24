# =============================================================================
# modules/measurements.py
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from utils.database import get_db_connection
from datetime import datetime

def app(lang):
    st.title(f"📏 {lang('measurements')}")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Add new measurement
    st.subheader(f"➕ {lang('add')} Measurement")
    
    # Get active gammas for dropdown
    gammas_df = pd.read_sql("""
        SELECT g.id, g.name, p.code as product_code, p.name as product_name
        FROM gammas g
        JOIN products p ON g.product_id = p.id
        WHERE g.active = 1
    """, conn)
    
    if not gammas_df.empty:
        # Select gamma first
        gamma_options = dict(zip([f"{row['product_code']} - {row['name']}" for _, row in gammas_df.iterrows()], 
                               gammas_df['id']))
        selected_gamma = st.selectbox("Control Gamma", options=list(gamma_options.keys()))
        
        if selected_gamma:
            gamma_id = gamma_options[selected_gamma]
            
            # Get features for selected gamma
            features_df = pd.read_sql("""
                SELECT f.id, f.name, gf.target, gf.usl, gf.lsl, f.unit
                FROM features f
                JOIN gamma_features gf ON f.id = gf.feature_id
                WHERE gf.gamma_id = ?
            """, conn, params=(gamma_id,))
            
            if not features_df.empty:
                with st.form("add_measurement"):
                    feature_options = dict(zip(features_df['name'], features_df['id']))
                    selected_feature = st.selectbox("Feature", options=list(feature_options.keys()))
                    
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        serial_number = st.text_input("Serial Number")
                        value = st.number_input("Measured Value", format="%.3f", value=0.0)
                    with col2:
                        operator = st.text_input("Operator", value=st.session_state.user['username'])
                        notes = st.text_area("Notes")
                    with col3:
                        # Show target and limits for reference
                        if selected_feature:
                            feature_info = features_df[features_df['name'] == selected_feature].iloc[0]
                            st.info(f"Target: {feature_info['target']}")
                            st.info(f"USL: {feature_info['usl']}")
                            st.info(f"LSL: {feature_info['lsl']}")
                            st.info(f"Unit: {feature_info['unit']}")
                    
                    if st.form_submit_button(lang("add")):
                        if serial_number and selected_feature:
                            try:
                                # Get product_id from gamma
                                product_id = pd.read_sql("""
                                    SELECT product_id FROM gammas WHERE id = ?
                                """, conn, params=(gamma_id,)).iloc[0]['product_id']
                                
                                feature_id = feature_options[selected_feature]
                                cursor.execute("""INSERT INTO measurements 
                                                (product_id, gamma_id, feature_id, serial_number, value, timestamp, operator, notes) 
                                                VALUES (?, ?, ?, ?, ?, ?, ?, ?)""", 
                                             (product_id, gamma_id, feature_id, serial_number, value, 
                                              datetime.now().isoformat(), operator, notes))
                                conn.commit()
                                st.success("Measurement added!")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error: {e}")
                        else:
                            st.error("Please fill Serial Number and select Feature")
            else:
                st.warning(f"No features configured for this gamma. Please go to {lang('gammas')} section to configure features first.")
                
                # Show link/button to gammas section
                st.info("💡 To add features to this gamma:")
                st.write("1. Go to 'Control Gammas' section")
                st.write("2. Find your gamma and expand it")
                st.write("3. Add features with Target, USL, and LSL values")
    else:
        st.warning("No active control gammas available")
    
    # Display measurements and SPC charts
    st.subheader("📊 SPC Analysis")
    
    # Filter controls
    col1, col2 = st.columns(2)
    with col1:
        # Get all gammas for filter
        all_gammas = pd.read_sql("""
            SELECT g.id, g.name, p.code as product_code
            FROM gammas g
            JOIN products p ON g.product_id = p.id
        """, conn)
        
        if not all_gammas.empty:
            gamma_filter_options = dict(zip([f"{row['product_code']} - {row['name']}" for _, row in all_gammas.iterrows()], 
                                          all_gammas['id']))
            selected_gamma_filter = st.selectbox("Select Gamma for Analysis", 
                                                options=list(gamma_filter_options.keys()), 
                                                key="gamma_filter")
    
    with col2:
        if 'selected_gamma_filter' in locals() and selected_gamma_filter:
            gamma_id_filter = gamma_filter_options[selected_gamma_filter]
            
            # Get features for selected gamma
            gamma_features = pd.read_sql("""
                SELECT f.id, f.name
                FROM features f
                JOIN gamma_features gf ON f.id = gf.feature_id
                WHERE gf.gamma_id = ?
            """, conn, params=(gamma_id_filter,))
            
            if not gamma_features.empty:
                feature_filter_options = dict(zip(gamma_features['name'], gamma_features['id']))
                selected_feature_filter = st.selectbox("Select Feature", 
                                                      options=list(feature_filter_options.keys()),
                                                      key="feature_filter")
    
    # Show SPC chart if filters are selected
    if 'selected_gamma_filter' in locals() and 'selected_feature_filter' in locals() and selected_gamma_filter and selected_feature_filter:
        feature_id_filter = feature_filter_options[selected_feature_filter]
        
        # Get measurement data
        measurements_data = pd.read_sql("""
            SELECT m.value, m.timestamp, m.serial_number, m.operator,
                   gf.target, gf.usl, gf.lsl, f.unit, f.name as feature_name
            FROM measurements m
            JOIN gamma_features gf ON m.gamma_id = gf.gamma_id AND m.feature_id = gf.feature_id
            JOIN features f ON m.feature_id = f.id
            WHERE m.gamma_id = ? AND m.feature_id = ?
            ORDER BY m.timestamp
        """, conn, params=(gamma_id_filter, feature_id_filter))
        
        if not measurements_data.empty:
            # SPC Control Chart
            fig = go.Figure()
            
            # Add measurement points
            fig.add_trace(go.Scatter(
                x=list(range(len(measurements_data))),
                y=measurements_data['value'],
                mode='lines+markers',
                name='Measurements',
                text=[f"SN: {sn}<br>Operator: {op}" for sn, op in zip(measurements_data['serial_number'], measurements_data['operator'])],
                hovertemplate='%{text}<br>Value: %{y}<extra></extra>'
            ))
            
            # Add control lines
            target = measurements_data['target'].iloc[0]
            usl = measurements_data['usl'].iloc[0]
            lsl = measurements_data['lsl'].iloc[0]
            
            fig.add_hline(y=target, line_dash="dash", line_color="green", annotation_text="Target")
            fig.add_hline(y=usl, line_dash="dash", line_color="red", annotation_text="USL")
            fig.add_hline(y=lsl, line_dash="dash", line_color="red", annotation_text="LSL")
            
            # Color points based on spec limits
            colors = []
            for value in measurements_data['value']:
                if value > usl or value < lsl:
                    colors.append('red')
                elif abs(value - target) > abs(usl - target) * 0.7:  # Warning zone
                    colors.append('orange')
                else:
                    colors.append('green')
            
            fig.update_traces(marker_color=colors)
            fig.update_layout(
                title=f"SPC Chart - {selected_feature_filter} ({measurements_data['unit'].iloc[0]})",
                xaxis_title="Sample Number",
                yaxis_title=f"Value ({measurements_data['unit'].iloc[0]})",
                showlegend=True
            )
            
            st.plotly_chart(fig, use_container_width=True)
            
            # Statistics
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Mean", f"{measurements_data['value'].mean():.3f}")
            with col2:
                st.metric("Std Dev", f"{measurements_data['value'].std():.3f}")
            with col3:
                if measurements_data['value'].std() > 0:
                    cpk = min((usl - measurements_data['value'].mean()) / (3 * measurements_data['value'].std()),
                             (measurements_data['value'].mean() - lsl) / (3 * measurements_data['value'].std()))
                    st.metric("Cpk", f"{cpk:.2f}")
                else:
                    st.metric("Cpk", "N/A")
            with col4:
                out_of_spec = len(measurements_data[(measurements_data['value'] > usl) | (measurements_data['value'] < lsl)])
                st.metric("Out of Spec", f"{out_of_spec}/{len(measurements_data)}")
            
            # Recent measurements table
            st.subheader("Recent Measurements")
            recent_measurements = measurements_data.tail(10)[['serial_number', 'value', 'timestamp', 'operator']]
            st.dataframe(recent_measurements, use_container_width=True, hide_index=True)
        else:
            st.info("No measurements found for selected gamma and feature")
    
    conn.close()
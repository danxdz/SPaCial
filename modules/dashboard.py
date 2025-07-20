import streamlit as st
from utils.mongo import get_db
import pandas as pd

def app(lang, filters):
    t = lang
    st.header(f"🏭 {t('factory_overview','Factory Overview')}")

    db = get_db()
    data = {
        t("zones","Zones"): list(db.zones.find()),
        t("ateliers","Ateliers"): list(db.ateliers.find()),
        t("workstations","Workstations"): list(db.workstations.find()),
        t("routes","Routes"): list(db.routes.find()),
        t("products","Products"): list(db.products.find()),
    }

    # Carousel with interactive cards
    cols = st.columns(len(data))
    for i, (label, items) in enumerate(data.items()):
        with cols[i]:
            st.markdown(f"""
                <div style='
                    border:1px solid #ccc;
                    border-radius:8px;
                    padding:15px;
                    text-align:center;
                    background:white;
                    height:120px;
                    box-shadow:2px 2px 6px rgba(0,0,0,0.1);
                    cursor:pointer;
                '>
                    <h3>{label}</h3>
                    <div style='font-size:24px;font-weight:bold;margin:10px;'>
                        {len(items)}
                    </div>
                </div>
            """, unsafe_allow_html=True)
            
            if st.button(t("view_details", "View Details"), key=f"btn_{label}", use_container_width=True):
                st.session_state['selected_view'] = label

    st.markdown("---")

    if 'selected_view' in st.session_state:
        selected = st.session_state['selected_view']
        st.subheader(f"📊 {selected} {t('details','Details')}")
        
        items = data[selected]
        if items:
            # Convert to DataFrame for display
            if selected == t("zones","Zones"):
                df = pd.DataFrame([{
                    t("name", "Name"): item.get("name", ""),
                    t("description", "Description"): item.get("description", ""),
                    t("status", "Status"): item.get("status", t("active", "Active"))
                } for item in items])
            
            elif selected == t("ateliers","Ateliers"):
                df = pd.DataFrame([{
                    t("name", "Name"): item.get("name", ""),
                    t("zone", "Zone"): item.get("zone", ""),
                    t("capacity", "Capacity"): item.get("capacity", 0)
                } for item in items])
            
            elif selected == t("workstations","Workstations"):
                df = pd.DataFrame([{
                    t("name", "Name"): item.get("name", ""),
                    t("atelier", "Atelier"): item.get("atelier", ""),
                    t("status", "Status"): item.get("status", t("active", "Active"))
                } for item in items])
            
            elif selected == t("routes","Routes"):
                df = pd.DataFrame([{
                    t("name", "Name"): item.get("name", ""),
                    t("product", "Product"): item.get("product_id", ""),
                    t("operations", "Operations"): len(list(db.operations.find({"route_id": item.get("_id")})))
                } for item in items])
            
            elif selected == t("products","Products"):
                df = pd.DataFrame([{
                    t("name", "Name"): item.get("name", ""),
                    t("code", "Code"): item.get("code", ""),
                    t("status", "Status"): item.get("status", t("active", "Active"))
                } for item in items])

            st.dataframe(
                df,
                use_container_width=True,
                hide_index=True
            )
            
            if st.download_button(
                f"📥 {t('export_to_csv','Export to CSV')}",
                df.to_csv(index=False).encode('utf-8'),
                f"{selected.lower()}_export.csv",
                mime="text/csv"
            ):
                st.success(t("download_started","Download started!"))
        else:
            st.info(t("no_data_available","No {type} data available.").format(type=selected))

    if filters:
        st.markdown("---")
        st.write(f"🔎 {t('active_filters','Active Filters')}:")
        for k, v in filters.items():
            st.write(f"- **{k}**: {v}")
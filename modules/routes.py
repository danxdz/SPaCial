# modules/routes.py

import streamlit as st
import pandas as pd
from bson import ObjectId
from pathlib import Path
from utils.mongo import get_db

db = get_db()

def app(lang, filters):
    """
    Routes & Operations management page.
    Uses the global `filters["product_id"]` to scope everything.
    """
    st.title(lang("routes", "Routes & Operations"))

    # 1) Ensure a product is selected in the global filters
    product_id = filters.get("product_id")
    if not product_id:
        st.info(lang("please_select_product",
                     "Please select a product in the global filters to continue."))
        

    # ————————————— Manage Routes —————————————
    st.subheader(lang("manage_routes", "Manage Routes"))

    # 2) Load & edit existing routes for this product
    if not product_id:
        routes = list(db.routes.find({}))
    else:
        routes = list(db.routes.find({"product_id": product_id}))
    if routes:
        df_routes = pd.DataFrame([{
            "_id": str(r["_id"]),
            lang("route_name","Route Name"): r["name"]
        } for r in routes])

        edited_routes = st.data_editor(
            df_routes,
            column_order=[ lang("route_name","Route Name") ],
            hide_index=True,
            use_container_width=True,
            key="routes_editor"
        )

        if st.button(lang("save_routes","💾 Save Routes")):
            origs = df_routes.to_dict("records")
            edits = edited_routes.to_dict("records")
            updates = 0
            for orig, new in zip(origs, edits):
                if orig[lang("route_name","Route Name")] != new[lang("route_name","Route Name")]:
                    db.routes.update_one(
                        {"_id": ObjectId(orig["_id"])},
                        {"$set": {"name": new[lang("route_name","Route Name")]}}
                    )
                    updates += 1
            if updates:
                st.success(lang("routes_updated", f"{updates} routes updated!"))
                st.rerun()
            else:
                st.info(lang("no_changes","No changes to save."))
    else:
        st.info(lang("no_routes","No routes found for this product."))

    # 3) Add New Route (collapsed)
    with st.expander(lang("add_route","➕ Add New Route"), expanded=False):
        with st.form("route_form", clear_on_submit=True):
            name = st.text_input(lang("route_name","Route Name"))
            submitted = st.form_submit_button(lang("create_route","Create Route"))
            if submitted:
                if not name.strip():
                    st.error(lang("fill_route_name","Please fill in the Route Name."))
                else:
                    db.routes.insert_one({
                        "product_id": product_id,
                        "name": name.strip()
                    })
                    st.success(lang("route_created","Route created successfully!"))
                    st.rerun()

    st.markdown("---")

    # ————————————— Manage Operations —————————————
    # 4) Must select one of the existing routes
    if not routes:
        return

    route_map = {r["name"]: r["_id"] for r in routes}
    selected_route = st.selectbox(
        lang("select_route","Select Route"),
        list(route_map.keys()),
        key="select_route"
    )
    route_id = route_map[selected_route]

    st.subheader(lang("operations","Operations"))
    ops = list(db.operations.find({"route_id": route_id}))
    if ops:
        df_ops = pd.DataFrame([{
            "_id": str(o["_id"]),
            lang("step_number","Step"): o.get("step_number",0),
            lang("operation_name","Operation Name"): o.get("name","")
        } for o in ops])

        edited_ops = st.data_editor(
            df_ops,
            column_order=[
                lang("step_number","Step"),
                lang("operation_name","Operation Name")
            ],
            hide_index=True,
            use_container_width=True,
            key="ops_editor"
        )

        if st.button(lang("save_operations","💾 Save Operations")):
            origs = df_ops.to_dict("records")
            edits = edited_ops.to_dict("records")
            updates = 0
            for orig, new in zip(origs, edits):
                delta = {}
                if orig[lang("step_number","Step")] != new[lang("step_number","Step")]:
                    delta["step_number"] = new[lang("step_number","Step")]
                if orig[lang("operation_name","Operation Name")] != new[lang("operation_name","Operation Name")]:
                    delta["name"] = new[lang("operation_name","Operation Name")]
                if delta:
                    db.operations.update_one(
                        {"_id": ObjectId(orig["_id"])},
                        {"$set": delta}
                    )
                    updates += 1
            if updates:
                st.success(lang("operations_updated", f"{updates} operations updated!"))
                st.rerun()
            else:
                st.info(lang("no_changes","No changes to save."))
    else:
        st.info(lang("no_operations","No operations found for this route."))

    # 5) Add New Operation (collapsed)
    with st.expander(lang("add_operation","➕ Add New Operation"), expanded=False):
        with st.form("op_form", clear_on_submit=True):
            op_name = st.text_input(lang("operation_name","Operation Name"))
            step    = st.number_input(
                lang("step_number","Step Number"),
                min_value=1,
                value=len(ops)+1
            )
            submitted = st.form_submit_button(lang("create_operation","Create Operation"))
            if submitted:
                if not op_name.strip():
                    st.error(lang("fill_operation_name","Please fill in the Operation Name."))
                else:
                    db.operations.insert_one({
                        "route_id":   route_id,
                        "name":       op_name.strip(),
                        "step_number": step
                    })
                    st.success(lang("operation_created","Operation created successfully!"))
                    st.rerun()

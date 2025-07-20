import streamlit as st
from utils.mongo import get_db

def app(lang, filters):
    st.title(lang("measurements"))
    st.sidebar.title(lang("measurements_management"))

    # get db
    db = get_db()

    # get measurements
    measurements = list(db.measurements.find({}))
    if not measurements:
        st.info(lang("no_measurements", "No measurements found."))
        

    # display measurements
    for m in measurements:
        st.markdown(f"**{m['name']}**: {m['value']} {m['unit']}")

    # add new measurement form, link to routes
    st.sidebar.subheader(lang("add_measurement", "Add Measurement"))
    # dropdown to select family or all
    selected_family = st.selectbox(lang("select_family", "Select Family"), ["All"] + [f["name"] for f in db.families.find({})])
    if selected_family != "All":
        family_id = db.families.find_one({"name": selected_family})["_id"]
    else:
        family_id = None
    # dropdown to select product or all
    selected_product = st.selectbox(lang("select_product", "Select Product"), ["All"] + [p["name"] for p in db.products.find({"family_id": family_id})] if family_id else ["All"])
    if selected_product != "All":
        product_id = db.products.find_one({"name": selected_product})["family_id"]
    else:
        product_id = None

    with st.form("add_measurement"):
        st.subheader(lang("add_measurement", "Add Measurement"))
        name = st.text_input(lang("measurement_name", "Measurement Name"))
        value = st.number_input(lang("measurement_value", "Value"), format="%.2f")
        unit = st.text_input(lang("measurement_unit", "Unit"))

        if st.form_submit_button(lang("add", "Add")):
            if name and unit:
                db.measurements.insert_one({
                    "name": name,
                    "value": value,
                    "unit": unit
                })
                st.success(lang("measurement_added", "Measurement added successfully."))
            else:
                st.error(lang("fill_all_fields", "Please fill all fields."))
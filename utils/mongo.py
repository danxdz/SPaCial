# utils/mongo.py

import streamlit as st
from pymongo import MongoClient
from pathlib import Path
import tempfile
import base64
import random
import bcrypt
from pymongo import MongoClient
import certifi



# 1) Carrega URI diretamente
MONGO_URI = st.secrets["MONGO_URI"]

# 2) Se usa X.509, grava temporariamente o PEM no disco
pem_text = st.secrets.get("MONGO_PEM")
if pem_text:
    # cria ficheiro temporário
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pem")
    tmp.write(pem_text.encode())
    tmp.flush()
    PEM_PATH = tmp.name
else:
    PEM_PATH = None

# 3) Conecta
client = MongoClient(
    MONGO_URI,
    tls=bool(PEM_PATH),
    tlsCertificateKeyFile=PEM_PATH,
    tlsCAFile=certifi.where()
)

def get_db():
    return client["spacial"]


def get_client():
    """Return the MongoClient."""
    return client


def initialize_mongo_if_needed():
    """
    If no products exist, drop & seed all collections with demo data.
    """
    db = get_db()
    if db["users"].count_documents({}) == 0:
        seed_demo_data(db)
        print("✅ MongoDB seeded successfully.")

def seed_demo_data(db):
    """
    Drop existing data and insert demo collections:
      - families
      - ateliers
      - workstations
      - products
      - routes
      - operations
      - characteristics
      - measurements (left empty)
      - users
    """
    print("🌱 Seeding MongoDB with demo data...")

    # 1) Clear existing collections
    for coll in [
        "users", "families", "products",
        "ateliers", "workstations", "routes",
        "operations", "characteristics", "measurements"
    ]:
        db[coll].delete_many({})

    # 2) Create indexes
    db.families.create_index("name", unique=True)
    db.ateliers.create_index("name", unique=True)
    db.workstations.create_index("name", unique=True)
    db.products.create_index("code", unique=True)
    db.routes.create_index([("product_id", 1), ("name", 1)], unique=True)
    db.users.create_index("username", unique=True)
    db.users.create_index("preferred_language")  # Add language index
    # 3) Seed Families
    families = [
        "Turbines", "Primary Structures", "Cockpit Components",
        "Hydraulic Systems", "Instrumentation", "Outer Skin",
        "Navigation Systems", "Landing Gear", "Flight Controls"
    ]
    family_ids = {}
    for name in families:
        res = db.families.insert_one({"name": name})
        family_ids[name] = res.inserted_id

    # 4) Seed Ateliers (Zones)
    ateliers = ["Assembly", "Machining", "Inspection", "Packaging"]
    atelier_ids = {}
    for name in ateliers:
        res = db.ateliers.insert_one({"name": name})
        atelier_ids[name] = res.inserted_id

    # 5) Seed Workstations (2 per Atelier)
    workstation_ids = {}
    for atelier, a_id in atelier_ids.items():
        for i in range(1, 3):
            ws_name = f"{atelier} WS{i}"
            res = db.workstations.insert_one({
                "name": ws_name,
                "atelier_id": a_id
            })
            workstation_ids[ws_name] = res.inserted_id

    # 6) Seed Products
    products = [
        ("AX-900", "AX Turbine"),
        ("EST-FLEXWING", "Flexible Wing"),
        ("CPK-HUDZ4", "HUD Z4 Display"),
        ("HYD-VALVEX", "Hydraulic Valve X"),
        ("INS-ALT360", "Altimeter 360")
    ]
    product_ids = {}
    for code, name in products:
        fam = random.choice(families)
        res = db.products.insert_one({
            "code": code,
            "name": name,
            "family_id": family_ids[fam],
            "description": f"{name} for aerospace applications"
        })
        product_ids[code] = res.inserted_id

    # 7) Seed Routes (2 per Product, assigned to random WS)
    route_ids = {}
    for code, pid in product_ids.items():
        for suffix in ("A", "B"):
            route_name = f"{code}-Route-{suffix}"
            ws_name = random.choice(list(workstation_ids.keys()))
            res = db.routes.insert_one({
                "product_id": pid,
                "workstation_id": workstation_ids[ws_name],
                "name": route_name
            })
            route_ids[route_name] = res.inserted_id

    # 8) Seed Operations (3 per Route)
    operation_ids = {}
    for rname, rid in route_ids.items():
        for step in range(1, 4):
            op_name = f"Op{step} - {rname}"
            res = db.operations.insert_one({
                "route_id": rid,
                "step_number": step,
                "name": op_name,
                "description": "",
                "image_path": None,
                "annotation_path": None
            })
            operation_ids[op_name] = res.inserted_id

    # 9) Seed Characteristics (2 per Operation)
    for opname, oid in operation_ids.items():
        for axis in ("X", "Y"):
            char_name = f"Char{axis} - {opname}"
            db.characteristics.insert_one({
                "operation_id": oid,
                "name": char_name,
                "designation": "Diameter",
                "unit": "mm",
                "nominal": 100.0,
                "tol_min": -0.1,
                "tol_max": 0.2,
                "image_path": None,
                "annotation_path": None
            })

    # 10) Leave `measurements` empty for real data entry

    # 11) Seed Admin User
    username = "1"
    password = "1"
    create_admin_user(username, password)

    print("🌱 Demo data insertion complete.")


def create_admin_user(username: str, password: str):
    db = get_db()
    
    try:
        # Check if user already exists
        if db.users.find_one({"username": username}):
            print(f"User {username} already exists!")
            return False
        
        # Hash the password
        hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt())
        
        # Create user document with language preference
        user = {
            "username": username,
            "password": hashed.decode(),  # store as string
            "role": "admin",
            "active": True,
            "preferred_language": "en"  # default language
        }
        
        # Insert into database
        result = db.users.insert_one(user)
        if result.inserted_id:
            print(f"✅ Admin user {username} created successfully!")
            return True
            
        print("❌ Failed to create admin user")
        return False
        
    except Exception as e:
        print(f"❌ Error creating admin user: {str(e)}")
        return False
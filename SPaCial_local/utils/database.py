
# =============================================================================
# utils/database.py
import sqlite3
import hashlib
from pathlib import Path
from datetime import datetime, timedelta
import random

DB_PATH = Path("spc.sqlite")

def get_db_connection():
    return sqlite3.connect(DB_PATH)

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def initialize_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Users table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        role TEXT NOT NULL,
        active INTEGER DEFAULT 1,
        preferred_language TEXT DEFAULT 'en'
    )
    """)
    
    # Families table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS families (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL,
        description TEXT
    )
    """)
    
    # Products table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT UNIQUE NOT NULL,
        name TEXT NOT NULL,
        family_id INTEGER,
        description TEXT,
        FOREIGN KEY (family_id) REFERENCES families(id)
    )
    """)
    
    # Features table (características a medir nos produtos)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS features (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        description TEXT,
        nominal REAL,
        tolerance_plus REAL,
        tolerance_minus REAL,
        unit TEXT,
        measurement_type TEXT,
        FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE
    )
    """)
    
    # Gammas table (grupos de controle para produtos)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS gammas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        description TEXT,
        created_date TEXT,
        active INTEGER DEFAULT 1,
        FOREIGN KEY (product_id) REFERENCES products(id)
    )
    """)
    
    # Gamma Features (features selecionadas para cada gamma)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS gamma_features (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        gamma_id INTEGER NOT NULL,
        feature_id INTEGER NOT NULL,
        target REAL,
        usl REAL,
        lsl REAL,
        FOREIGN KEY (gamma_id) REFERENCES gammas(id) ON DELETE CASCADE,
        FOREIGN KEY (feature_id) REFERENCES features(id) ON DELETE CASCADE,
        UNIQUE(gamma_id, feature_id)
    )
    """)
    
    # Measurements table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS measurements (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_id INTEGER,
        gamma_id INTEGER,
        feature_id INTEGER,
        serial_number TEXT,
        value REAL,
        timestamp TEXT,
        operator TEXT,
        notes TEXT,
        FOREIGN KEY (product_id) REFERENCES products(id),
        FOREIGN KEY (gamma_id) REFERENCES gammas(id),
        FOREIGN KEY (feature_id) REFERENCES features(id)
    )
    """)
    
    # Operations table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS operations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        gamma_id INTEGER,
        step_number INTEGER,
        name TEXT,
        description TEXT,
        image_path TEXT,
        FOREIGN KEY (gamma_id) REFERENCES gammas(id)
    )
    """)
    
    # Seed admin user if not exists
    cursor.execute("SELECT COUNT(*) FROM users WHERE username='admin'")
    if cursor.fetchone()[0] == 0:
        hashed_pw = hash_password("admin")
        cursor.execute("""INSERT INTO users (username, password, role, preferred_language) 
                         VALUES (?, ?, ?, ?)""", ("admin", hashed_pw, "admin", "en"))
        
        # Add demo data
        seed_demo_data(cursor)
    
    conn.commit()
    conn.close()

def seed_demo_data(cursor):
    # Families
    families = [
        ("Turbines", "Turbine components"),
        ("Structures", "Primary structural parts"),
        ("Electronics", "Electronic components")
    ]
    
    for name, desc in families:
        cursor.execute("INSERT OR IGNORE INTO families (name, description) VALUES (?, ?)", (name, desc))
    
    # Products
    products = [
        ("AX-900", "Turbine AX900", 1, "High-performance turbine"),
        ("HUD-Z4", "Display HUD Z4", 3, "Head-up display unit")
    ]
    
    for code, name, family_id, desc in products:
        cursor.execute("""INSERT OR IGNORE INTO products (code, name, family_id, description) 
                         VALUES (?, ?, ?, ?)""", (code, name, family_id, desc))
    
    # Features for products
    features = [
        (1, "Diameter", "Main shaft diameter", 50.0, 0.1, -0.1, "mm", "dimension"),
        (1, "Surface Roughness", "Surface finish quality", 1.6, 0.2, -0.2, "Ra", "surface"),
        (1, "Roundness", "Geometric roundness", 0.01, 0.005, -0.005, "mm", "geometric"),
        (2, "Screen Brightness", "Display brightness level", 500.0, 50.0, -50.0, "cd/m²", "optical"),
        (2, "Response Time", "Touch response time", 10.0, 2.0, -2.0, "ms", "temporal")
    ]
    
    for prod_id, name, desc, nominal, tol_plus, tol_minus, unit, meas_type in features:
        cursor.execute("""INSERT OR IGNORE INTO features 
                         (product_id, name, description, nominal, tolerance_plus, tolerance_minus, unit, measurement_type) 
                         VALUES (?, ?, ?, ?, ?, ?, ?, ?)""", 
                      (prod_id, name, desc, nominal, tol_plus, tol_minus, unit, meas_type))
    
    # Demo measurements
    for i in range(30):
        cursor.execute("""INSERT INTO measurements 
                        (product_id, feature_id, serial_number, value, timestamp, operator) 
                        VALUES (?, ?, ?, ?, ?, ?)""",
                      (1, 1, f"SN{1000+i}", 
                       round(random.normalvariate(50.0, 0.05), 3),
                       (datetime.now() - timedelta(days=random.randint(0, 30))).isoformat(),
                       "operator1"))
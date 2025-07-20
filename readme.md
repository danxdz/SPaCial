# SPaCial - Smart Production Control Application

## 🌟 Overview
SPaCial is a modern, secure web application for production control and quality management, built with Streamlit and MongoDB. It features multi-language support, role-based access control, and modular architecture.

## 🔐 Security Features
- **Authentication System**
  - Secure password hashing with bcrypt
  - Session management with encrypted cookies
  - Role-based access control (Admin/User)
  - Password change functionality
  - Session persistence

- **Data Protection**
  - MongoDB connection with SSL/TLS
  - Environment variable protection
  - Secrets management
  - Input validation and sanitization

## 🧩 Modules
1. **Dashboard** (`modules/dashboard.py`)
   - Factory overview
   - Real-time statistics
   - Interactive data cards

2. **Products** (`modules/products.py`)
   - Product management
   - Family categorization
   - Image handling

3. **Routes** (`modules/routes.py`)
   - Production route definition
   - Operation sequencing
   - Process management

4. **Characteristics** (`modules/characteristics.py`)
   - Quality characteristics
   - Measurement specifications
   - Visual annotations

5. **Users** (`modules/users.py`)
   - User management
   - Role assignment
   - Access control

## 🌍 Internationalization
- Multiple language support
- Easy translation system
- Currently supported:
  - English (en)
  - French (fr)
  - Portuguese (pt)

## 💾 Database Structure
```
MongoDB Collections:
├── users
├── families
├── products
├── ateliers
├── workstations
├── routes
├── operations
├── characteristics
└── measurements
```

## 🚀 Getting Started

### Prerequisites
```bash
python 3.8+
MongoDB 4.4+
```

### Installation
1. Clone the repository
```bash
git clone https://github.com/yourusername/SPaCial.git
cd SPaCial
```

2. Install dependencies
```bash
pip install -r requirements.txt
```

3. Set up environment variables
```bash
# Create .streamlit/secrets.toml
MONGO_URI = "your_mongodb_uri"
COOKIE_PASSWORD = "your_secret_key"
CRYPTO_KEY = "your_crypto_key"
```

4. Run the application
```bash
streamlit run main.py
```

## 🛠️ Customization

### Adding New Languages
1. Create a new language file in `languages/`:
```json
{
  "language": "Your Language",
  "language_code": "code",
  // Add translations
}
```

### Creating Custom Modules
1. Add new module file in `modules/`:
```python
def app(lang, filters):
    st.title(lang("your_module"))
    # Your module code
```

2. Register in `main.py`:
```python
modules = {
    lang("your_module"): your_module.app
}
```

### Extending Database Schema
1. Update `utils/mongo.py`
2. Add indexes if needed
3. Update seeding function

## 📦 Project Structure
```
SPaCial/
├── .streamlit/
│   └── secrets.toml
├── languages/
│   ├── lang_en.json
│   ├── lang_fr.json
│   └── lang_pt.json
├── modules/
│   ├── dashboard.py
│   ├── products.py
│   └── ...
├── utils/
│   ├── auth.py
│   ├── mongo.py
│   └── ...
├── main.py
└── requirements.txt
```

## 🔒 Security Recommendations
1. Use strong passwords
2. Regular security updates
3. Monitor access logs
4. Backup database regularly
5. Use SSL/TLS for MongoDB connection
6. Keep secrets secure

## 🤝 Contributing
1. Fork the repository
2. Create feature branch
3. Commit changes
4. Push to branch
5. Create Pull Request

## 📄 License
This project is licensed under the MIT License

## 🙏 Acknowledgments
- Streamlit team
- MongoDB team
- Contributors
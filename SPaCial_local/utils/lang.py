import json
import logging
from pathlib import Path
import streamlit as st

# Configure logging - only errors
logging.basicConfig(
    level=logging.ERROR,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Constants
LANG_DIR = Path(__file__).resolve().parent.parent / "lang"  # Changed to "lang" directory
DEFAULT_LANG = "en"

def validate_language_file(data):
    """Validate required keys in language file"""
    required_keys = ["language", "language_code", "language_select"]
    missing = [key for key in required_keys if key not in data]
    if missing:
        st.warning(f"Missing required translations: {', '.join(missing)}")
        return False
    return True

@st.cache_data(ttl=3600)
def load_language_file(lang_code):
    """Load and cache language file from lang/ directory"""
    try:
        path = LANG_DIR / f"lang_{lang_code}.json"
        if not path.exists():
            path = LANG_DIR / f"lang_{DEFAULT_LANG}.json"
            
        with path.open('r', encoding='utf-8') as f:
            return json.load(f)
            
    except Exception as e:
        logging.error(f"Error loading language file {lang_code}: {str(e)}")
        return get_default_translations()

def get_default_translations():
    """Default English translations as fallback"""
    return {
        "language": "English",
        "language_code": "en",
        "language_select": "Language",
        "welcome": "Welcome",
        "navigate": "Navigate",
        "home": "Dashboard",
        "families": "Families",
        "products": "Products", 
        "features": "Features",
        "gammas": "Control Gammas",
        "measurements": "Measurements",
        "users": "Users",
        "access_denied": "Access denied",
        "login": "Login",
        "logout": "Logout",
        "username": "Username",
        "password": "Password",
        "add": "Add",
        "edit": "Edit",
        "delete": "Delete",
        "save": "Save",
        "cancel": "Cancel",
        "name": "Name",
        "description": "Description",
        "code": "Code",
        "family": "Family",
        "active": "Active",
        "role": "Role",
        "admin": "Admin",
        "user": "User",
        "nominal": "Nominal",
        "tolerance": "Tolerance",
        "unit": "Unit",
        "measurement_type": "Measurement Type",
        "target": "Target",
        "usl": "USL",
        "lsl": "LSL",
        "value": "Value",
        "timestamp": "Timestamp",
        "operator": "Operator",
        "serial_number": "Serial Number",
        "notes": "Notes"
    }

def get_available_languages():
    """Automatically discover available language files in lang/ directory"""
    valid_languages = []
    
    # Create lang directory if it doesn't exist
    LANG_DIR.mkdir(exist_ok=True)
    
    # Look for lang_*.json files
    for path in LANG_DIR.glob("lang_*.json"):
        try:
            data = json.loads(path.read_text(encoding='utf-8'))
            if validate_language_file(data):
                # Extract language code from filename (lang_pt.json -> pt)
                code = path.stem.split("_")[1]
                valid_languages.append({
                    'code': code,
                    'name': data.get('language', code.upper()),
                    'path': path
                })
        except Exception as e:
            logging.error(f"Error processing {path}: {str(e)}")
            continue
    
    # If no valid languages found, ensure default is available
    if not valid_languages:
        valid_languages.append({
            'code': DEFAULT_LANG,
            'name': 'English',
            'path': None  # Will use default translations
        })
    
    # Sort by language name
    valid_languages.sort(key=lambda x: x['name'])
    
    return valid_languages

def get_user_language():
    """Get user's preferred language from session state"""
    return st.session_state.get("user_preferred_language")

def save_user_language(lang_code):
    """Save user's language preference to session state"""
    st.session_state["user_preferred_language"] = lang_code
    logging.info(f"Language preference saved: {lang_code}")

def reset_language_state():
    """Reset language-related session state"""
    for key in ["lang_code", "previous_lang", "lang_selector", "user_preferred_language"]:
        if key in st.session_state:
            del st.session_state[key]

def init_language():
    """Initialize language system with automatic discovery and rerun on change"""
    try:
        # Get available languages
        available_languages = get_available_languages()
        lang_codes = [lang['code'] for lang in available_languages]
        lang_names = [lang['name'] for lang in available_languages]
        
        # Get current language preference
        current = st.session_state.get("lang_code")
        if not current:
            current = get_user_language()
            if current not in lang_codes:
                current = DEFAULT_LANG
            st.session_state["lang_code"] = current
        
        # Load current language data for selector label
        current_data = load_language_file(current)
        selector_label = current_data.get("language_select", "Language")
        
        # Find current language index
        try:
            current_index = lang_codes.index(current)
        except ValueError:
            current_index = lang_codes.index(DEFAULT_LANG) if DEFAULT_LANG in lang_codes else 0
            st.session_state["lang_code"] = lang_codes[current_index]
        
        # Language selector in sidebar
        selected_name = st.sidebar.selectbox(
            f"🌐 {selector_label}",
            lang_names,
            index=current_index,
            key="lang_selector"
        )
        
        # Get selected language code
        selected_code = None
        for lang in available_languages:
            if lang['name'] == selected_name:
                selected_code = lang['code']
                break
        
        # Handle language change
        if selected_code and selected_code != current:
            st.session_state["lang_code"] = selected_code
            save_user_language(selected_code)
            st.rerun()
        
        # Load translations for current language
        translations = load_language_file(st.session_state["lang_code"])
        
        # Return translator function
        def translate(key, fallback=None):
            return translations.get(key, fallback or key)
        
        return translate

    except Exception as e:
        logging.error(f"Language initialization error: {str(e)}")
        st.error("Error initializing language system")
        
        # Return fallback translator
        default_translations = get_default_translations()
        return lambda key, fallback=None: default_translations.get(key, fallback or key)
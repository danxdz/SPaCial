import json
import logging
from pathlib import Path
import streamlit as st
from utils.mongo import get_db

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Constants
LANG_DIR = Path(__file__).resolve().parent.parent / "languages"
DEFAULT_LANG = "en"

def validate_language_file(data):
    """Validate required keys in language file"""
    required_keys = ["language", "language_code", "language_select"]
    missing = [key for key in required_keys if key not in data]
    if missing:
        logging.error(f"Language file validation failed: {missing}")
        st.warning(f"Missing required translations: {', '.join(missing)}")
        return False
    
    logging.info(f"Found valid language: {data.get('language')} ({data.get('language_code')})")
    return True

@st.cache_data(ttl=3600)  # Cache for 1 hour
def load_language_file(lang_code):
    """Load and cache language file"""
    try:
        path = LANG_DIR / f"lang_{lang_code}.json"
        if not path.exists():
            logging.warning(f"Language file not found: {path}")
            path = LANG_DIR / f"lang_{DEFAULT_LANG}.json"
            
        # Explicitly specify UTF-8 encoding
        with path.open('r', encoding='utf-8') as f:
            data = json.load(f)
            logging.info(f"Loaded language file: {path}")
            return data
            
    except Exception as e:
        logging.error(f"Error loading language file {lang_code}: {str(e)}")
        return {}

def get_available_languages():
    """Get list of valid language files"""
    valid_languages = []
    logging.info(f"Searching for language files in: {LANG_DIR}")
    
    for path in LANG_DIR.glob("lang_*.json"):
        logging.info(f"Found language file: {path}")
        try:
            data = json.loads(path.read_text(encoding='utf-8'))
            if validate_language_file(data):
                code = path.stem.split("_")[1]
                valid_languages.append(code)
                logging.info(f"Added valid language: {code}")
        except Exception as e:
            logging.error(f"Error processing {path}: {str(e)}")
            continue
            
    if not valid_languages:
        logging.warning(f"No valid languages found, using default: {DEFAULT_LANG}")
        return [DEFAULT_LANG]
        
    logging.info(f"Available languages: {valid_languages}")
    return valid_languages

def get_user_language():
    """Get user's preferred language from DB"""
    try:
        if "user" in st.session_state:
            db = get_db()
            user = db.users.find_one({"username": st.session_state["user"]["username"]})
            return user.get("preferred_language")
    except Exception as e:
        logging.error(f"Error getting user language: {str(e)}")
    return None

def save_user_language(lang_code):
    """Save user's language preference to DB"""
    if "user" not in st.session_state:
        return
        
    try:
        db = get_db()
        result = db.users.update_one(
            {"username": st.session_state["user"]["username"]},
            {"$set": {"preferred_language": lang_code}}
        )
        if not result.modified_count:
            logging.warning(f"Failed to save language preference for user {st.session_state['user']['username']}")
    except Exception as e:
        logging.error(f"Database error saving language: {str(e)}")
        reset_language_state()

def reset_language_state():
    """Reset language-related session state"""
    for key in ["lang_code", "previous_lang", "lang_selector"]:
        if key in st.session_state:
            del st.session_state[key]

def init_language():
    """Initialize language system with automatic rerun on change"""
    try:
        # Debug current state
        logging.info(f"Session state keys: {list(st.session_state.keys())}")
        
        # Get language preference with proper fallback chain
        current = st.session_state.get("lang_code")
        if not current:
            current = get_user_language() or DEFAULT_LANG
            st.session_state["lang_code"] = current
        
        logging.info(f"Current language: {current}")
        
        # Load language file
        data = load_language_file(current)
        if not data:
            logging.warning("No language data loaded, falling back to default")
            current = DEFAULT_LANG
            data = load_language_file(DEFAULT_LANG)
        
        # Get language selector label
        label = data.get("language_select", "Language")
        
        # Get available languages
        available = get_available_languages()
        logging.info(f"Available languages: {available}")
        
        try:
            current_index = available.index(current)
        except ValueError:
            logging.warning(f"Current language {current} not in available languages")
            current_index = available.index(DEFAULT_LANG)
        
        # Language selector
        choice = st.sidebar.selectbox(
            f"🌐 {label}",
            available,
            index=current_index,
            key="lang_selector"
        )
        
        # Handle language change
        if choice != current:
            logging.info(f"Language changing: {current} -> {choice}")
            st.session_state["lang_code"] = choice
            if "user" in st.session_state:
                save_user_language(choice)
            st.experimental_rerun()
        
        # Return translator function
        translations = load_language_file(choice)
        return lambda key, fallback=None: translations.get(key, fallback or key)

    except Exception as e:
        logging.error(f"Language initialization error: {str(e)}")
        st.error("Error initializing language system")
        return lambda key, fallback=None: fallback or key
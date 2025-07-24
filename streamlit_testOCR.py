import streamlit as st
from PIL import Image, ImageEnhance, ImageFilter
import numpy as np
import cv2
import os
import re
from typing import List, Dict, Tuple, Optional, Set
from datetime import datetime
import pytesseract
import easyocr
from PIL import Image
from pdf2image import convert_from_bytes # Descomenta se tiveres instalado pdf2image

# ==============================================================================
# Classes OCR - Integradas diretamente neste ficheiro para evitar problemas de importação
# ==============================================================================

class TechnicalDrawingOCR:
    """Classe especializada para OCR de desenhos técnicos"""
    
    def __init__(self, language='en', tesseract_conf_thresh=75, easyocr_conf_thresh=0.5):
        self.language = language
        self.tesseract_confidence_threshold = tesseract_conf_thresh
        self.easyocr_confidence_threshold = easyocr_conf_thresh
        self.drawing_patterns = self._load_technical_patterns()
        
        # Initialize EasyOCR reader
        try:
            # Tentar com GPU primeiro, fallback para CPU
            self.easyocr_reader = easyocr.Reader([self.language], gpu=True)
        except Exception as e:
            print(f"Erro ao inicializar EasyOCR com GPU: {e}. A tentar novamente com CPU.")
            self.easyocr_reader = easyocr.Reader([self.language], gpu=False)

    def _load_technical_patterns(self) -> Dict[str, Dict]:
        """Carrega padrões específicos para desenhos técnicos"""
        return {
            'dimensions': {
                'linear': r'(\d+\.?\d*)\s*[±]\s*(\d+\.?\d*)',
                'bilateral': r'(\d+\.?\d*)\s*\+(\d+\.?\d*)\s*-(\d+\.?\d*)',
                'unilateral_plus': r'(\d+\.?\d*)\s*\+(\d+\.?\d*)',
                'unilateral_minus': r'(\d+\.?\d*)\s*-(\d+\.?\d*)',
            },
            'geometric': {
                'diameter': r'[ØΦφ]\s*(\d+\.?\d*)\s*([±]\s*\d+\.?\d*)?',
                'radius': r'R\s*(\d+\.?\d*)\s*([±]\s*\d+\.?\d*)?',
                'square': r'□\s*(\d+\.?\d*)\s*([±]\s*\d+\.?\d*)?',
                'angle': r'(\d+\.?\d*)\s*°\s*([±]\s*\d+\.?\d*)?',
            },
            'surface': {
                'roughness_ra': r'Ra\s*(\d+\.?\d*)',
                'roughness_rz': r'Rz\s*(\d+\.?\d*)',
                'surface_finish': r'N\s*(\d+)',
            },
            'threading': {
                'metric': r'M\s*(\d+\.?\d*)\s*x\s*(\d+\.?\d*)',
                'imperial': r'(\d+\.?\d*)-(\d+)\s*(UNC|UNF|UNEF)',
                'pipe': r'(\d+\.?\d*)\s*(NPT|BSPT)',
            },
            'materials': {
                'hardness_hrc': r'HRC\s*(\d+)',
                'hardness_hb': r'HB\s*(\d+)',
                'strength': r'(\d+)\s*MPa',
            },
            'gdt': {
                'straightness': r'—',
                'flatness': r'⏥',
                'circularity': r'○',
                'cylindricity': r'⌭',
                'position': r'⊕',
                'concentricity': r'◎',
                'symmetry': r'≡',
                'runout': r'↗',
                'perpendicularity': r'⊥',
                'angularity': r'∠',
                'parallelism': r'∥',
            }
        }
    
    def preprocess_image(self, image: np.ndarray, enhance_contrast: bool = True, 
                         denoise: bool = True, sharpen: bool = True, binarize: bool = True) -> np.ndarray:
        """Pré-processamento específico para desenhos técnicos com opções"""
        
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image.copy()
        
        height, width = gray.shape
        if width < 2000: # Redimensiona se muito pequeno
            scale_factor = 2000 / width
            new_width = int(width * scale_factor)
            new_height = int(height * scale_factor)
            gray = cv2.resize(gray, (new_width, new_height), interpolation=cv2.INTER_CUBIC)
        
        processed = gray

        if enhance_contrast:
            clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
            processed = clahe.apply(processed)
        
        if denoise:
            processed = cv2.fastNlMeansDenoising(processed, h=10)
        
        if sharpen:
            kernel = np.array([[-1,-1,-1], [-1, 9,-1], [-1,-1,-1]])
            processed = cv2.filter2D(processed, -1, kernel)
        
        if binarize:
            processed = cv2.adaptiveThreshold(processed, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                                               cv2.THRESH_BINARY, 11, 2)
        return processed
    
    def run_tesseract_ocr(self, pil_image: Image.Image, psm: int = 6, whitelist: str = None) -> List[str]:
        """Executa OCR com Tesseract e retorna uma lista de textos."""
        cv_image = cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)
        processed_image = self.preprocess_image(cv_image)
        
        # Configuração OCR
        custom_config = f'--oem 3 --psm {psm}'
        if whitelist:
            custom_config += f' -c tessedit_char_whitelist={whitelist}'
        else:
            # Whitelist padrão mais segura e abrangente
            custom_config += ' -c tessedit_char_whitelist=0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz .,+-=*/\\()[]{}<>%&!?:;@#_`~|$^ØΦφ□⊕◎≡∥⊥∠↗⌭⏥○—'

        ocr_data = pytesseract.image_to_data(
            processed_image,
            lang=self.language,
            config=custom_config,
            output_type=pytesseract.Output.DICT
        )
        
        extracted_texts = []
        for i in range(len(ocr_data['text'])):
            confidence = int(ocr_data['conf'][i])
            text = ocr_data['text'][i].strip()
            if confidence > self.tesseract_confidence_threshold and text:
                extracted_texts.append(text)
        return extracted_texts

    def run_easyocr(self, pil_image: Image.Image) -> List[str]:
        """Executa OCR com EasyOCR e retorna uma lista de textos."""
        cv_image = cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)
        processed_image = self.preprocess_image(cv_image)
        
        results = self.easyocr_reader.readtext(processed_image, detail=0, 
                                                paragraph=True, text_threshold=self.easyocr_confidence_threshold)
        
        return [text.strip() for text in results if text.strip()]

    def extract_text_with_locations(self, image: np.ndarray, psm: int = 6, whitelist: str = None) -> List[Dict]:
        """Extrai texto com coordenadas precisas usando Tesseract."""
        
        processed_image = self.preprocess_image(image)
        
        custom_config = f'--oem 3 --psm {psm}'
        if whitelist:
            custom_config += f' -c tessedit_char_whitelist={whitelist}'
        else:
            custom_config += ' -c tessedit_char_whitelist=0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz .,+-=*/\\()[]{}<>%&!?:;@#_`~|$^ØΦφ□⊕◎≡∥⊥∠↗⌭⏥○—'
        
        ocr_data = pytesseract.image_to_data(
            processed_image,
            lang=self.language,
            config=custom_config,
            output_type=pytesseract.Output.DICT
        )
        
        text_regions = []
        for i in range(len(ocr_data['text'])):
            confidence = int(ocr_data['conf'][i])
            text = ocr_data['text'][i].strip()
            
            if confidence > self.tesseract_confidence_threshold and text:
                region = {
                    'text': text,
                    'confidence': confidence,
                    'bbox': {
                        'x': ocr_data['left'][i],
                        'y': ocr_data['top'][i],
                        'width': ocr_data['width'][i],
                        'height': ocr_data['height'][i]
                    },
                    'block_num': ocr_data['block_num'][i],
                    'par_num': ocr_data['par_num'][i],
                    'line_num': ocr_data['line_num'][i],
                    'word_num': ocr_data['word_num'][i]
                }
                text_regions.append(region)
        
        return text_regions
    
    # Os métodos _load_technical_patterns, _create_characteristic,
    # _process_dimension, _process_geometric, _process_surface,
    # _process_threading, _process_materials, _process_gdt
    # são os mesmos que no teu ficheiro `ocr_engine.py` original.
    # Por brevidade no exemplo, assumimos que estão completos e corretos aqui.
    # Certifica-te de que copias as definições completas desses métodos para este ficheiro.

    def identify_characteristics(self, text_regions: List[Dict]) -> List[Dict]:
        """Identifica características técnicas no texto extraído"""
        characteristics = []
        for region in text_regions:
            text = region['text']
            for category, patterns in self.drawing_patterns.items():
                for pattern_name, pattern_regex in patterns.items():
                    matches = re.finditer(pattern_regex, text, re.IGNORECASE)
                    for match in matches:
                        char = self._create_characteristic(
                            category, pattern_name, match, region, text
                        )
                        if char:
                            characteristics.append(char)
        return characteristics
    
    def _create_characteristic(self, category: str, pattern_name: str, 
                               match: re.Match, region: Dict, original_text: str) -> Optional[Dict]:
        """Cria objeto de característica baseado no padrão identificado"""
        try:
            char = {
                'category': category,
                'pattern_type': pattern_name,
                'raw_text': original_text,
                'matched_text': match.group(0),
                'confidence': region['confidence'],
                'location': region['bbox'],
                'extraction_timestamp': datetime.now().isoformat()
            }
            if category == 'dimensions':
                char.update(self._process_dimension(pattern_name, match))
            elif category == 'geometric':
                char.update(self._process_geometric(pattern_name, match))
            elif category == 'surface':
                char.update(self._process_surface(pattern_name, match))
            elif category == 'threading':
                char.update(self._process_threading(pattern_name, match))
            elif category == 'materials':
                char.update(self._process_materials(pattern_name, match))
            elif category == 'gdt':
                char.update(self._process_gdt(pattern_name, match))
            return char
        except Exception as e:
            print(f"Erro ao criar característica: {e}")
            return None
    
    def _process_dimension(self, pattern_type: str, match: re.Match) -> Dict:
        if pattern_type == 'linear':
            nominal = float(match.group(1))
            tolerance = float(match.group(2))
            return {
                'type': 'dimension', 'subtype': 'linear', 'nominal_value': nominal,
                'upper_tolerance': tolerance, 'lower_tolerance': -tolerance, 'unit': 'mm',
                'name': f'Dimensão {nominal}±{tolerance}'
            }
        elif pattern_type == 'bilateral':
            nominal = float(match.group(1))
            upper = float(match.group(2))
            lower = float(match.group(3))
            return {
                'type': 'dimension', 'subtype': 'bilateral', 'nominal_value': nominal,
                'upper_tolerance': upper, 'lower_tolerance': -lower, 'unit': 'mm',
                'name': f'Dimensão {nominal} +{upper}/-{lower}'
            }
        elif pattern_type == 'unilateral_plus':
            nominal = float(match.group(1))
            plus_tol = float(match.group(2))
            return {
                'type': 'dimension', 'subtype': 'unilateral_plus', 'nominal_value': nominal,
                'upper_tolerance': plus_tol, 'lower_tolerance': 0.0, 'unit': 'mm',
                'name': f'Dimensão {nominal}+{plus_tol}'
            }
        elif pattern_type == 'unilateral_minus':
            nominal = float(match.group(1))
            minus_tol = float(match.group(2))
            return {
                'type': 'dimension', 'subtype': 'unilateral_minus', 'nominal_value': nominal,
                'upper_tolerance': 0.0, 'lower_tolerance': -minus_tol, 'unit': 'mm',
                'name': f'Dimensão {nominal}-{minus_tol}'
            }
        return {}
    
    def _process_geometric(self, pattern_type: str, match: re.Match) -> Dict:
        value = float(match.group(1))
        tolerance_text = match.group(2) if len(match.groups()) > 1 and match.group(2) else '±0.1'
        tol_match = re.search(r'(\d+\.?\d*)', tolerance_text)
        tolerance = float(tol_match.group(1)) if tol_match else 0.1
        base_data = {
            'nominal_value': value, 'upper_tolerance': tolerance, 'lower_tolerance': -tolerance, 'unit': 'mm'
        }
        if pattern_type == 'diameter':
            base_data.update({'type': 'diameter', 'subtype': 'circular', 'name': f'Ø{value} {tolerance_text}'})
        elif pattern_type == 'radius':
            base_data.update({'type': 'radius', 'subtype': 'circular', 'name': f'R{value} {tolerance_text}'})
        elif pattern_type == 'angle':
            base_data.update({'type': 'angle', 'subtype': 'angular', 'unit': 'degrees', 'name': f'{value}° {tolerance_text}'})
        elif pattern_type == 'square':
            base_data.update({'type': 'square', 'subtype': 'linear', 'name': f'□{value} {tolerance_text}'})
        return base_data
    
    def _process_surface(self, pattern_type: str, match: re.Match) -> Dict:
        value = float(match.group(1))
        if pattern_type == 'roughness_ra':
            return {
                'type': 'roughness', 'subtype': 'ra', 'nominal_value': value,
                'upper_tolerance': value * 0.2, 'lower_tolerance': 0, 'unit': 'μm', 'name': f'Ra {value}'
            }
        elif pattern_type == 'roughness_rz':
            return {
                'type': 'roughness', 'subtype': 'rz', 'nominal_value': value,
                'upper_tolerance': value * 0.2, 'lower_tolerance': 0, 'unit': 'μm', 'name': f'Rz {value}'
            }
        elif pattern_type == 'surface_finish':
            return {
                'type': 'surface_finish',
                'subtype': 'n_class',
                'nominal_value': value,
                'upper_tolerance': 0,
                'lower_tolerance': 0,
                'unit': 'N',
                'name': f'N{value}'
            }
        return {}
    
    def _process_threading(self, pattern_type: str, match: re.Match) -> Dict:
        if pattern_type == 'metric':
            diameter = float(match.group(1))
            pitch = float(match.group(2))
            return {
                'type': 'thread', 'subtype': 'metric', 'nominal_value': diameter,
                'pitch': pitch, 'upper_tolerance': 0.1, 'lower_tolerance': -0.1, 'unit': 'mm',
                'name': f'M{diameter}x{pitch}'
            }
        elif pattern_type == 'imperial':
            major_dia = float(match.group(1))
            tpi = int(match.group(2))
            series = match.group(3)
            return {
                'type': 'thread', 'subtype': 'imperial', 'nominal_value': major_dia,
                'tpi': tpi, 'series': series, 'upper_tolerance': 0.005, 'lower_tolerance': -0.005,
                'unit': 'inch', 'name': f'{major_dia}-{tpi} {series}'
            }
        elif pattern_type == 'pipe':
            size = float(match.group(1))
            thread_type = match.group(2)
            return {
                'type': 'thread', 'subtype': 'pipe', 'nominal_value': size,
                'thread_type': thread_type, 'unit': 'inch', 'name': f'Pipe {size} {thread_type}'
            }
        return {}
    
    def _process_materials(self, pattern_type: str, match: re.Match) -> Dict:
        value = float(match.group(1))
        if pattern_type == 'hardness_hrc':
            return {
                'type': 'hardness', 'subtype': 'hrc', 'nominal_value': value,
                'upper_tolerance': 2, 'lower_tolerance': -2, 'unit': 'HRC', 'name': f'HRC {value}'
            }
        elif pattern_type == 'hardness_hb':
            return {
                'type': 'hardness', 'subtype': 'hb', 'nominal_value': value,
                'upper_tolerance': 5, 'lower_tolerance': -5,
                'unit': 'HB', 'name': f'HB {value}'
            }
        elif pattern_type == 'strength':
            return {
                'type': 'strength', 'subtype': 'tensile', 'nominal_value': value,
                'unit': 'MPa', 'name': f'{value} MPa'
            }
        return {}
    
    def _process_gdt(self, pattern_type: str, match: re.Match) -> Dict:
        return {
            'type': 'gdt', 'subtype': pattern_type, 'symbol': match.group(0),
            'name': f'GD&T: {pattern_type}',
            'requires_datum': pattern_type in ['position', 'perpendicularity', 'angularity', 'parallelism']
        }


# ==============================================================================
# Funções Auxiliares de Imagem
# ==============================================================================

def rotate_image(image: Image.Image, angle: int) -> Image.Image:
    """Rotaciona uma imagem PIL por um dado ângulo."""
    return image.rotate(angle, expand=True)

def combine_ocr_results(results_list: List[List[str]]) -> List[str]:
    """Combina múltiplas listas de resultados OCR e remove duplicados."""
    combined_set = set()
    for results in results_list:
        combined_set.update(results)
    return sorted(list(combined_set))

def combine_text_regions_results(results_list: List[List[Dict]]) -> List[Dict]:
    """Combina múltiplas listas de regiões de texto OCR e tenta remover duplicados
       baseado no texto e numa localização aproximada para evitar resultados idênticos de rotações.
    """
    combined_regions: List[Dict] = []
    seen_texts_and_approx_locations: Set[Tuple[str, int, int]] = set()

    for regions in results_list:
        for region in regions:
            text = region['text']
            # Usa uma localização aproximada para deduplicação (arredonda para múltiplos de 10 ou 20)
            # Isto é necessário porque a rotação pode ligeiramente mudar as coordenadas exatas
            x_approx = int(region['bbox']['x'] / 20) * 20 
            y_approx = int(region['bbox']['y'] / 20) * 20 
            
            unique_key = (text, x_approx, y_approx)

            if unique_key not in seen_texts_and_approx_locations:
                combined_regions.append(region)
                seen_texts_and_approx_locations.add(unique_key)
    
    return combined_regions


# ==============================================================================
# Aplicação Streamlit
# ==============================================================================

def app():
    st.set_page_config(page_title="OCR Técnico", layout="wide")
    st.title("📐 Detecção de Texto e Características em Desenhos Técnicos")
    st.markdown("Carregue uma imagem de um desenho técnico para extrair texto e identificar características.")

    st.sidebar.header("Opções de Imagem")
    
    uploaded_file = st.sidebar.file_uploader("📎 Carregar Imagem (JPG, PNG) ou PDF", type=["jpg", "jpeg", "png", "pdf"])
    
    if uploaded_file is not None:
        if uploaded_file.type == "application/pdf":
            st.info("A processar PDF... isto pode demorar se tiver muitas páginas.")
            # Converte o PDF em uma lista de imagens PIL
            # Nota: 'poppler_path' pode ser necessário no Windows, apontando para a pasta bin do Poppler
            # images = convert_from_bytes(uploaded_file.read(), poppler_path=r"C:\path\to\poppler\bin")
            images = convert_from_bytes(uploaded_file.read()) # Para Linux/macOS ou se Poppler estiver no PATH
            
            all_combined_tesseract_results = []
            all_combined_easyocr_results = []
            all_combined_tesseract_regions_with_loc = []
            all_identified_characteristics = []

            for i, page_image in enumerate(images):
                st.subheader(f"Página {i+1} do PDF")
                st.image(page_image, caption=f"Página {i+1}", use_container_width=True)

                # Chama as tuas funções OCR para cada 'page_image'
                # Adaptar a lógica de rotação e combinação para cada página
                
                # Exemplo para Tesseract
                page_tesseract_results = ocr_engine_instance.run_tesseract_ocr(page_image, psm=tesseract_psm)
                all_combined_tesseract_results.extend(page_tesseract_results)

                # Exemplo para EasyOCR
                page_easyocr_results = ocr_engine_instance.run_easyocr(page_image)
                all_combined_easyocr_results.extend(page_easyocr_results)
                
                # Para características e bounding boxes, usarias a page_image convertida para cv2
                cv_page_image = cv2.cvtColor(np.array(page_image), cv2.COLOR_RGB2BGR)
                page_regions_with_loc = ocr_engine_instance.extract_text_with_locations(cv_page_image, psm=tesseract_psm)
                all_combined_tesseract_regions_with_loc.extend(page_regions_with_loc)
                
                # Caracteristicas por página
                page_characteristics = ocr_engine_instance.identify_characteristics(page_regions_with_loc)
                all_identified_characteristics.extend(page_characteristics)

            # Depois de processar todas as páginas, apresentarias os resultados combinados
            # ... (Lógica de exibição dos resultados combinados de todas as páginas) ...

        else: # Ficheiro é uma imagem (JPG, PNG)
            image_to_process = Image.open(uploaded_file)
    
    
    use_default_image = st.sidebar.checkbox("Usar exemplo: expanded-shaft-sketch.jpg", True)

    default_image_path = "expanded-shaft-sketch-with-polishing-and-degrees-GKERAM.jpg" # Use a mais genérica para teste

    if use_default_image:
        if os.path.exists(default_image_path):
            image_to_process = Image.open(default_image_path)
            st.info(f"Usando a imagem de exemplo: {default_image_path}")
        else:
            st.error(f"Imagem de exemplo '{default_image_path}' não encontrada. Por favor, carregue uma imagem ou verifique o caminho do arquivo.")
            use_default_image = False 
    
    if not use_default_image and uploaded_file is not None:
        image_to_process = Image.open(uploaded_file)
        st.info("Usando a imagem carregada.")
    elif not use_default_image and uploaded_file is None:
        st.warning("Por favor, carregue uma imagem ou selecione a opção de imagem de exemplo para continuar.")
        image_to_process = None

    if image_to_process is not None:
        st.subheader("🖼️ Imagem Original")
        st.image(image_to_process, caption="Imagem para processamento", use_container_width=True)

        st.sidebar.header("Configurações OCR")
        tesseract_conf_thresh = st.sidebar.slider("Confiança Mínima Tesseract (%)", 0, 100, 70) 
        easyocr_conf_thresh = st.sidebar.slider("Confiança Mínima EasyOCR (0.0-1.0)", 0.0, 1.0, 0.4)
        tesseract_psm = st.sidebar.selectbox("Tesseract PSM (Page Segmentation Mode)", 
                                             options=[1,3,4,5,6,7,8,9,10,11,12,13], index=5)
        
        perform_rotation_ocr = st.sidebar.checkbox("Tentar OCR com Rotações (90°, 270°)", True)

        st.subheader("⚙️ Processando a Imagem...")
        with st.spinner("A executar OCR e a identificar características... Isto pode demorar um pouco."):
            ocr_engine_instance = TechnicalDrawingOCR(language='en', 
                                                      tesseract_conf_thresh=tesseract_conf_thresh, 
                                                      easyocr_conf_thresh=easyocr_conf_thresh)

            # --- Processamento da Imagem Original ---
            cv_image_original = cv2.cvtColor(np.array(image_to_process), cv2.COLOR_RGB2BGR)
            processed_image_for_display = ocr_engine_instance.preprocess_image(cv_image_original)
            
            st.subheader("✨ Imagem Pré-processada (O que o OCR vê)")
            st.image(processed_image_for_display, caption="Imagem após pré-processamento", use_container_width=True, channels="GRAY")

            # Armazena os resultados de cada rotação
            all_tesseract_raw_results: List[List[str]] = []
            all_easyocr_raw_results: List[List[str]] = []
            all_tesseract_regions_with_loc: List[List[Dict]] = []

            # Processa a imagem original
            all_tesseract_raw_results.append(ocr_engine_instance.run_tesseract_ocr(image_to_process, psm=tesseract_psm))
            all_easyocr_raw_results.append(ocr_engine_instance.run_easyocr(image_to_process))
            all_tesseract_regions_with_loc.append(ocr_engine_instance.extract_text_with_locations(cv_image_original, psm=tesseract_psm))
            
            if perform_rotation_ocr:
                st.info("A processar rotações da imagem para OCR.")
                # Processa imagem rotacionada 90 graus
                image_90 = rotate_image(image_to_process, 90)
                cv_image_90 = cv2.cvtColor(np.array(image_90), cv2.COLOR_RGB2BGR)
                all_tesseract_raw_results.append(ocr_engine_instance.run_tesseract_ocr(image_90, psm=tesseract_psm))
                all_easyocr_raw_results.append(ocr_engine_instance.run_easyocr(image_90))
                # Note: extract_text_with_locations para rotações pode requerer transformação de coordenadas
                # Para simplificar agora, só usamos para a imagem original na identificação de características.
                # Se for necessário, a lógica para transformar bounding boxes de volta para as coordenadas originais é complexa.
                # Por agora, a identificação de características será baseada apenas no OCR da imagem original.

                # Processa imagem rotacionada 270 graus (ou -90)
                image_270 = rotate_image(image_to_process, 270)
                cv_image_270 = cv2.cvtColor(np.array(image_270), cv2.COLOR_RGB2BGR)
                all_tesseract_raw_results.append(ocr_engine_instance.run_tesseract_ocr(image_270, psm=tesseract_psm))
                all_easyocr_raw_results.append(ocr_engine_instance.run_easyocr(image_270))
            
            # Combina todos os resultados
            combined_tesseract_results = combine_ocr_results(all_tesseract_raw_results)
            combined_easyocr_results = combine_ocr_results(all_easyocr_raw_results)
            # A identificação de características e bounding boxes ainda é feita apenas na imagem original
            # para evitar a complexidade de transformar coordenadas das imagens rotacionadas.
            combined_tesseract_regions_with_loc = combine_text_regions_results(all_tesseract_regions_with_loc)

            # Identificação de características é feita apenas uma vez, com os resultados da melhor "view" ou da original.
            # Por simplicidade e para manter a precisão das coordenadas, usaremos apenas as regiões da imagem original.
            identified_characteristics = ocr_engine_instance.identify_characteristics(all_tesseract_regions_with_loc[0])


        # --- Exibir Resultados OCR Brutos ---
        st.subheader("Output Bruto do OCR (Combinado de todas as Rotações)")
        col1, col2 = st.columns(2)
        with col1:
            st.write("🧠 **EasyOCR**")
            if combined_easyocr_results:
                st.code("\n".join(combined_easyocr_results))
            else:
                st.info("Nada reconhecido com EasyOCR (ajuste o limiar).")
        with col2:
            st.write("🔤 **Tesseract**")
            if combined_tesseract_results:
                st.code("\n".join(combined_tesseract_results))
            else:
                st.info("Nada reconhecido com Tesseract (ajuste o limiar ou PSM).")

        # --- Comparação dos Motores ---
        st.subheader("Comparação dos Motores OCR (Combinado)")
        easyocr_set_combined = set(combined_easyocr_results)
        tesseract_set_combined = set(combined_tesseract_results)
        common_combined = easyocr_set_combined.intersection(tesseract_set_combined)
        
        if common_combined:
            st.success(f"✅ Textos coincidentes (após rotações): {len(common_combined)} linhas")
            st.code("\n".join(sorted(list(common_combined))))
        else:
            st.info("ℹ️ Nenhum texto coincidente entre os dois OCRs nos limiares atuais.")

        # --- Exibir Todo o Texto Detetado e Anotar Imagem ---
        st.subheader("🔍 Texto Detetado e Bounding Boxes (da Imagem Original)")
        # Anotar a imagem original com os resultados da análise da imagem original
        annotated_image = cv_image_original.copy()

        BOX_COLOR = (0, 255, 0)
        TEXT_COLOR = (255, 0, 0)
        FONT = cv2.FONT_HERSHEY_SIMPLEX
        FONT_SCALE = 0.6
        THICKNESS = 2
        TEXT_BG_COLOR = (255, 255, 255)

        all_found_texts_list = []

        if combined_tesseract_regions_with_loc: # Use combined regions for listing
            for i, region in enumerate(combined_tesseract_regions_with_loc):
                text = region['text']
                confidence = region['confidence']
                bbox = region['bbox']
                x, y, w, h = bbox['x'], bbox['y'], bbox['width'], bbox['height']

                all_found_texts_list.append(f"- '{text}' (Confiança: {confidence:.2f}%, Posição: x={x}, y={y}, w={w}, h={h})")

                # Desenha apenas se a bbox estiver dentro dos limites da imagem original
                if x >= 0 and y >= 0 and x+w <= annotated_image.shape[1] and y+h <= annotated_image.shape[0]:
                    cv2.rectangle(annotated_image, (x, y), (x + w, y + h), BOX_COLOR, THICKNESS)

                    display_text = text
                    (text_width, text_height), baseline = cv2.getTextSize(display_text, FONT, FONT_SCALE, THICKNESS)

                    text_x = x
                    text_y = y - 5 
                    if text_y < text_height + 5: 
                        text_y = y + h + text_height + 5

                    cv2.rectangle(annotated_image, (text_x, text_y - text_height - baseline), 
                                (text_x + text_width, text_y + baseline), TEXT_BG_COLOR, -1) 
                    cv2.putText(annotated_image, display_text, (text_x, text_y), FONT, FONT_SCALE, TEXT_COLOR, THICKNESS, cv2.LINE_AA)
            
            st.text_area("Lista de Todo o Texto Detetado (Tesseract - Incluindo rotações para detecção):", "\n".join(all_found_texts_list), height=200)

            annotated_pil_image = Image.fromarray(cv2.cvtColor(annotated_image, cv2.COLOR_BGR2RGB))
            st.image(annotated_pil_image, caption="Imagem com Texto Detetado Realçado (Bounding Boxes da Imagem Original)", use_container_width=True)

        else:
            st.info("Nenhum texto foi detetado na imagem com confiança suficiente para ser realçado ou listado.")

        # --- Exibir Características Técnicas Identificadas ---
        st.subheader("📊 Características Técnicas Identificadas")
        if identified_characteristics:
            features_display = []
            for i, char in enumerate(identified_characteristics):
                features_display.append({
                    "ID": i + 1,
                    "Categoria": char.get('category', 'N/A'),
                    "Tipo de Padrão": char.get('pattern_type', 'N/A'),
                    "Valor/Símbolo": char.get('name', char.get('matched_text', 'N/A')),
                    "Confiança (%)": f"{char.get('confidence', 0):.2f}"
                })
            st.dataframe(features_display, use_container_width=True)
        else:
            st.info("Nenhuma característica técnica foi identificada com os padrões definidos ou confiança suficiente.")

# Garante que a aplicação Streamlit é executada quando o script é iniciado
if __name__ == "__main__":
    app()
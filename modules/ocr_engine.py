import pytesseract
import easyocr
import numpy as np
from PIL import Image
from transformers import TrOCRProcessor, VisionEncoderDecoderModel
from transformers import DonutProcessor, VisionEncoderDecoderModel as DonutModel
import torch

easy_reader = easyocr.Reader(['en'], gpu=False)
trocr_processor = TrOCRProcessor.from_pretrained("microsoft/trocr-base-handwritten")
trocr_model = VisionEncoderDecoderModel.from_pretrained("microsoft/trocr-base-handwritten")

donut_processor = DonutProcessor.from_pretrained("naver-clova-ix/donut-base")
donut_model = DonutModel.from_pretrained("naver-clova-ix/donut-base")

device = "cuda" if torch.cuda.is_available() else "cpu"
trocr_model.to(device)
donut_model.to(device)

def run_tesseract(image: Image.Image) -> list[str]:
    text = pytesseract.image_to_string(image)
    return [line.strip() for line in text.splitlines() if line.strip()]

def run_easyocr(image: Image.Image) -> list[str]:
    results = easy_reader.readtext(np.array(image))
    return [text for _, text, _ in results]

def run_trocr(image: Image.Image) -> list[str]:
    pixel_values = trocr_processor(images=image, return_tensors="pt").pixel_values.to(device)
    generated_ids = trocr_model.generate(pixel_values)
    generated_text = trocr_processor.batch_decode(generated_ids, skip_special_tokens=True)[0]
    return [generated_text]

def run_donut(image: Image.Image) -> list[str]:
    image = image.convert("RGB")
    pixel_values = donut_processor(image, return_tensors="pt").pixel_values.to(device)
    task_prompt = "<s_docvqa><s_question>What is written?</s_question><s_answer>"
    decoder_input_ids = donut_processor.tokenizer(task_prompt, add_special_tokens=False, return_tensors="pt")["input_ids"].to(device)
    outputs = donut_model.generate(pixel_values, decoder_input_ids=decoder_input_ids)
    return [donut_processor.batch_decode(outputs, skip_special_tokens=True)[0]]

def run_all(image: Image.Image) -> dict:
    return {
        "tesseract": run_tesseract(image),
        "easyocr": run_easyocr(image),
        "trocr": run_trocr(image),
        "donut": run_donut(image)
    }

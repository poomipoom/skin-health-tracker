from inference_sdk import InferenceHTTPClient, InferenceConfiguration
from collections import Counter


def infer_image_with_sdk(image_path):
    CLIENT = InferenceHTTPClient(
        api_url="https://detect.roboflow.com",
        api_key="APIKEY"  # ใช้ environment variable เพื่อความปลอดภัย
    )
    custom_configuration = InferenceConfiguration(confidence_threshold=0.10)
    CLIENT.configure(custom_configuration)
    
    result = CLIENT.infer(image_path, model_id="skin-disease-detection-vtmmm/1")
    predictions = result['predictions']
    
    class_counts = Counter()
    for prediction in predictions:
        class_counts[prediction['class']] += 1
    
    return class_counts

from PIL import Image
from transformers import AutoImageProcessor, AutoModelForImageClassification
import torch

def infer_image_with_transformers(image_path):
    processor = AutoImageProcessor.from_pretrained("dima806/skin_types_image_detection")
    model = AutoModelForImageClassification.from_pretrained("dima806/skin_types_image_detection")

    image = Image.open(image_path)
    inputs = processor(images=image, return_tensors="pt")

    with torch.no_grad():
        outputs = model(**inputs)
    
    logits = outputs.logits
    predicted_class_id = logits.argmax(-1).item()
    predicted_class_label = model.config.id2label[predicted_class_id]
    
    return predicted_class_label

def infer_image_with_facedetect(image_path):
    CLIENT = InferenceHTTPClient(
        api_url="https://detect.roboflow.com",
        api_key="APIKEY"  # ใช้ environment variable เพื่อความปลอดภัย
    )
    custom_configuration = InferenceConfiguration(confidence_threshold=0.05)
    CLIENT.configure(custom_configuration)
    
    result = CLIENT.infer(image_path, model_id="face-detection-mik1i/21")
    predictions = result['predictions']

    if predictions:
        # ดึง prediction ที่มีค่า confidence สูงสุด (กรณีมีหลาย detection)
        best_prediction = max(predictions, key=lambda x: x['confidence'])
        
        x = best_prediction['x']
        y = best_prediction['y']
        width = best_prediction['width']
        height = best_prediction['height']
        
        # คำนวณตำแหน่ง bounding box
        left = x - (width / 2)
        top = y - (height / 2)
        right = x + (width / 2)
        bottom = y + (height / 2)
        
        return left, top, right, bottom
    else:
        raise ValueError("No predictions found")


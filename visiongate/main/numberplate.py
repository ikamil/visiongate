import os.path

# import onnxruntime
from typing import List, Union
import cv2
import numpy as np
from django.conf import settings
# from paddleocr import PaddleOCR
# ocr = PaddleOCR(lang="en")

# для инференса на ГПУ передать провайдер ['CUDAExecutionProvider']
# можно передать несколько провайдеров через запятую, будет использован первый доступный из них
# providers = ["CPUExecutionProvider"]
# onnx_model = onnxruntime.InferenceSession(path_or_bytes=os.path.join(settings.BASE_DIR, "main", "license_plate_detector.onnx"), providers=providers)

# нормировка и преобразование картинки к нужной размерности
def preprocess_image(cv2_image: np.ndarray) -> np.ndarray:
    # преобразование формата каналов из BGR в RGB
    np_image = cv2.cvtColor(cv2_image, cv2.COLOR_BGR2RGB)
    # изменение размера
    np_image = cv2.resize(np_image, (640, 640))
    # нормировка из [0 - 255] в [0 - 1]
    np_image = np_image / 255.0
    # преобразование типа даны в float32
    np_image = np_image.astype(np.float32)
    # перестановка местами размерностей из [H, W, C] в [C, H, W]
    np_image = np_image.transpose(2, 0, 1)
    # добавление размерности по батчу [1, C, H, W]
    input_np_image = np.expand_dims(np_image, axis=0)
    return input_np_image

def intersection(box1: np.ndarray, box2: np.ndarray) -> float:
    box1_x1, box1_y1, box1_x2, box1_y2 = box1[:4]
    box2_x1, box2_y1, box2_x2, box2_y2 = box2[:4]
    x1 = max(box1_x1, box2_x1)
    y1 = max(box1_y1, box2_y1)
    x2 = min(box1_x2, box2_x2)
    y2 = min(box1_y2, box2_y2)
    return (x2 - x1) * (y2 - y1)

# расчет площади объединения двух боксов box1 и box2
def union(box1: np.ndarray, box2: np.ndarray) -> float:
    box1_x1, box1_y1, box1_x2, box1_y2 = box1[:4]
    box2_x1, box2_y1, box2_x2, box2_y2 = box2[:4]
    box1_area = (box1_x2 - box1_x1) * (box1_y2 - box1_y1)
    box2_area = (box2_x2 - box2_x1) * (box2_y2 - box2_y1)
    return box1_area + box2_area - intersection(box1, box2)

# метрика IOU между двумя боксами - площадь пересечения поделить на площадь объединения
def iou(box1: np.ndarray, box2: np.ndarray) -> float:
    return intersection(box1, box2) / union(box1, box2)

# преобразование одного элемента выхода модели (параметры бокса) к нужному формату
# из [x_координата_центра, y_координата_центра, ширина, высота]
# в координаты левого верхнего и правого нижнего углов [x1, y1, x2, y2]
# а так же преобразование координат к системе координат изначальной картинки, до обрезки
# а так же извлечение вероятности предсказанного класса для текущего бокса
# возвращает маасив в формате [4_коодинаты_углов_бокса, индекс_класса, вероятность_класса]
def convert_detections(detection_row: np.ndarray, img_width: int, img_height: int) -> List[Union[float, int]]:
    x, y, w, h = detection_row[:4]
    x1 = (x - w/2) / 640 * img_width
    y1 = (y - h/2) / 640 * img_height
    x2 = (x + w/2) / 640 * img_width
    y2 = (y + h/2) / 640 * img_height
    # извлечь вероятноть и индекс класса, в котором модель максимально уверенна
    prob = detection_row[4:].max()
    class_id = detection_row[4:].argmax()
    return [int(x1), int(y1), int(x2), int(y2), class_id, prob]

# преобразование выходов модели в нужный формат, удаление лишних боксов по вероятности и по IOU
def model_output_to_boxes(model_output, img_width, img_height, prob_threshold, iou_threshold) -> List[List[Union[int, float]]]:
    detections = model_output[0]
    # перестановка размерностей выходов модели для удобства, чтобы кол-во боксов стояло нулевой размерностью
    detections = detections.transpose()

    # конвертация детекций в формат [4_координаты, индекс_класса, вероятность_класса]
    detections = [convert_detections(detection, img_width, img_height) for detection in detections]
    # отвеивание только боксов вероятность которых более prob_threshold (0.5)
    boxes = [detection for detection in detections if detection[5] > prob_threshold]
    # сортировка по убыванию боксов по вероятности
    boxes.sort(key=lambda x: x[5], reverse=True)

    # итоговый список для боксов который будет возвращатся
    boxes_list = []
    # удаление лишних боксов (которые сильно пересекаются), пока не останется ни одного
    while len(boxes) > 0:
        # добавляем первый самый вероятный бокс в итоговый список
        boxes_list.append(boxes[0])
        # из остальных оставляем только те которые пересекаются с текущим не сильно (меньше iou_threshold)
        boxes = [box for box in boxes if iou(box, boxes[0]) < iou_threshold]
    return boxes_list


def perform_ocr(image_array, ocr):
    if image_array is None:
        raise ValueError("Image is None")

    # Perform OCR on the image array
    results = ocr.ocr(image_array, rec=True)  # rec=True enables text recognition
    detected_text = []

    # Process OCR results
    if results[0] is not None:
        for result in results[0]:
            text = result[1][0]
            detected_text.append(text)

    # Join all detected texts into a single string
    return "".join(detected_text)


def boxes(frame):
    # предикт кадра моделью
    # results = model(frame)
    # image_path = 'слоны.jpg'
    # cv2_image = cv2.imread(image_path)
    cv2_image = frame
    input_np_image = preprocess_image(cv2_image)
    # вход словарь для модели inputs в формате {строка_название_входа: входной_объект}
    inputs = {settings.ONNX_MODEL.get_inputs()[0].name: input_np_image}

    # предикт
    outputs = settings.ONNX_MODEL.run(None, inputs)

    # на выходе 8400 бокса с 84 параметрами у каждого [x, y, w, h, вероятности_для_80_классов]
    # порог вероятности для отсеивания боксов
    prob_threshold = 0.5
    # порог IOU для отсеивания боксов
    iou_threshold = 0.7

    # получение высоты и ширины изображения
    img_height = cv2_image.shape[0]
    img_width = cv2_image.shape[1]

    # проверка работы функции преобразования выходов модели в нужный формат
    boxes_list = model_output_to_boxes(outputs, img_width, img_height, prob_threshold, iou_threshold)
    return boxes_list


def numbers(frame, boxes_list, ocr):
    texts = []
    for box in boxes_list:
        x1, y1, x2, y2 = box[:4]
        crop = frame[y1:y2, x1:x2]
        crop = cv2.resize(crop, (120, 70))
        text = perform_ocr(crop, ocr)
        text = text.replace('(', '').replace(')', '').replace(',', '').replace(']', '').replace('-', ' ')
        texts.append(text.strip().upper())

    return texts

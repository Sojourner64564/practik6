"""Все настройки и пороги проекта в одном месте."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
VIDEOS_DIR = DATA / "videos"
AUDIO_DIR = DATA / "audio"
FRAMES_DIR = DATA / "frames"
JSON_DIR = DATA / "json"
OUT = ROOT / "out"
ERRORS_CSV = DATA / "errors.csv"
SOURCES_FILE = ROOT / "sources.txt"

MAX_VIDEOS = 10                 # учебный лимит числа роликов

# --- Кадры -------------------------------------------------------------
FRAME_SAMPLE_FPS = 1.0          # желаемая частота выборки кадров (кадр/с)
MAX_FRAMES_PER_VIDEO = 900      # потолок кадров на ролик (защита памяти/диска)
FRAME_MAX_WIDTH = 640           # кадры уменьшаются до этой ширины
JPEG_QUALITY = 80

# --- YOLO --------------------------------------------------------------
YOLO_MODEL = "yolov8n.pt"
YOLO_CONF_SAVE = 0.25           # все детекции пишутся с этого порога
YOLO_CONF = 0.4                 # порог для анализа (событий)
YOLO_IMGSZ = 640
YOLO_BATCH = 16
OBJECT_MIN_DURATION = 3.0       # объект должен непрерывно быть в кадре >= 3 с
OBJECT_GAP_FACTOR = 1.5         # разрыв > 1.5 шага выборки прерывает интервал
CONF_SWEEP = [0.25, 0.30, 0.35, 0.40, 0.45, 0.50, 0.60, 0.70, 0.80]

# --- Смена сцен --------------------------------------------------------
SCENE_CORR_THRESHOLD = 0.6      # корреляция HSV-гистограмм < 0.6 => смена сцены

# --- Аудио -------------------------------------------------------------
AUDIO_SR = 16000
LOUD_WINDOW_SEC = 0.5
LOUD_SIGMA = 2.0                # громкий момент: dB >= среднее + 2σ
LOUD_MIN_DB = -45.0             # абсолютный пол (чтобы тишина не давала «пиков»)
WHISPER_MODEL = "tiny"
WHISPER_LANG = "ru"
WHISPER_MAX_NO_SPEECH = 0.6     # сегменты с большей вероятностью «не речь» отбрасываются

# --- Темы --------------------------------------------------------------
TOPIC_METHOD = "kmeans"         # kmeans | hdbscan
TOPIC_K = 3
HDBSCAN_MIN_CLUSTER = 2

# --- Поиск / дашборд ---------------------------------------------------
PREFIX_LEN = 5                  # поиск в панели — по префиксу из 5 букв
SERVER_PORTS = (8000, 9000)

"""Шаг 3. Детекция объектов (YOLO) и смена сцен (корреляция HSV-гистограмм)."""
import config as cfg
from common import absp, get_logger, json_path, load_json, save_json, imread_u

log = get_logger()
_MODEL = None


def get_model():
    global _MODEL
    if _MODEL is None:
        from ultralytics import YOLO
        _MODEL = YOLO(cfg.YOLO_MODEL)  # при первом запуске модель скачивается
    return _MODEL


def scene_series(frames_info: dict) -> list:
    """corr между соседними выбранными кадрами; низкая корреляция => смена сцены."""
    import cv2
    series, prev = [], None
    for f in frames_info["frames"]:
        img = imread_u(absp(f["file"]))
        if img is None:
            continue
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        h = cv2.calcHist([hsv], [0, 1], None, [16, 16], [0, 180, 0, 256])
        #h = cv2.calcHist([hsv], [0, 1], None, [50, 60], [0, 180, 0, 256])
        cv2.normalize(h, h, 0, 1, cv2.NORM_MINMAX)
        if prev is not None:
            corr = float(cv2.compareHist(prev, h, cv2.HISTCMP_CORREL))
            series.append({"t": f["t"], "file": f["file"], "corr": round(corr, 4)})
        prev = h
    return series


def detect(frames_info: dict, conf: float) -> list:
    model = get_model()
    frames, dets = frames_info["frames"], []
    for i in range(0, len(frames), cfg.YOLO_BATCH):
        chunk = frames[i:i + cfg.YOLO_BATCH]
        imgs = [imread_u(absp(f["file"])) for f in chunk]
        results = model.predict(imgs, conf=conf, imgsz=cfg.YOLO_IMGSZ, verbose=False, device="cpu")
        #results = model.predict([str(absp(f["file"])) for f in chunk], conf=conf, imgsz=cfg.YOLO_IMGSZ, verbose=False, device="cpu")
        for f, r in zip(chunk, results):
            for b in r.boxes:
                dets.append({"t": f["t"], "file": f["file"], "cls": r.names[int(b.cls[0])],
                             "conf": round(float(b.conf[0]), 3)})
    return dets


def run(vid: str, force: bool = False, skip_yolo: bool = False):
    fr = load_json(json_path(vid, "frames"))
    if not fr:
        raise RuntimeError("нет кадров (decompose не выполнен)")
    sp = json_path(vid, "scenes")
    if force or not sp.exists():
        save_json(sp, scene_series(fr))
    if skip_yolo:
        return
    yp = json_path(vid, "yolo")
    if force or not yp.exists():
        save_json(yp, detect(fr, cfg.YOLO_CONF_SAVE))  # пишем всё от 0.25
        log.info("[%s] YOLO готово", vid)

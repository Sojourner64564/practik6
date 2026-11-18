"""Вспомогательные утилиты: логирование, JSON, errors.csv."""
import csv
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

import config as cfg


def get_logger(name: str = "practice6") -> logging.Logger:
    log = logging.getLogger(name)
    if not log.handlers:
        h = logging.StreamHandler(sys.stdout)
        h.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", "%H:%M:%S"))
        log.addHandler(h)
        log.setLevel(logging.INFO)
    return log


def ensure_dirs():
    for d in (cfg.VIDEOS_DIR, cfg.AUDIO_DIR, cfg.FRAMES_DIR, cfg.JSON_DIR, cfg.OUT):
        d.mkdir(parents=True, exist_ok=True)


def rel(p) -> str:
    """Путь относительно корня проекта (POSIX) — переносимо между ОС."""
    return Path(p).resolve().relative_to(cfg.ROOT).as_posix()


def absp(r) -> Path:
    return cfg.ROOT / r


def load_json(path, default=None):
    path = Path(path)
    if not path.exists():
        return default
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def save_json(path, obj):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


def json_path(vid: str, kind: str) -> Path:
    return cfg.JSON_DIR / f"{vid}.{kind}.json"


def load_meta(vid: str) -> dict:
    return load_json(json_path(vid, "meta"), {})


def save_meta(meta: dict):
    save_json(json_path(meta["id"], "meta"), meta)


def list_video_ids() -> list:
    return sorted(p.name[: -len(".meta.json")] for p in cfg.JSON_DIR.glob("*.meta.json"))


def log_error(video_id: str, stage: str, message: str):
    """Дописывает причину пропуска/сбоя в data/errors.csv (без дублей)."""
    cfg.ERRORS_CSV.parent.mkdir(parents=True, exist_ok=True)
    message = " ".join(str(message).split())[:500]
    seen = set()
    exists = cfg.ERRORS_CSV.exists()
    if exists:
        with open(cfg.ERRORS_CSV, encoding="utf-8", newline="") as f:
            for row in csv.reader(f):
                if len(row) >= 4:
                    seen.add((row[1], row[2], row[3]))
    if (video_id, stage, message) in seen:
        return
    with open(cfg.ERRORS_CSV, "a", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        if not exists:
            w.writerow(["timestamp", "video_id", "stage", "message"])
        w.writerow([datetime.now().isoformat(timespec="seconds"), video_id, stage, message])
    get_logger().warning("[%s] %s: %s", video_id, stage, message)


def fmt_time(t: float) -> str:
    t = int(round(t))
    h, rem = divmod(t, 3600)
    m, s = divmod(rem, 60)
    return f"{h:d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"

def imread_u(path):
    import cv2, numpy as np
    return cv2.imdecode(np.fromfile(str(path), dtype=np.uint8), cv2.IMREAD_COLOR)

def imwrite_u(path, img, quality=80):
    import cv2
    ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, quality])
    if ok:
        buf.tofile(str(path))
    return ok
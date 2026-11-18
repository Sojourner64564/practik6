"""Шаг 2. Метаданные (ffprobe), аудио (ffmpeg), кадры (OpenCV), веб-совместимость."""
import json
import math
import shutil
import subprocess
from fractions import Fraction

import config as cfg
from common import (absp, get_logger, json_path, load_meta, log_error,
                    rel, save_json, save_meta, imwrite_u)

log = get_logger()


def _run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")


def probe(path) -> dict:
    r = _run(["ffprobe", "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(path)])
    if r.returncode != 0:
        raise RuntimeError(f"ffprobe: {r.stderr.strip()[:200]}")
    data = json.loads(r.stdout)
    v = next((s for s in data["streams"] if s.get("codec_type") == "video"), None)
    a = next((s for s in data["streams"] if s.get("codec_type") == "audio"), None)
    if v is None:
        raise RuntimeError("в файле нет видеопотока")

    def to_fps(s):
        try:
            f = float(Fraction(s))
            return f if f > 0 else 0.0
        except Exception:
            return 0.0

    fps = to_fps(v.get("avg_frame_rate", "0")) or to_fps(v.get("r_frame_rate", "0")) or 25.0
    dur = float(data.get("format", {}).get("duration") or v.get("duration") or 0)
    return {
        "fps": round(fps, 3), "duration": round(dur, 2),
        "width": v.get("width"), "height": v.get("height"),
        "vcodec": v.get("codec_name"), "pix_fmt": v.get("pix_fmt"),
        "acodec": a.get("codec_name") if a else None,
        "has_audio": a is not None,
        "container": data.get("format", {}).get("format_name", ""),
    }


def _browser_ok(info: dict) -> bool:
    return (info["vcodec"] == "h264" and "mp4" in info["container"]
            and info["pix_fmt"] in ("yuv420p", "yuvj420p")
            and (not info["has_audio"] or info["acodec"] in ("aac", "mp3")))


def ensure_web_video(meta: dict, info: dict):
    """Rutube часто отдаёт MPEG-TS/нестандартные кодеки — конвертируем в H.264/AAC MP4."""
    src = absp(meta["video"])
    if _browser_ok(info):
        meta["web_video"] = meta["video"]
        return
    dst = cfg.VIDEOS_DIR / f"{meta['id']}.web.mp4"
    if not dst.exists():
        log.info("[%s] конвертирую в H.264/AAC для браузера", meta["id"])
        r = _run(["ffmpeg", "-y", "-i", str(src), "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2",
                  "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-pix_fmt", "yuv420p",
                  "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", str(dst)])
        if r.returncode != 0:
            dst.unlink(missing_ok=True)
            raise RuntimeError(f"ffmpeg convert: {r.stderr.strip()[-200:]}")
    meta["web_video"] = rel(dst)


def extract_audio(meta: dict, force: bool):
    if not meta.get("has_audio"):
        log_error(meta["id"], "decompose", "no_audio: в ролике нет звуковой дорожки")
        meta["audio"] = None
        return
    dst = cfg.AUDIO_DIR / f"{meta['id']}.wav"
    if force or not dst.exists():
        r = _run(["ffmpeg", "-y", "-i", str(absp(meta["video"])), "-vn", "-ac", "1",
                  "-ar", str(cfg.AUDIO_SR), "-c:a", "pcm_s16le", str(dst)])
        if r.returncode != 0:
            dst.unlink(missing_ok=True)
            log_error(meta["id"], "decompose", f"audio_extract_failed: {r.stderr.strip()[-200:]}")
            meta["audio"] = None
            return
    meta["audio"] = rel(dst)


def extract_frames(meta: dict, force: bool):
    """Шаг кадров считается по fps ролика, кадры пишутся на диск по одному (память не растёт)."""
    import cv2
    fpath = json_path(meta["id"], "frames")
    fdir = cfg.FRAMES_DIR / meta["id"]
    if not force and fpath.exists() and fdir.exists() and any(fdir.iterdir()):
        return
    if fdir.exists():
        shutil.rmtree(fdir)
    fdir.mkdir(parents=True, exist_ok=True)

    cap = cv2.VideoCapture(str(absp(meta["web_video"])))
    if not cap.isOpened():
        raise RuntimeError("OpenCV не смог открыть видео")
    fps = meta["fps"] or cap.get(cv2.CAP_PROP_FPS) or 25.0
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    step = max(1, round(fps / cfg.FRAME_SAMPLE_FPS))
    if total > 0:
        step = max(step, math.ceil(total / cfg.MAX_FRAMES_PER_VIDEO))
    frames, idx = [], 0
    while cap.grab():
        if idx % step == 0:
            ok, img = cap.retrieve()
            if ok:
                h, w = img.shape[:2]
                if w > cfg.FRAME_MAX_WIDTH:
                    img = cv2.resize(img, (cfg.FRAME_MAX_WIDTH, int(h * cfg.FRAME_MAX_WIDTH / w)))
                p = fdir / f"{idx:07d}.jpg"
                if imwrite_u(p, img, cfg.JPEG_QUALITY):
                    frames.append({"i": idx, "t": round(idx / fps, 3), "file": rel(p)})
                #cv2.imwrite(str(p), img, [cv2.IMWRITE_JPEG_QUALITY, cfg.JPEG_QUALITY])
                #frames.append({"i": idx, "t": round(idx / fps, 3), "file": rel(p)})
        idx += 1
    cap.release()
    if not frames:
        raise RuntimeError("не удалось извлечь ни одного кадра")
    save_json(fpath, {"fps": fps, "step": step, "step_sec": round(step / fps, 4), "frames": frames})
    log.info("[%s] кадров: %d (шаг %d, fps %.2f)", meta["id"], len(frames), step, fps)


def decompose(vid: str, force: bool = False) -> bool:
    meta = load_meta(vid)
    try:
        info = probe(absp(meta["video"]))
        meta.update(info)
        ensure_web_video(meta, info)
        extract_audio(meta, force)
        save_meta(meta)
        extract_frames(meta, force)
        return True
    except Exception as e:
        log_error(vid, "decompose", str(e))
        return False

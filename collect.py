"""Шаг 1. Скачивание видео (yt-dlp) и сбор локальных файлов."""
import hashlib
import shutil
from pathlib import Path

import config as cfg
from common import (absp, get_logger, load_meta, log_error, rel, save_meta)

log = get_logger()
VIDEO_EXT = {".mp4", ".mkv", ".webm", ".mov", ".ts", ".avi", ".m4v", ".flv"}


def read_sources(path) -> list:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Файл источников не найден: {path}")
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            out.append(line)
    return out[: cfg.MAX_VIDEOS]


def is_url(s: str) -> bool:
    return s.lower().startswith(("http://", "https://"))


def resolve_local(src: str) -> Path:
    p = Path(src).expanduser()
    for cand in (p, cfg.ROOT / p):
        if cand.exists():
            return cand.resolve()
    return p


def make_id(src: str) -> str:
    if is_url(src):
        return "net_" + hashlib.md5(src.encode("utf-8")).hexdigest()[:10]
    return "local_" + hashlib.md5(str(resolve_local(src)).encode("utf-8")).hexdigest()[:8]


def _find_downloaded(vid: str):
    cands = [p for p in cfg.VIDEOS_DIR.glob(f"{vid}.*")
             if p.suffix.lower() in VIDEO_EXT and not p.name.endswith(".web.mp4")]
    return max(cands, key=lambda p: p.stat().st_size) if cands else None


def _download(src: str, vid: str) -> dict:
    from yt_dlp import YoutubeDL
    opts = {
        "format": "bv*[height<=720]+ba/b[height<=720]/b",
        "outtmpl": str(cfg.VIDEOS_DIR / f"{vid}.%(ext)s"),
        "merge_output_format": "mp4",
        "quiet": True, "noprogress": True, "retries": 3, "socket_timeout": 30,
        "noplaylist": True,
    }
    with YoutubeDL(opts) as ydl:
        info = ydl.extract_info(src, download=True)
    path = _find_downloaded(vid)
    if path is None:
        raise RuntimeError("yt-dlp завершился, но файл видео не найден")
    return {
        "title": info.get("title") or vid,
        "uploader": info.get("uploader") or info.get("channel") or "",
        "description": info.get("description") or "",
        "upload_date": info.get("upload_date") or "",
        "tags": info.get("tags") or [],
        "duration": info.get("duration"),
        "video": rel(path),
    }


def collect_one(src: str, force: bool = False):
    vid = make_id(src)
    meta = load_meta(vid)
    if meta and not force and meta.get("video") and absp(meta["video"]).exists():
        log.info("[%s] уже собрано (кэш)", vid)
        return vid
    try:
        if is_url(src):
            log.info("[%s] скачиваю %s", vid, src)
            fields = _download(src, vid)
            meta = {"id": vid, "source": src, "kind": "url", **fields}
        else:
            p = resolve_local(src)
            if not p.exists():
                raise FileNotFoundError(f"локальный файл не найден: {src}")
            # ASCII-имя файла: кириллица в путях ломает ffmpeg/OpenCV на части ОС
            dst = cfg.VIDEOS_DIR / f"{vid}{p.suffix.lower()}"
            shutil.copy2(p, dst)
            meta = {"id": vid, "source": str(p), "kind": "local", "title": p.stem,
                    "uploader": "", "description": "", "upload_date": "", "tags": [],
                    "duration": None, "video": rel(dst)}
        save_meta(meta)
        return vid
    except Exception as e:  # ролик недоступен — пропускаем, не падаем
        log_error(vid, "collect", f"{src}: {e}")
        return None


def collect(sources_file=None, force: bool = False) -> list:
    sources = read_sources(sources_file or cfg.SOURCES_FILE)
    if not sources:
        log.warning("sources.txt пуст — добавьте ссылки или пути к видео")
    ids = []
    for s in sources:
        vid = collect_one(s, force)
        if vid:
            ids.append(vid)
    log.info("Собрано роликов: %d из %d", len(ids), len(sources))
    return ids

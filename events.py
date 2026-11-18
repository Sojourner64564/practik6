"""Шаг 5. Временные события: интервалы, метки, уверенность."""
import bisect

import config as cfg
from common import get_logger, json_path, load_json, load_meta, save_json

log = get_logger()


def _nearest_frame(times, files, t):
    if not times:
        return None
    i = bisect.bisect_left(times, t)
    cands = [j for j in (i - 1, i) if 0 <= j < len(times)]
    return files[min(cands, key=lambda j: abs(times[j] - t))]


def loud_events(loud: dict, sigma: float = cfg.LOUD_SIGMA) -> list:
    import numpy as np
    db_all = np.array(loud.get("db", []), dtype=float)
    db = db_all
    active = db_all[db_all > cfg.LOUD_MIN_DB]
    if len(active) < 4:
        return []
    #mean, std = float(active.mean()), float(active.std())

    med = float(np.median(active))
    mad = float(np.median(np.abs(active - med))) * 1.4826
    mean, std = med, (mad if mad > 1e-6 else float(active.std()))

    thr = max(mean + sigma * std, cfg.LOUD_MIN_DB)
    w = loud["window"]
    idx = [i for i, v in enumerate(db) if v >= thr]
    events, group = [], []
    for i in idx + [None]:
        if group and (i is None or i != group[-1] + 1):
            peak = float(db[group].max())
            z = (peak - mean) / std if std > 1e-6 else 0.0
            events.append({"type": "loud_peak", "label": f"{peak:.1f} dB",
                           "start": round(group[0] * w, 2), "end": round((group[-1] + 1) * w, 2),
                           "confidence": round(min(1.0, max(0.0, z / 4.0)), 3)})
            group = []
        if i is not None:
            group.append(i)
    return events


# def scene_events(series: list, thr: float = cfg.SCENE_CORR_THRESHOLD) -> list:
#     return [{"type": "scene_change", "label": f"corr={s['corr']:.2f}", "start": s["t"], "end": s["t"],
#              "confidence": round(min(1.0, max(0.0, 1.0 - s["corr"])), 3), "frame": s["file"]}
#             for s in series if s["corr"] < thr]

def scene_events(series: list, thr: float = cfg.SCENE_CORR_THRESHOLD, min_gap: float = 2.0) -> list:
    out, last = [], -1e9
    for s in series:
        if s["corr"] < thr and s["t"] - last >= min_gap:
            out.append({"type": "scene_change", "label": f"corr={s['corr']:.2f}", "start": s["t"], "end": s["t"],
                        "confidence": round(min(1.0, max(0.0, 1.0 - s["corr"])), 3), "frame": s["file"]})
            last = s["t"]
    return out

def object_events(dets: list, step_sec: float, conf: float = cfg.YOLO_CONF,
                  min_dur: float = cfg.OBJECT_MIN_DURATION) -> list:
    """Класс YOLO, непрерывно присутствующий >= min_dur секунд (каждый кадр = step_sec)."""
    by = {}
    for d in dets:
        if d["conf"] >= conf:
            by.setdefault(d["cls"], {}).setdefault(d["t"], []).append(d)
    events = []
    for cls, tmap in by.items():
        times = sorted(tmap)
        groups = [[times[0]]]
        for t in times[1:]:
            if t - groups[-1][-1] <= step_sec * cfg.OBJECT_GAP_FACTOR:
                groups[-1].append(t)
            else:
                groups.append([t])
        for g in groups:
            start, end = g[0], g[-1] + step_sec
            if end - start + 1e-6 < min_dur:
                continue
            ds = [d for t in g for d in tmap[t]]
            best = max(ds, key=lambda d: d["conf"])
            events.append({"type": "object", "label": cls, "start": round(start, 2), "end": round(end, 2),
                           "confidence": round(sum(d["conf"] for d in ds) / len(ds), 3),
                           "frame": best["file"]})
    return events


def speech_events(asr: dict, times, files) -> list:
    out = []
    for s in (asr or {}).get("segments", []):
        mid = (s["start"] + s["end"]) / 2
        out.append({"type": "speech", "label": s["text"], "start": s["start"], "end": s["end"],
                    "confidence": s["conf"], "frame": _nearest_frame(times, files, mid)})
    return out


def build(vid: str, conf: float = cfg.YOLO_CONF) -> list:
    fr = load_json(json_path(vid, "frames"), {"frames": [], "step_sec": 1.0})
    times = [f["t"] for f in fr["frames"]]
    files = [f["file"] for f in fr["frames"]]
    ev = []
    loud = load_json(json_path(vid, "loud"))
    if loud:
        for e in loud_events(loud):
            e["frame"] = _nearest_frame(times, files, e["start"])
            ev.append(e)
    scenes = load_json(json_path(vid, "scenes"))
    if scenes:
        ev += scene_events(scenes)
    dets = load_json(json_path(vid, "yolo"))
    if dets:
        ev += object_events(dets, fr["step_sec"], conf)
    ev += speech_events(load_json(json_path(vid, "asr")), times, files)
    for e in ev:
        e["video_id"] = vid
        e["duration"] = round(e["end"] - e["start"], 2)
    ev.sort(key=lambda e: (e["start"], e["type"]))
    save_json(json_path(vid, "events"), ev)
    log.info("[%s] событий: %d", vid, len(ev))
    return ev

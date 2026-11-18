"""Ручная валидация событий: выборка -> out/validation.csv -> подсчёт точности."""
import argparse
import shutil

import pandas as pd

import config as cfg
from common import absp, fmt_time, load_meta

TYPES = ["loud_peak", "scene_change", "object"]
PATH = cfg.OUT / "validation.csv"


def make(n: int, seed: int = 42):
    src = cfg.OUT / "events.csv"
    if not src.exists():
        raise SystemExit("Нет out/events.csv — сначала запустите run_pipeline.py")
    df = pd.read_csv(src, encoding="utf-8-sig")
    fdir = cfg.OUT / "validation_frames"
    fdir.mkdir(exist_ok=True)
    rows = []
    for t in TYPES:
        sub = df[df["type"] == t]
        sub = sub.sample(min(n, len(sub)), random_state=seed) if len(sub) else sub
        for _, r in sub.iterrows():
            k = len(rows) + 1
            frame = ""
            if isinstance(r["frame"], str) and r["frame"] and absp(r["frame"]).exists():
                frame = f"validation_frames/{k:03d}.jpg"
                shutil.copy2(absp(r["frame"]), cfg.OUT / frame)
            video = load_meta(r["video_id"]).get("web_video", "")
            rows.append({"id": k, "video_id": r["video_id"], "type": t, "label": r["label"],
                         "start": r["start"], "end": r["end"], "confidence": r["confidence"],
                         "frame": frame, "video_at": f"{video} @ {fmt_time(r['start'])}", "verdict": ""})
    pd.DataFrame(rows).to_csv(PATH, index=False, encoding="utf-8-sig")
    print(f"Создано {len(rows)} строк: {PATH}\nПроверьте кадры/видео и поставьте 1 (верно) или 0 (ошибка) в 'verdict'.")


def score():
    if not PATH.exists():
        raise SystemExit("Нет out/validation.csv — сначала: python3 validate.py --n 5")
    df = pd.read_csv(PATH, dtype=str, encoding="utf-8-sig").fillna("")
    df["v"] = pd.to_numeric(df["verdict"].str.strip(), errors="coerce")
    done = df[df["v"].isin([0, 1])]
    if done.empty:
        return print("Вердикты не заполнены")
    print(f"Проверено: {len(done)} из {len(df)}")
    for t, g in done.groupby("type"):
        print(f"  {t:13s} точность {g['v'].mean():.2f}  ({int(g['v'].sum())}/{len(g)})")
    print(f"  {'ИТОГО':13s} точность {done['v'].mean():.2f}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=5, help="событий каждого типа в выборке")
    ap.add_argument("--score", action="store_true", help="посчитать точность по заполненному файлу")
    a = ap.parse_args()
    score() if a.score else make(a.n)

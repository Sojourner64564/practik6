"""Шаг 7. Отчёт, графики и CSV-таблицы."""
import csv

import config as cfg
from common import fmt_time, get_logger, json_path, list_video_ids, load_json, load_meta
from events import object_events
from textutils import label_ru

log = get_logger()
TYPES = ["speech", "loud_peak", "scene_change", "object"]


def _plt():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    return plt


def write_csvs(ids):
    cfg.OUT.mkdir(parents=True, exist_ok=True)
    topics = load_json(cfg.JSON_DIR / "topics.json", {"assignment": {}})
    ev_rows, tr_rows, vid_rows = [], [], []
    for v in ids:
        m = load_meta(v)
        ev = load_json(json_path(v, "events"), [])
        for e in ev:
            ev_rows.append([v, e["type"], e["label"], e["start"], e["end"], e["duration"],
                            e["confidence"], e.get("frame") or ""])
        for s in load_json(json_path(v, "asr"), {"segments": []})["segments"]:
            tr_rows.append([v, s["start"], s["end"], s["conf"], s["text"]])
        vid_rows.append([v, m.get("title", ""), m.get("source", ""), m.get("duration"), m.get("fps"),
                         m.get("has_audio"), len(ev), topics["assignment"].get(v, "")])

    def dump(name, header, rows):
        with open(cfg.OUT / name, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.writer(f)
            w.writerow(header)
            w.writerows(rows)

    dump("events.csv", ["video_id", "type", "label", "start", "end", "duration", "confidence", "frame"], ev_rows)
    dump("transcripts.csv", ["video_id", "start", "end", "confidence", "text"], tr_rows)
    dump("videos.csv", ["video_id", "title", "source", "duration", "fps", "has_audio", "n_events", "topic"], vid_rows)
    return ev_rows


def plot_conf_sweep(ids, conf):
    """Обоснование порога YOLO: как число детекций/событий зависит от conf."""
    plt = _plt()
    rows = []
    for thr in cfg.CONF_SWEEP:
        dets_n = ev_n = 0
        for v in ids:
            dets = load_json(json_path(v, "yolo"))
            fr = load_json(json_path(v, "frames"))
            if not dets or not fr:
                continue
            dets_n += sum(1 for d in dets if d["conf"] >= thr)
            ev_n += len(object_events(dets, fr["step_sec"], thr))
        rows.append((thr, dets_n, ev_n))
    if not any(r[1] for r in rows):
        return None
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.plot([r[0] for r in rows], [r[1] for r in rows], "o-", color="#2563eb", label="детекции")
    ax.set_xlabel("порог conf")
    ax.set_ylabel("число детекций", color="#2563eb")
    ax2 = ax.twinx()
    ax2.plot([r[0] for r in rows], [r[2] for r in rows], "s--", color="#ef4444", label="события object (≥3 с)")
    ax2.set_ylabel("число событий", color="#ef4444")
    ax.axvline(conf, color="gray", ls=":")
    ax.set_title(f"Выбор порога YOLO (выбран {conf})")
    fig.tight_layout()
    fig.savefig(cfg.OUT / "conf_sweep.png", dpi=130)
    plt.close(fig)
    return rows


def plot_counts(ev_rows):
    plt = _plt()
    counts = {t: sum(1 for r in ev_rows if r[1] == t) for t in TYPES}
    fig, ax = plt.subplots(figsize=(6, 3.5))
    ax.bar(counts.keys(), counts.values(), color=["#3b82f6", "#ef4444", "#a855f7", "#10b981"])
    ax.set_title("События по типам")
    fig.tight_layout()
    fig.savefig(cfg.OUT / "events_by_type.png", dpi=130)
    plt.close(fig)
    return counts


def plot_topics():
    plt = _plt()
    t = load_json(cfg.JSON_DIR / "topics.json")
    if not t:
        return
    fig, ax = plt.subplots(figsize=(7, 3.5))
    ax.barh([c["label"] for c in t["clusters"]], [len(c["videos"]) for c in t["clusters"]], color="#6366f1")
    ax.set_xlabel("роликов")
    ax.set_title("Тематические кластеры")
    fig.tight_layout()
    fig.savefig(cfg.OUT / "topics.png", dpi=130)
    plt.close(fig)


def plot_timeline(vid):
    plt = _plt()
    meta, ev = load_meta(vid), load_json(json_path(vid, "events"), [])
    if not ev:
        return
    lanes = [("речь", "speech", "#3b82f6"), ("громкость", "loud_peak", "#ef4444"), ("сцены", "scene_change", "#a855f7")]
    objs = sorted({e["label"] for e in ev if e["type"] == "object"})[:8]
    fig, ax = plt.subplots(figsize=(10, 1.2 + 0.35 * (len(lanes) + len(objs))))
    names = []
    for i, (name, t, col) in enumerate(lanes):
        names.append(name)
        ax.broken_barh([(e["start"], max(e["duration"], 0.4)) for e in ev if e["type"] == t],
                       (i - 0.35, 0.7), color=col)
    for j, o in enumerate(objs, start=len(lanes)):
        names.append(label_ru(o))
        ax.broken_barh([(e["start"], e["duration"]) for e in ev if e["type"] == "object" and e["label"] == o],
                       (j - 0.35, 0.7), color="#10b981")
    ax.set_yticks(range(len(names)))
    ax.set_yticklabels(names)
    ax.invert_yaxis()
    ax.set_xlabel("время, с")
    ax.set_title(meta.get("title", vid)[:80])
    fig.tight_layout()
    (cfg.OUT / "timelines").mkdir(exist_ok=True)
    fig.savefig(cfg.OUT / "timelines" / f"{vid}.png", dpi=110)
    plt.close(fig)


def write_markdown(ids, counts, sweep, conf):
    topics = load_json(cfg.JSON_DIR / "topics.json", {"clusters": [], "method": "-"})
    L = ["# Отчёт: мультимодальный анализ видео\n", f"Роликов обработано: **{len(ids)}**\n",
         "## Сводка по типам событий\n", "| тип | число |", "|---|---|"]
    L += [f"| {t} | {n} |" for t, n in counts.items()]
    L += ["\n## Ролики\n", "| id | название | длит. | событий |", "|---|---|---|---|"]
    for v in ids:
        m = load_meta(v)
        L.append(f"| {v} | {m.get('title', '')[:60]} | {fmt_time(m.get('duration') or 0)} | "
                 f"{len(load_json(json_path(v, 'events'), []))} |")
    L += [f"\n## Темы ({topics['method']})\n"]
    for c in topics["clusters"]:
        L.append(f"- **{c['label']}** — роликов: {len(c['videos'])} ({', '.join(c['videos'])})")
    L += ["\n## Пороги\n",
          f"- громкость: среднее + {cfg.LOUD_SIGMA}σ (не ниже {cfg.LOUD_MIN_DB} dB)",
          f"- смена сцен: корреляция HSV < {cfg.SCENE_CORR_THRESHOLD}",
          f"- объекты: YOLO пишет от conf {cfg.YOLO_CONF_SAVE}, анализ с conf {conf}, "
          f"интервал ≥ {cfg.OBJECT_MIN_DURATION} с"]
    if sweep:
        L.append("\nЧувствительность к conf (график `conf_sweep.png`):\n")
        L += ["| conf | детекций | событий |", "|---|---|---|"] + [f"| {a} | {b} | {c} |" for a, b, c in sweep]
    errs = cfg.ERRORS_CSV
    if errs.exists():
        L += ["\n## Ошибки и пропуски (data/errors.csv)\n", "```", errs.read_text(encoding="utf-8").strip(), "```"]
    L += ["\n## Этика\n", "Эмоции и «внимание» по лицам не оцениваются (152-ФЗ).",
          "\n## Ограничения\n", "Поиск в панели — по префиксу, в консоли — по лемме; семантический поиск требует эмбеддингов."]
    (cfg.OUT / "report.md").write_text("\n".join(L), encoding="utf-8")


def run(conf: float = cfg.YOLO_CONF):
    ids = list_video_ids()
    cfg.OUT.mkdir(parents=True, exist_ok=True)
    ev_rows = write_csvs(ids)
    sweep = plot_conf_sweep(ids, conf)
    counts = plot_counts(ev_rows)
    plot_topics()
    for v in ids:
        plot_timeline(v)
    write_markdown(ids, counts, sweep, conf)
    log.info("Отчёт: %s", cfg.OUT / "report.md")

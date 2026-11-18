"""Консольный поиск по транскриптам, объектам и метаданным (по лемме, pymorphy3)."""
import argparse

import config as cfg
from common import absp, fmt_time, json_path, list_video_ids, load_json, load_meta
from textutils import OBJECT_NAMES_RU, lemma, lemmas, normalize


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("query")
    ap.add_argument("--limit", type=int, default=30, help="максимум совпадений на ролик")
    a = ap.parse_args()
    q = {lemma(w) for w in normalize(a.query).split() if w}
    if not q:
        return print("Пустой запрос")
    total = 0
    for v in list_video_ids():
        m = load_meta(v)
        lines = []
        if q & set(lemmas(m.get("title", "") + " " + m.get("description", ""))):
            lines.append("  [мета] совпадение в названии/описании")
        for s in load_json(json_path(v, "asr"), {"segments": []})["segments"]:
            if q & set(lemmas(s["text"])):
                lines.append(f"  [речь   {fmt_time(s['start'])}] {s['text']}")
        for e in load_json(json_path(v, "events"), []):
            if e["type"] == "object":
                names = {lemma(w) for w in f"{e['label']} {OBJECT_NAMES_RU.get(e['label'], '')}".split()}
                if q & names:
                    lines.append(f"  [объект {fmt_time(e['start'])}–{fmt_time(e['end'])}] {e['label']} "
                                 f"(conf {e['confidence']}) кадр: {e.get('frame')}")
        if lines:
            total += len(lines)
            print(f"\n{m.get('title', v)}  ({v})\n  файл: {m.get('web_video')}")
            print("\n".join(lines[: a.limit]))
    print(f"\nВсего совпадений: {total}" if total else "Ничего не найдено")


if __name__ == "__main__":
    main()

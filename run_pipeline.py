"""Главный скрипт: collect -> decompose -> visual -> audio -> events -> topics -> report -> dashboard."""
import argparse
import time

import config as cfg
from common import ensure_dirs, get_logger, list_video_ids, log_error

log = get_logger()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--sources", default=str(cfg.SOURCES_FILE), help="файл со ссылками/путями")
    ap.add_argument("--whisper", default=cfg.WHISPER_MODEL, help="tiny|base|small|medium")
    ap.add_argument("--conf", type=float, default=cfg.YOLO_CONF, help="порог YOLO для анализа")
    ap.add_argument("--method", default=cfg.TOPIC_METHOD, choices=["kmeans", "hdbscan"])
    ap.add_argument("--skip-yolo", action="store_true")
    ap.add_argument("--skip-asr", action="store_true")
    ap.add_argument("--force", action="store_true", help="игнорировать кэш")
    ap.add_argument("--stage", default="all", choices=["all", "collect", "analyze", "aggregate"],
                    help="collect = скачать+декомпозиция; analyze = YOLO/Whisper/события; aggregate = темы/отчёт/дашборд")
    a = ap.parse_args()
    ensure_dirs()
    t0 = time.time()
    run = lambda s: a.stage in ("all", s)

    if run("collect"):
        import collect
        import decompose
        ids = collect.collect(a.sources, a.force)
        for v in ids:
            decompose.decompose(v, a.force)

    if run("analyze"):
        import audio
        import events
        import visual
        for v in list_video_ids():
            log.info("=== анализ %s ===", v)
            for name, fn in (("visual", lambda: visual.run(v, a.force, a.skip_yolo)),
                             ("audio", lambda: audio.run(v, a.force, a.skip_asr, a.whisper))):
                try:
                    fn()
                except Exception as e:  # один сбой не останавливает пайплайн
                    log_error(v, name, repr(e))
            try:
                events.build(v, a.conf)  # события пересчитываются всегда (быстро, зависят от --conf)
            except Exception as e:
                log_error(v, "events", repr(e))

    if run("aggregate"):
        import dashboard
        import report
        import topics
        if list_video_ids():
            topics.cluster(a.method)
            report.run(a.conf)
            dashboard.build()
        else:
            log.warning("Нет обработанных роликов — заполните sources.txt")

    log.info("Готово за %.1f с. Откройте дашборд: python3 view_dashboard.py", time.time() - t0)


if __name__ == "__main__":
    main()

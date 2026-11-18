"""Шаг 4. Громкость (RMS в dBFS) и распознавание речи (Whisper)."""
import math
import wave

import config as cfg
from common import absp, get_logger, json_path, load_meta, save_json

log = get_logger()
_WHISPER = {}


def loudness(wav_path) -> dict:
    import numpy as np
    with wave.open(str(wav_path), "rb") as w:
        sr, n = w.getframerate(), w.getnframes()
        raw = w.readframes(n)
        width = w.getsampwidth()
    if width != 2:
        raise RuntimeError("ожидался 16-bit PCM wav")
    x = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    win = max(1, int(sr * cfg.LOUD_WINDOW_SEC))
    k = len(x) // win
    db = []
    for i in range(k):
        seg = x[i * win:(i + 1) * win]
        rms = float(np.sqrt(np.mean(seg ** 2)))
        db.append(round(20 * math.log10(rms + 1e-10), 2))
    return {"window": cfg.LOUD_WINDOW_SEC, "db": db}


def transcribe(wav_path, model_name: str) -> list:
    import whisper
    if model_name not in _WHISPER:
        log.info("Загружаю Whisper '%s'...", model_name)
        _WHISPER[model_name] = whisper.load_model(model_name, device="cpu")
    res = _WHISPER[model_name].transcribe(str(wav_path), language=cfg.WHISPER_LANG, fp16=False,
                                          condition_on_previous_text=False, verbose=None)
    segs = []
    for s in res.get("segments", []):
        text = s["text"].strip()
        if not text or s.get("no_speech_prob", 0) > cfg.WHISPER_MAX_NO_SPEECH:
            continue
        segs.append({"start": round(s["start"], 2), "end": round(s["end"], 2), "text": text,
                     "conf": round(math.exp(min(0.0, s.get("avg_logprob", -1.0))), 3)})
    return segs


def run(vid: str, force: bool = False, skip_asr: bool = False, whisper_model: str = None):
    meta = load_meta(vid)
    if not meta.get("audio"):
        return  # нет звука — уже записано в errors.csv, пайплайн не падает
    wav = absp(meta["audio"])
    lp = json_path(vid, "loud")
    if force or not lp.exists():
        save_json(lp, loudness(wav))
    if skip_asr:
        return
    ap = json_path(vid, "asr")
    if force or not ap.exists():
        save_json(ap, {"model": whisper_model or cfg.WHISPER_MODEL,
                       "segments": transcribe(wav, whisper_model or cfg.WHISPER_MODEL)})
        log.info("[%s] речь распознана", vid)

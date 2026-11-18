"""Шаг 6. Тематическая кластеризация роликов (TF-IDF + KMeans / HDBSCAN)."""
import config as cfg
from common import get_logger, json_path, list_video_ids, load_json, load_meta, save_json
from textutils import label_ru, lemmas

log = get_logger()
TOPICS_PATH = cfg.JSON_DIR / "topics.json"


def build_doc(vid: str) -> str:
    meta = load_meta(vid)
    asr = load_json(json_path(vid, "asr"), {"segments": []})
    ev = load_json(json_path(vid, "events"), [])
    parts = [(meta.get("title", "") + " ") * 2, meta.get("description", ""), " ".join(meta.get("tags", [])),
             " ".join(s["text"] for s in asr["segments"]),
             " ".join(label_ru(e["label"]) for e in ev if e["type"] == "object")]
    return " ".join(lemmas(" ".join(parts)))


def _pick_k(X, n, k):
    from sklearn.cluster import KMeans
    from sklearn.metrics import silhouette_score
    if n >= 6:  # автоподбор по силуэту
        best, best_s = k, -1
        for kk in range(2, min(6, n - 1) + 1):
            lab = KMeans(n_clusters=kk, n_init=10, random_state=0).fit_predict(X)
            if len(set(lab)) > 1:
                s = silhouette_score(X, lab)
                if s > best_s:
                    best, best_s = kk, s
        return best
    return max(1, min(k, n))


def cluster(method: str = cfg.TOPIC_METHOD, k: int = cfg.TOPIC_K) -> dict:
    import numpy as np
    from sklearn.feature_extraction.text import TfidfVectorizer
    ids = list_video_ids()
    docs = {v: build_doc(v) for v in ids}
    ids = [v for v in ids if docs[v].strip()] or ids
    labels = np.zeros(len(ids), dtype=int)
    terms_all, X = [], None
    if len(ids) >= 2 and any(docs[v].strip() for v in ids):
        try:
            vec = TfidfVectorizer(tokenizer=str.split, token_pattern=None, lowercase=False,
                                  max_df=0.9 if len(ids) > 3 else 1.0, sublinear_tf=True)
            X = vec.fit_transform([docs[v] for v in ids])
            terms_all = vec.get_feature_names_out()
            if method == "hdbscan" and len(ids) >= cfg.HDBSCAN_MIN_CLUSTER:
                from sklearn.cluster import HDBSCAN
                labels = HDBSCAN(min_cluster_size=cfg.HDBSCAN_MIN_CLUSTER).fit_predict(X.toarray())
            else:
                from sklearn.cluster import KMeans
                kk = _pick_k(X, len(ids), k)
                labels = KMeans(n_clusters=kk, n_init=10, random_state=0).fit_predict(X) if kk > 1 else labels
        except ValueError as e:  # пустой словарь и т.п.
            log.warning("Кластеризация невозможна: %s", e)
            X = None
    clusters = []
    for c in sorted(set(int(l) for l in labels)):
        members = [ids[i] for i, l in enumerate(labels) if int(l) == c]
        terms = []
        if X is not None and c != -1:
            mean = np.asarray(X[[i for i, l in enumerate(labels) if int(l) == c]].mean(axis=0)).ravel()
            terms = [str(terms_all[j]) for j in mean.argsort()[::-1][:6] if mean[j] > 0]
        label = "Прочее" if c == -1 else (", ".join(terms[:3]) or f"Тема {c + 1}")
        clusters.append({"id": int(c), "label": label, "terms": terms, "videos": members})
    result = {"method": method, "clusters": clusters,
              "assignment": {ids[i]: int(l) for i, l in enumerate(labels)}}
    save_json(TOPICS_PATH, result)
    log.info("Тем: %d (%s)", len(clusters), method)
    return result

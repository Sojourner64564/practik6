"""Генерация HTML-дашборда: поиск, временная шкала событий, темы."""
import json

import config as cfg
from common import get_logger, json_path, list_video_ids, load_json, load_meta
from textutils import label_ru, object_names

log = get_logger()

TEMPLATE = r'''<!doctype html>
<html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Видеоаналитика для журналистов</title>
<style>
:root{--bg:#f6f7f9;--card:#fff;--text:#1d2330;--muted:#6b7385;--line:#e2e5ec;--accent:#2563eb;--hit:#f59e0b;
--c-speech:#3b82f6;--c-loud:#ef4444;--c-scene:#a855f7;--c-object:#10b981}
@media (prefers-color-scheme:dark){:root{--bg:#12151c;--card:#1a1e28;--text:#e6e9f0;--muted:#9aa3b5;--line:#2b3140;--accent:#60a5fa;--hit:#fbbf24}}
*{box-sizing:border-box}body{margin:0;font:14px/1.45 system-ui,Segoe UI,Roboto,sans-serif;background:var(--bg);color:var(--text)}
header{display:flex;gap:12px;align-items:center;padding:12px 18px;background:var(--card);border-bottom:1px solid var(--line);position:sticky;top:0;z-index:5}
header h1{font-size:16px;margin:0;white-space:nowrap}
#q{flex:1;max-width:460px;padding:8px 12px;border:1px solid var(--line);border-radius:8px;background:var(--bg);color:var(--text);font-size:14px}
button{cursor:pointer;border:1px solid var(--line);background:var(--card);color:var(--text);border-radius:8px;padding:7px 12px;font:inherit}
button.primary{background:var(--accent);border-color:var(--accent);color:#fff}
main{display:grid;grid-template-columns:380px 1fr;gap:16px;padding:16px;align-items:start}
@media(max-width:900px){main{grid-template-columns:1fr}}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px;margin-bottom:14px}
.card h2{font-size:13px;margin:0 0 10px;color:var(--muted);text-transform:uppercase;letter-spacing:.04em}
.muted{color:var(--muted)}.chip{display:inline-block;padding:1px 8px;border-radius:99px;background:var(--bg);border:1px solid var(--line);margin:2px 3px 2px 0;font-size:12px}
.vid{padding:8px;border-radius:8px;cursor:pointer;border:1px solid transparent}.vid:hover,.vid.active{background:var(--bg);border-color:var(--line)}
.hit{display:flex;gap:8px;padding:6px;border-radius:8px;cursor:pointer;align-items:flex-start}.hit:hover{background:var(--bg)}
.hit img{width:72px;border-radius:4px;flex:none}.hit .t{font-variant-numeric:tabular-nums;color:var(--accent);font-weight:600;flex:none;min-width:48px}
mark{background:var(--hit);color:#000;border-radius:3px;padding:0 2px}
video{width:100%;max-height:420px;background:#000;border-radius:8px}
#tl{position:relative;margin-top:10px}.lane{display:flex;align-items:center;height:22px;margin:3px 0}
.lane .name{width:96px;flex:none;font-size:12px;color:var(--muted);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.lane .track{position:relative;flex:1;height:16px;background:var(--bg);border-radius:4px}
.ev{position:absolute;top:0;height:100%;min-width:3px;border-radius:3px;cursor:pointer;opacity:.9}.ev:hover{opacity:1;outline:2px solid var(--text)}
.ev.hitev{outline:2px solid var(--hit)}
#playhead{position:absolute;top:0;bottom:0;width:2px;background:var(--text);left:96px;pointer-events:none}
.filters label{margin-right:12px;font-size:13px}
table{width:100%;border-collapse:collapse}td{padding:4px 6px;border-top:1px solid var(--line);vertical-align:top}tr.row{cursor:pointer}tr.row:hover{background:var(--bg)}
.dot{display:inline-block;width:9px;height:9px;border-radius:50%;margin-right:6px}
</style></head><body>
<header><h1>🎬 Видеоаналитика</h1>
<input id="q" placeholder="Введите слово, например «ремонт»…" autofocus>
<button class="primary" id="go">Найти</button><button id="clr">Сброс</button></header>
<main>
<aside>
  <div class="card" id="resCard" style="display:none"><h2>Результаты поиска</h2><div id="results"></div></div>
  <div class="card"><h2>Темы</h2><div id="topics"></div></div>
  <div class="card"><h2>Ролики</h2><div id="videos"></div></div>
</aside>
<section>
  <div class="card"><div id="title" style="font-weight:600;margin-bottom:8px"></div>
    <video id="player" controls preload="metadata"></video>
    <div class="filters" style="margin-top:10px" id="filters"></div>
    <div id="tl"></div></div>
  <div class="card"><h2>События</h2><table id="events"></table></div>
</section></main>
<script>
const D = __DATA__;
const $ = s => document.querySelector(s);
const TYPES = {speech:['Речь','var(--c-speech)'],loud_peak:['Громкий момент','var(--c-loud)'],scene_change:['Смена сцены','var(--c-scene)'],object:['Объект','var(--c-object)']};
const state = {vid:null, filter:{speech:true,loud_peak:true,scene_change:true,object:true}, hits:{}};
const norm = s => (s||'').toLowerCase().replace(/ё/g,'е');
const esc = s => (s||'').replace(/[&<>"]/g, c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const fmt = t => {t=Math.round(t);const m=Math.floor(t/60),s=t%60;return String(m).padStart(2,'0')+':'+String(s).padStart(2,'0')};
const WORD = /[A-Za-zА-Яа-яЁё0-9]+/g;
const vById = id => D.videos.find(v=>v.id===id);
const prefixes = q => norm(q).match(/[a-zа-я0-9]+/g)?.map(w=>w.slice(0,D.prefix)) || [];
const wordHit = (text, ps) => (norm(text).match(/[a-zа-я0-9]+/g)||[]).some(w=>ps.some(p=>w.startsWith(p)));
const hl = (text, ps) => esc(text).replace(WORD, w => ps.some(p=>norm(w).startsWith(p)) ? '<mark>'+w+'</mark>' : w);

function renderTopics(){
  $('#topics').innerHTML = D.topics.map(c => `<div style="margin-bottom:8px"><b>${esc(c.label)}</b>
   <div>${c.terms.map(t=>'<span class="chip">'+esc(t)+'</span>').join('')}</div>
   <div>${c.videos.map(id=>'<a href="#" data-v="'+id+'" class="vl">'+esc((vById(id)||{}).title||id)+'</a>').join('<br>')}</div></div>`).join('') || '<span class="muted">нет данных</span>';
  document.querySelectorAll('.vl').forEach(a=>a.onclick=e=>{e.preventDefault();selectVideo(a.dataset.v,0)});
}
function renderVideos(){
  $('#videos').innerHTML = D.videos.map(v=>`<div class="vid ${v.id===state.vid?'active':''}" data-v="${v.id}">
    <div>${esc(v.title)}</div><div class="muted">${fmt(v.duration)} · тема: ${esc(v.topic)} · событий: ${v.events.length+v.segments.length}</div></div>`).join('');
  document.querySelectorAll('.vid').forEach(d=>d.onclick=()=>selectVideo(d.dataset.v,0));
}
function selectVideo(id, t){
  const v = vById(id); if(!v) return; const p = $('#player');
  if(state.vid !== id){ state.vid = id; p.src = v.src; $('#title').textContent = v.title; renderVideos(); }
  const go = () => { p.currentTime = t||0; p.play().catch(()=>{}); };
  if(p.readyState >= 1) go(); else p.addEventListener('loadedmetadata', go, {once:true});
  renderTimeline(); renderEvents();
}
function lanes(v){
  const L = [], f = state.filter, H = state.hits[v.id]||[];
  if(H.length) L.push({name:'Совпадения',color:'var(--hit)',items:H.map(h=>({s:h.s,e:h.e,tip:'совпадение',hit:1}))});
  if(f.speech && v.segments.length) L.push({name:'Речь',color:'var(--c-speech)',items:v.segments.map(s=>({s:s.s,e:s.e,tip:s.t}))});
  if(f.loud_peak) L.push({name:'Громкость',color:'var(--c-loud)',items:v.events.filter(e=>e.type==='loud_peak').map(e=>({s:e.s,e:e.e,tip:e.label}))});
  if(f.scene_change) L.push({name:'Смена сцен',color:'var(--c-scene)',items:v.events.filter(e=>e.type==='scene_change').map(e=>({s:e.s,e:e.e,tip:e.label}))});
  if(f.object){ const m={}; v.events.filter(e=>e.type==='object').forEach(e=>(m[e.ru]=m[e.ru]||[]).push({s:e.s,e:e.e,tip:e.label+' '+Math.round(e.c*100)+'%'}));
    Object.keys(m).sort().forEach(k=>L.push({name:k,color:'var(--c-object)',items:m[k]})); }
  return L.filter(l=>l.items.length);
}
function renderTimeline(){
  const v = vById(state.vid); if(!v) return; const dur = Math.max(v.duration,1);
  $('#tl').innerHTML = lanes(v).map(l=>`<div class="lane"><div class="name" title="${esc(l.name)}">${esc(l.name)}</div><div class="track">`+
    l.items.map(i=>`<div class="ev ${i.hit?'hitev':''}" style="left:${i.s/dur*100}%;width:${Math.max((i.e-i.s)/dur*100,.3)}%;background:${l.color}" data-t="${i.s}" title="${fmt(i.s)} — ${esc(i.tip)}"></div>`).join('')+
    `</div></div>`).join('') + '<div id="playhead"></div>';
  document.querySelectorAll('.ev').forEach(e=>e.onclick=()=>{const p=$('#player');p.currentTime=+e.dataset.t;p.play().catch(()=>{})});
}
function renderEvents(){
  const v = vById(state.vid); if(!v) return;
  const rows = [...v.segments.map(s=>({type:'speech',s:s.s,label:s.t})), ...v.events.map(e=>({type:e.type,s:e.s,label:e.type==='object'?e.ru+' ('+e.label+')':e.label}))]
    .filter(r=>state.filter[r.type]).sort((a,b)=>a.s-b.s).slice(0,400);
  $('#events').innerHTML = rows.map(r=>`<tr class="row" data-t="${r.s}"><td class="muted" style="width:52px">${fmt(r.s)}</td>
    <td style="width:130px"><span class="dot" style="background:${TYPES[r.type][1]}"></span>${TYPES[r.type][0]}</td><td>${esc(r.label)}</td></tr>`).join('');
  document.querySelectorAll('tr.row').forEach(r=>r.onclick=()=>{const p=$('#player');p.currentTime=+r.dataset.t;p.play().catch(()=>{})});
}
function renderFilters(){
  $('#filters').innerHTML = Object.keys(TYPES).map(k=>`<label><input type="checkbox" data-k="${k}" checked> <span class="dot" style="background:${TYPES[k][1]}"></span>${TYPES[k][0]}</label>`).join('');
  document.querySelectorAll('#filters input').forEach(c=>c.onchange=()=>{state.filter[c.dataset.k]=c.checked;renderTimeline();renderEvents()});
}
function search(){
  const q = $('#q').value.trim(), ps = prefixes(q); state.hits = {};
  if(!ps.length){ $('#resCard').style.display='none'; renderTimeline(); return; }
  let html = '', total = 0;
  D.videos.forEach(v=>{
    const items = [];
    v.segments.forEach(s=>{ if(wordHit(s.t,ps)) items.push({t:s.s,e:s.e,html:'<span>🗣 '+hl(s.t,ps)+'</span>'}); });
    v.events.forEach(e=>{ if(e.type==='object' && wordHit(e.names,ps)) items.push({t:e.s,e:e.e,img:e.frame,html:'<span>🖼 в кадре: <b>'+esc(e.ru)+'</b> <span class="muted">'+fmt(e.s)+'–'+fmt(e.e)+'</span></span>'}); });
    if(wordHit(v.title+' '+v.desc, ps)) items.unshift({t:0,e:0,html:'<span>📄 совпадение в названии/описании</span>'});
    if(!items.length) return;
    total += items.length; state.hits[v.id] = items.filter(i=>i.e||i.t).map(i=>({s:i.t,e:Math.max(i.e,i.t+0.5)}));
    html += `<div style="margin-bottom:10px"><b>${esc(v.title)}</b> <span class="muted">(${items.length})</span>`+
      items.slice(0,60).map(i=>`<div class="hit" data-v="${v.id}" data-t="${i.t}"><span class="t">${fmt(i.t)}</span>${i.img?'<img loading="lazy" src="../'+i.img+'">':''}${i.html}</div>`).join('')+`</div>`;
  });
  $('#resCard').style.display = 'block';
  $('#results').innerHTML = html ? `<div class="muted" style="margin-bottom:8px">Найдено: ${total} (поиск по префиксу «${esc(ps.join(', '))}»)</div>`+html : '<span class="muted">Ничего не найдено</span>';
  document.querySelectorAll('.hit').forEach(h=>h.onclick=()=>selectVideo(h.dataset.v,+h.dataset.t));
  renderTimeline();
}
$('#go').onclick = search; $('#q').addEventListener('keydown', e=>{if(e.key==='Enter')search()});
$('#clr').onclick = ()=>{$('#q').value='';search()};
$('#player').addEventListener('timeupdate', ()=>{
  const v = vById(state.vid), ph = $('#playhead'), tr = document.querySelector('.lane .track'); if(!v||!ph||!tr) return;
  const l = tr.offsetLeft, w = tr.clientWidth; ph.style.left = (l + $('#player').currentTime/Math.max(v.duration,1)*w)+'px';
});
renderFilters(); renderTopics(); renderVideos();
if(D.videos.length) selectVideo(D.videos[0].id, 0); else $('#title').textContent = 'Нет данных. Запустите run_pipeline.py';
</script></body></html>'''


def build_data() -> dict:
    topics = load_json(cfg.JSON_DIR / "topics.json", {"clusters": [], "assignment": {}})
    names = {c["id"]: c["label"] for c in topics["clusters"]}
    videos = []
    for vid in list_video_ids():
        m = load_meta(vid)
        if not m.get("web_video"):
            continue
        ev = load_json(json_path(vid, "events"), [])
        segs = [{"s": e["start"], "e": e["end"], "t": e["label"], "c": e["confidence"]}
                for e in ev if e["type"] == "speech"]
        others = []
        for e in ev:
            if e["type"] == "speech":
                continue
            o = {"type": e["type"], "label": e["label"], "s": e["start"], "e": e["end"], "c": e["confidence"]}
            if e["type"] == "object":
                o.update(ru=label_ru(e["label"]), names=object_names(e["label"]), frame=e.get("frame"))
            others.append(o)
        a = topics["assignment"].get(vid)
        videos.append({"id": vid, "title": m.get("title", vid), "src": "../" + m["web_video"],
                       "duration": m.get("duration") or 0, "desc": (m.get("description") or "")[:400],
                       "topic": names.get(a, "—"), "segments": segs, "events": others})
    return {"videos": videos, "prefix": cfg.PREFIX_LEN,
            "topics": [{"label": c["label"], "terms": c["terms"], "videos": c["videos"]} for c in topics["clusters"]]}


def build() -> str:
    cfg.OUT.mkdir(parents=True, exist_ok=True)
    data = json.dumps(build_data(), ensure_ascii=False).replace("</", "<\\/")
    path = cfg.OUT / "dashboard.html"
    path.write_text(TEMPLATE.replace("__DATA__", data), encoding="utf-8")
    log.info("Дашборд: %s", path)
    return str(path)


if __name__ == "__main__":
    build()

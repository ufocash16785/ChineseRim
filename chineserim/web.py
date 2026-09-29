"""瀏覽器介面（世界地圖探索）：python -m chineserim.web  → http://127.0.0.1:8765"""
import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

from .session import Session

session = Session()
try:
    session.load()
except Exception as e:   # 壞檔不擋開局
    print("讀檔失敗，改開新局：", e)


PAGE = """<!doctype html><meta charset=utf-8><title>凡人修仙傳</title>
<style>
body{font-family:sans-serif;background:#14181d;color:#e6e2d3;margin:0;padding:12px}
.wrap{display:flex;flex-wrap:wrap;gap:14px}.col{flex:1 1 380px;min-width:300px}
svg{background:#0c1a22;border:1px solid #444;border-radius:8px;width:100%;aspect-ratio:1;max-height:46vh}
#err{background:#7a1f1f;padding:6px 10px;border-radius:6px;display:none;margin-bottom:8px}
.node{cursor:pointer}.node:hover circle{stroke:#fff}.node text{fill:#e6e2d3;font-size:3.2px;pointer-events:none}
.lock circle{fill:#333!important}.bar{background:#333;height:10px;border-radius:5px;overflow:hidden;margin:3px 0 8px}.bar i{display:block;height:100%}
button{margin:3px;padding:7px 12px}#log{background:#0c0f12;padding:8px;min-height:120px;border-radius:6px;font-size:14px}
.realms span{padding:1px 7px;margin:1px;border:1px solid #555;border-radius:10px;display:inline-block;font-size:13px}.realms .on{background:#b8893a;color:#000}
h3{margin:8px 0 4px}
#dlg{display:none;position:fixed;left:0;right:0;bottom:0;background:#1d222aee;border-top:2px solid #b8893a;padding:14px 20px;z-index:9}
#dlg .sp{color:#e6b45a;font-weight:bold;margin-bottom:4px}#dlg .tx{font-size:17px;line-height:1.6;margin-bottom:8px}#dlg button{display:block;margin:4px 0;font-size:15px;text-align:left}small{color:#9a9686}
</style>
<h2 style="margin:0 0 8px">凡人修仙傳 <small>UI v3（地圖＋任務＋對話）</small></h2><div id=err></div>
<div class=wrap>
<div class=col><h3>世界地圖 <small>點區域旅行</small></h3><svg id=wm viewBox="0 0 100 100"></svg>
<h3 id=rt></h3><svg id=rm viewBox="0 0 100 100"></svg></div>
<div class=col><div id=s></div>
<button onclick="a('/act?c=break')">突破</button><button onclick="a('/act?c=refine')">祭煉青竹蜂雲劍</button><button onclick="a('/act?c=rest')">閉關 7 日</button>
<button onclick="if(confirm('確定重開新局？（會覆蓋存檔）'))a('/act?c=new')">新遊戲</button> <small>自動存檔</small>
<div id=dlg></div><h3 id=qt></h3><div id=qs></div>
<h3>紀錄</h3><div id=log></div></div></div>
<script>
const COL={"人界":"#4a8","靈界":"#a6d"};
const TC={"村鎮":"#6c6","城市":"#6c6","都城":"#6c6","府城":"#6c6","坊市":"#6c6","巨城":"#6c6","門派":"#e94","門派/山":"#e94","秘境":"#d4d","聖地":"#d4d"};
window.onerror=(m)=>{err.style.display='block';err.textContent='頁面錯誤：'+m};
async function a(u){await fetch(u,{method:'POST'});r()}
async function r(){let d;try{d=await (await fetch('/state')).json();err.style.display='none'}catch(e){err.style.display='block';err.textContent='連不上伺服器：'+e;return}
const bar=(v,m,c)=>`<div class=bar><i style="width:${Math.min(100,100*v/m)}%;background:${c}"></i></div>`;
s.innerHTML=`<div class=realms>${d.realms.map((n,i)=>`<span class="${i==d.realm_index?'on':''}">${n}</span>`).join('')}</div>
<p><b>${d.name}</b> ${d.realm}·${d.sub}　靈根 ${d.elements.join('')}　第 ${d.day} 日　所在：${d.region_name}</p>
等級 ${d.level}/${d.cap}${d.bottleneck?' <b style=color:#e6a>【瓶頸】</b>':''}${bar(d.level,d.cap,'#b8893a')}
HP ${d.hp}/${d.max_hp}${bar(d.hp,d.max_hp,'#c44')}
<p>靈石 ${d.lingshi}　突破丹 ${d.pills}　靈液 ${d.lingye}　法寶 ${JSON.stringify(d.treasures)}<br>門派聲望 ${JSON.stringify(d.sects)}</p>`;
qt.textContent='任務：'+d.quest.arc+(d.quest.done?'（完成）':'');
qs.innerHTML=d.quest.quests.filter(q=>q.state!='locked').map(q=>`<div style="margin:4px 0;opacity:${q.state=='done'?.5:1}"><b>${q.state=='done'?'✔ ':'▶ '}${q.name}</b>`+(q.state=='active'?q.objectives.map(o=>`<div style="margin-left:14px;font-size:13px">${o.state=='done'?'☑':'☐'} ${o.text}${o.progress?' <small>('+o.progress+')</small>':''}</div>`).join(''):'')+'</div>').join('');
dlg.style.display=d.dialogue?'block':'none';
if(d.dialogue){const g=d.dialogue;dlg.innerHTML=`<div class=sp>${g.speaker}</div><div class=tx>${g.text}</div>`+(g.cont?`<button onclick="a('/choose')">▶ 繼續</button>`:g.choices.map(c=>`<button onclick="a('/choose?i=${c.i}')">${c.text}</button>`).join(''))}
log.innerHTML=d.log.map(x=>'<div>'+x+'</div>').join('');log.scrollTop=1e6;
wm.innerHTML=d.world.map(g=>`<g class="node ${g.locked?'lock':''}" onclick="a('/travel?to=${g.id}')"><circle cx=${g.x} cy=${100-g.y} r=${g.id==d.region?4.5:3.2} fill="${COL[g.world]}" stroke="${g.id==d.region?'#fc6':'#000'}" stroke-width=.8></circle>
<text x=${g.x} y=${100-g.y+7} text-anchor=middle>${g.name}${g.id==d.region?'':' ('+g.days+'日)'}${g.locked?'🔒':''}</text></g>`).join('');
rt.innerHTML=d.region_name+' <small>點地點探索</small>';
rm.innerHTML=`<circle cx=50 cy=50 r=46 fill="#10261c" stroke="#264"/>`+d.locations.map(l=>`<g class=node onclick="a('/visit?loc=${l.id}')"><title>${l.type}：${l.note}</title><circle cx=${l.x} cy=${l.y} r=3 fill="${TC[l.type]||'#c55'}" stroke=#000 stroke-width=.6></circle>
<text x=${l.x} y=${l.y+6} text-anchor=middle>${l.name.replace(/（.*/,'')}</text></g>`).join('')}
r()</script>"""


class H(BaseHTTPRequestHandler):
    def _send(self, body, ctype):
        b = body.encode()
        self.send_response(200)
        self.send_header("Content-Type", ctype + "; charset=utf-8")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        if self.path == "/state":
            self._send(json.dumps(session.snapshot(), ensure_ascii=False), "application/json")
        else:
            self._send(PAGE, "text/html")

    def do_POST(self):
        u = urlparse(self.path)
        q = {k: v[0] for k, v in parse_qs(u.query).items()}
        session.act(q.pop("c", u.path.strip("/")), **q)
        self._send("{}", "application/json")

    def log_message(self, *a):
        pass


def main():
    print("開啟瀏覽器：http://127.0.0.1:8765  （Ctrl+C 結束）")
    HTTPServer(("127.0.0.1", 8765), H).serve_forever()


if __name__ == "__main__":
    main()

from __future__ import annotations

from fastapi.responses import HTMLResponse

DASHBOARD_HTML = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Roticery Chicken</title>
<style>
:root{font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;color:#f5f5f5;background:#0b0d0f}
*{box-sizing:border-box}body{margin:0;background:radial-gradient(circle at 15% 0%,#2a2111 0,#0b0d0f 38%);min-height:100vh}
main{max-width:1180px;margin:auto;padding:28px}.top{display:flex;justify-content:space-between;align-items:center;gap:20px;margin-bottom:26px}
.brand{display:flex;align-items:center;gap:14px}.logo{width:48px;height:48px;border-radius:14px;background:#f2b84b;color:#111;display:grid;place-items:center;font-size:25px;box-shadow:0 8px 30px #0008}
h1{font-size:25px;margin:0}.sub{color:#92979f;font-size:13px;margin-top:3px}.pill{padding:8px 12px;border:1px solid #293039;border-radius:999px;color:#9ee7b2;background:#101814;font-size:13px}
.grid{display:grid;grid-template-columns:repeat(4,1fr);gap:14px}.card{background:#111418;border:1px solid #252a30;border-radius:16px;padding:18px;box-shadow:0 10px 30px #0004}.label{color:#858b94;font-size:12px;text-transform:uppercase;letter-spacing:.08em}.value{font-size:25px;font-weight:700;margin-top:9px}.muted{color:#858b94;font-size:12px;margin-top:5px}
.section{margin-top:18px}.section h2{font-size:15px;margin:0 0 12px}.table{overflow:hidden}.row{display:grid;grid-template-columns:1.5fr 1fr 1fr 1.2fr 1fr;gap:12px;padding:14px 16px;border-top:1px solid #22272d;align-items:center;font-size:13px}.head{color:#777e87;text-transform:uppercase;font-size:11px;letter-spacing:.07em;border-top:0}.account{font-weight:650}.status{display:inline-flex;align-items:center;gap:7px}.dot{width:7px;height:7px;border-radius:50%;background:#5dd48a}.dot.off{background:#e66d6d}.bar{height:7px;background:#252a30;border-radius:99px;overflow:hidden}.fill{height:100%;background:#f2b84b;border-radius:99px}.mono{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;color:#b8bec7}.footer{color:#626871;text-align:center;font-size:11px;margin:28px}
@media(max-width:850px){.grid{grid-template-columns:repeat(2,1fr)}.row{grid-template-columns:1fr 1fr}.head{display:none}}
@media(max-width:520px){main{padding:16px}.grid{grid-template-columns:1fr}.top{align-items:flex-start}.row{grid-template-columns:1fr}}
</style>
</head>
<body>
<main>
  <header class="top">
    <div class="brand"><div class="logo">🍗</div><div><h1>Roticery Chicken</h1><div class="sub">Token-aware AI gateway</div></div></div>
    <div class="pill" id="health">● Checking gateway…</div>
  </header>

  <section class="grid">
    <div class="card"><div class="label">Active account</div><div class="value mono" id="active">—</div><div class="muted" id="activeProvider">—</div></div>
    <div class="card"><div class="label">Usage</div><div class="value" id="usage">—</div><div class="muted" id="threshold">—</div></div>
    <div class="card"><div class="label">Rotation</div><div class="value" id="strategy">—</div><div class="muted">routing strategy</div></div>
    <div class="card"><div class="label">Accounts</div><div class="value" id="accounts">—</div><div class="muted" id="eligible">—</div></div>
  </section>

  <section class="section">
    <div class="card table">
      <h2>Credential pool</h2>
      <div class="row head"><div>Account</div><div>Provider</div><div>Status</div><div>Token usage</div><div>Remaining</div></div>
      <div id="rows"></div>
    </div>
  </section>

  <div class="footer">localhost:2500 · dashboard only · credentials are never displayed</div>
</main>
<script>
const fmt=n=>Number(n||0).toLocaleString();
function esc(s){return String(s).replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));}
async function refresh(){
  try{
    const h=await fetch("/healthz"); if(!h.ok) throw new Error();
    document.querySelector("#health").textContent="● Gateway online";
    const r=await fetch("/dashboard/data"); if(!r.ok) throw new Error();
    const d=await r.json(), a=d.accounts||[];
    document.querySelector("#strategy").textContent=d.strategy.replace("_"," ");
    document.querySelector("#accounts").textContent=a.length;
    const eligible=a.filter(x=>x.enabled && x.remaining_tokens>0 && !(x.disabled_until && x.disabled_until>Date.now()/1000)).length;
    document.querySelector("#eligible").textContent=eligible+" eligible";
    const active=a.find(x=>x.enabled && x.remaining_tokens>0 && !(x.disabled_until && x.disabled_until>Date.now()/1000));
    document.querySelector("#active").textContent=active?.id||"None";
    document.querySelector("#activeProvider").textContent=active?.provider||"No eligible account";
    document.querySelector("#usage").textContent=active?fmt(active.tokens_used):"—";
    document.querySelector("#threshold").textContent=active?fmt(active.token_threshold)+" token threshold":"—";
    document.querySelector("#rows").innerHTML=a.map(x=>{
      const pct=Math.min(100,(x.tokens_used/x.token_threshold)*100);
      const cooldown=x.disabled_until && x.disabled_until>Date.now()/1000;
      const online=x.enabled && !cooldown && x.remaining_tokens>0;
      return '<div class="row"><div class="account mono">'+esc(x.id)+'</div><div>'+esc(x.provider)+'</div><div class="status"><span class="dot '+(online?'':'off')+'"></span>'+(online?'Ready':cooldown?'Cooldown':x.enabled?'Threshold reached':'Disabled')+'</div><div><div class="bar"><div class="fill" style="width:'+pct+'%"></div></div><div class="muted">'+fmt(x.tokens_used)+' / '+fmt(x.token_threshold)+'</div></div><div class="mono">'+fmt(x.remaining_tokens)+'</div></div>';
    }).join("")||'<div class="row"><div>No accounts configured.</div></div>';
  }catch(e){document.querySelector("#health").textContent="● Gateway unavailable";}
}
refresh(); setInterval(refresh,3000);
</script>
</body>
</html>"""

def dashboard_response() -> HTMLResponse:
    return HTMLResponse(DASHBOARD_HTML)

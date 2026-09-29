from __future__ import annotations

from fastapi.responses import HTMLResponse

DASHBOARD_HTML = r"""<!doctype html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Roticery Chicken</title>
<style>
body{margin:0;background:#0b0d0f;color:#eee;font:14px system-ui;padding:28px}main{max-width:1180px;margin:auto}
.card{background:#111418;border:1px solid #292e34;border-radius:14px;padding:18px;margin:14px 0}
.grid{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}.value{font-size:25px;font-weight:700}.muted{color:#858b94;font-size:12px}
table{width:100%;border-collapse:collapse}th,td{text-align:left;padding:12px;border-bottom:1px solid #252a30}th{color:#858b94;font-size:11px;text-transform:uppercase}
button{background:#191e24;color:#eee;border:1px solid #3a4149;border-radius:7px;padding:7px 10px;cursor:pointer;margin:2px}.primary{background:#f2b84b;color:#111;font-weight:700}
input,select{width:100%;box-sizing:border-box;background:#0b0d0f;color:#eee;border:1px solid #30363d;border-radius:7px;padding:9px;margin-top:4px}
form{display:grid;grid-template-columns:1fr 1fr;gap:10px}.wide{grid-column:1/-1}.modal{display:none;position:fixed;inset:0;background:#000b;place-items:center;padding:20px}.modal.open{display:grid}.box{background:#111418;border:1px solid #30363d;border-radius:14px;padding:20px;max-width:620px;width:100%}
@media(max-width:800px){.grid{grid-template-columns:1fr 1fr}}@media(max-width:600px){.grid,form{grid-template-columns:1fr}}
</style></head>
<body><main>
<header><h1>🍗 Roticery Chicken</h1><p class="muted">Token-aware AI gateway · <span id="health">checking…</span></p></header>
<section class="grid">
<div class="card"><div class="muted">Active account</div><div class="value" id="active">—</div></div>
<div class="card"><div class="muted">Usage</div><div class="value" id="usage">—</div></div>
<div class="card"><div class="muted">Rotation</div><div class="value" id="strategy">—</div></div>
<div class="card"><div class="muted">Accounts</div><div class="value" id="accounts">—</div></div>
</section>
<section class="card"><h2>Credential pool</h2><table><thead><tr><th>Account</th><th>Provider</th><th>State</th><th>Usage</th><th>Key</th><th>Actions</th></tr></thead><tbody id="rows"></tbody></table></section>
<section class="card"><h2>API management</h2><button class="primary" onclick="newAccount()">＋ Add API</button>
<p class="muted">API keys are never written to YAML or returned to the browser. Configure each account with an environment variable such as ROTI_OR_01. Tests use that variable directly.</p></section>
<div id="modal" class="modal"><div class="box"><h2 id="title">Add API</h2><form onsubmit="saveAccount(event)">
<label>Account ID<input id="id" required></label><label>Provider<input id="provider" value="openrouter" required></label>
<label class="wide">Base URL<input id="base_url" value="https://openrouter.ai/api/v1" required></label>
<label>API key environment variable<input id="api_key_env" placeholder="ROTI_OR_01" required></label>
<label>Token threshold<input id="token_threshold" type="number" value="50000" min="1" required></label>
<label>Cooldown seconds<input id="cooldown_seconds" type="number" value="60" min="0" required></label>
<label>Enabled<select id="enabled"><option value="true">Yes</option><option value="false">No</option></select></label>
<div class="wide"><button class="primary">Save</button><button type="button" onclick="closeModal()">Cancel</button></div>
</form></div></div>
</main>
<script>
var accounts=[], editing=null;
function fmt(n){return Number(n||0).toLocaleString()}
function esc(s){return String(s).replace(/[&<>"']/g,function(c){return {"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]})}
async function refresh(){
 try{
  var h=await fetch("/healthz");if(!h.ok)throw 0;document.getElementById("health").textContent="gateway online";
  var d=await fetch("/dashboard/data").then(function(r){return r.json()});
  var cfg=await fetch("/dashboard/accounts").then(function(r){return r.json()});accounts=cfg.accounts||[];
  var a=d.accounts||[];document.getElementById("strategy").textContent=d.strategy.replace("_"," ");
  document.getElementById("accounts").textContent=a.length;
  var active=a.find(function(x){return x.enabled&&x.remaining_tokens>0&&!(x.disabled_until&&x.disabled_until>Date.now()/1000)});
  document.getElementById("active").textContent=active?active.id:"None";document.getElementById("usage").textContent=active?fmt(active.tokens_used):"—";
  document.getElementById("rows").innerHTML=a.map(function(x){
   var cool=x.disabled_until&&x.disabled_until>Date.now()/1000,ready=x.enabled&&!cool&&x.remaining_tokens>0,c=accounts.find(function(y){return y.id===x.id});
   return "<tr><td>"+esc(x.id)+"</td><td>"+esc(x.provider)+"</td><td>"+(ready?"● Ready":cool?"● Cooldown":x.enabled?"● Threshold reached":"● Disabled")+"</td><td>"+fmt(x.tokens_used)+" / "+fmt(x.token_threshold)+"</td><td>"+(c&&c.has_api_key?"Configured":"Missing")+"</td><td><button onclick=\"testAccount('"+esc(x.id)+"')\\">Test</button><button onclick=\"editAccount('"+esc(x.id)+"')\\">Edit</button><button onclick=\"deleteAccount('"+esc(x.id)+"')\\">Delete</button></td></tr>";
  }).join("");
 }catch(e){document.getElementById("health").textContent="gateway unavailable"}
}
function openModal(){document.getElementById("modal").classList.add("open")}
function closeModal(){document.getElementById("modal").classList.remove("open")}
function newAccount(){editing=null;document.getElementById("title").textContent="Add API";document.getElementById("id").value="";document.getElementById("provider").value="openrouter";document.getElementById("base_url").value="https://openrouter.ai/api/v1";document.getElementById("api_key_env").value="";document.getElementById("token_threshold").value=50000;document.getElementById("cooldown_seconds").value=60;document.getElementById("enabled").value="true";openModal()}
function editAccount(id){var a=accounts.find(function(x){return x.id===id});if(!a)return;editing=id;document.getElementById("title").textContent="Edit API";["id","provider","base_url","api_key_env","token_threshold","cooldown_seconds"].forEach(function(k){document.getElementById(k).value=a[k]});document.getElementById("enabled").value=String(a.enabled);openModal()}
async function saveAccount(e){e.preventDefault();var body={id:document.getElementById("id").value,provider:document.getElementById("provider").value,base_url:document.getElementById("base_url").value,api_key_env:document.getElementById("api_key_env").value,token_threshold:Number(document.getElementById("token_threshold").value),cooldown_seconds:Number(document.getElementById("cooldown_seconds").value),enabled:document.getElementById("enabled").value==="true",headers:{}};var url="/dashboard/accounts"+(editing?"/"+encodeURIComponent(editing):"");var r=await fetch(url,{method:editing?"PUT":"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)});var d=await r.json();if(!r.ok)return alert(d.detail||"Save failed");closeModal();refresh()}
async function deleteAccount(id){if(!confirm("Delete "+id+"?"))return;var r=await fetch("/dashboard/accounts/"+encodeURIComponent(id),{method:"DELETE"});var d=await r.json();if(!r.ok)return alert(d.detail||"Delete failed");refresh()}
async function testAccount(id){var r=await fetch("/dashboard/accounts/"+encodeURIComponent(id)+"/test",{method:"POST"}),d=await r.json();if(d.ok)alert("ONLINE · HTTP "+d.http_status+" · "+d.latency_ms+" ms");else alert((d.status||"error").replaceAll("_"," ") +(d.http_status?" · HTTP "+d.http_status:"")+(d.message?"\n"+d.message:""))}
refresh();setInterval(refresh,3000);
</script></body></html>"""

def dashboard_response() -> HTMLResponse:
    return HTMLResponse(DASHBOARD_HTML)

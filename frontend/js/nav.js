function nav(p){
  ["dash","wizard","templates"].forEach(x=>{
    $("page-"+x).classList.toggle("hidden",x!==p);
    const navEl=$("nav-"+x);
    if(navEl) navEl.classList.toggle("on",x===p);
  });
  if(p==="dash")loadDashboard();
  if(p==="templates")loadTemplatesPage();
}

async function loadTemplatesPage(){
  const tpls=await(await fetch(API+"/api/templates",{headers:H()})).json();
  TEMPLATES=tpls;
  $("tplCountBadge").textContent=tpls.length;
  if(!tpls.length){
    $("tplGrid").innerHTML='<p style="color:var(--muted);font-size:13.5px;grid-column:1/-1">No hay plantillas todavía. Sube la primera usando el formulario de arriba.</p>';
    return;
  }
  $("tplGrid").innerHTML=tpls.map(t=>{
    const fieldCount=t.schema?.sections?.reduce((s,sec)=>s+(sec.fields?.length||0),0)||0;
    return `<div class="tpl" style="position:relative">
      <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:6px">
        <div class="i" style="font-size:26px">${t.icon}</div>
        <div style="display:flex;gap:4px">
          <button onclick="openEditTpl('${t.id}')" title="Editar nombre y descripción"
            style="background:none;border:none;cursor:pointer;color:var(--muted);font-size:14px;padding:4px 6px;border-radius:6px"
            onmouseover="this.style.color='var(--brand-700)';this.style.background='var(--brand-100)'"
            onmouseout="this.style.color='var(--muted)';this.style.background='none'">✎</button>
          <button onclick="deleteTemplate('${t.id}')" title="Eliminar plantilla"
            style="background:none;border:none;cursor:pointer;color:var(--muted);font-size:16px;line-height:1;padding:4px;border-radius:6px"
            onmouseover="this.style.color='var(--danger)';this.style.background='var(--danger-bg)'"
            onmouseout="this.style.color='var(--muted)';this.style.background='none'">✕</button>
        </div>
      </div>
      <h4 style="font-size:15px;margin-bottom:5px">${esc(t.name)}</h4>
      <p style="font-size:12.5px;color:var(--muted);margin-bottom:12px">${esc(t.description)||'Sin descripción'}</p>
      <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap">
        <span class="tag info">${fieldCount} campo${fieldCount!==1?'s':''}</span>
        <span style="font-size:11px;color:var(--muted)">v${t.version}</span>
      </div>
    </div>`;
  }).join("");
}

async function deleteTemplate(id){
  if(!confirm("¿Eliminar esta plantilla? Las actas existentes no se verán afectadas."))return;
  const r=await fetch(API+"/api/templates/"+id,{method:"DELETE",headers:H()});
  if(r.ok||r.status===204){toast("Plantilla eliminada");loadTemplatesPage();}
  else toast("No se pudo eliminar la plantilla");
}

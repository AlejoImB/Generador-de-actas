let _allActas=[],_pg=1;
const PG_SIZE=8;

async function loadDashboard(){
  $("hello").textContent="Hola, "+USER.name.split(" ")[0]+" 👋";
  // Skeleton mientras carga
  $("actasBody").innerHTML=`
    ${[1,2,3].map(()=>`<tr class="sk-row">
      <td><div class="skeleton sk-cell sk-cell-lg" style="margin-bottom:6px"></div><div class="skeleton sk-cell sk-cell-md" style="opacity:.5"></div></td>
      <td><div class="skeleton sk-tag"></div></td>
      <td><div class="skeleton sk-badge"></div></td>
      <td><div class="skeleton sk-cell sk-cell-sm"></div></td>
      <td><div style="display:flex;gap:6px"><div class="skeleton sk-cell" style="width:80px;height:28px;border-radius:7px"></div><div class="skeleton sk-cell" style="width:28px;height:28px;border-radius:7px"></div></div></td>
    </tr>`).join('')}`;
  const actas=await(await fetch(API+"/api/actas",{headers:H()})).json();
  $("actasCount").textContent=actas.length;
  _allActas=actas; _pg=1;
  if($("filterSearch"))$("filterSearch").value="";
  if($("filterStatus"))$("filterStatus").value="";
  renderActasTable();
}

function nuevaActa(){
  state={transcript:null,template:null,acta:null};
  $("ta").value=""; $("trTitle").value="";
  if($("w3Hdr")) $("w3Hdr").innerHTML="";
  if($("w3Fields")) $("w3Fields").innerHTML="";
  if($("docSheet")) $("docSheet").innerHTML="";
  renderTemplates();
  nav('wizard');
  step(1);
}

async function resumeActa(id){
  try{
    const a=await(await fetch(API+"/api/actas/"+id,{headers:H()})).json();
    const tr=await(await fetch(API+"/api/transcripts/"+a.transcript_id,{headers:H()})).json();
    const tpl=TEMPLATES.find(t=>t.id===a.template_id);
    state.acta=a; state.transcript=tr; state.template=tpl||null;
    nav('wizard');
    renderTemplates();
    renderW3(); step(3);
    toast("↩ Acta cargada — puedes continuar desde donde lo dejaste");
  }catch(e){
    toast("No se pudo cargar el acta");
  }
}

async function deleteActa(id){
  if(!confirm("¿Eliminar esta acta? Esta acción no se puede deshacer.")) return;
  const r=await fetch(API+"/api/actas/"+id,{method:"DELETE",headers:H()});
  if(r.ok||r.status===204){ toast("Acta eliminada"); loadDashboard(); }
  else toast("No se pudo eliminar el acta");
}

function filterActas(){
  _pg=1;
  renderActasTable();
}

function renderActasTable(){
  const q=($("filterSearch")?.value||"").toLowerCase();
  const st=$("filterStatus")?.value||"";
  const filtered=_allActas.filter(a=>{
    const tpl=TEMPLATES.find(t=>t.id===a.template_id);
    const name=(tpl?.name||"").toLowerCase();
    return(!q||name.includes(q))&&(!st||a.status===st);
  });
  const total=filtered.length;
  const pages=Math.max(1,Math.ceil(total/PG_SIZE));
  if(_pg>pages)_pg=pages;
  const slice=filtered.slice((_pg-1)*PG_SIZE,_pg*PG_SIZE);
  const tag=s=>s==="approved"
    ?'<span class="tag ok"><span class="status-dot ok"></span>Aprobada</span>'
    :'<span class="tag info"><span class="status-dot info"></span>Borrador</span>';
  const isFiltering=!!$("filterSearch")?.value||!!$("filterStatus")?.value;

  if(!slice.length){
    $("actasTable")?.classList.add("table-hidden");
    const container = $("emptyStateContainer");
    if(container) {
      container.classList.remove("hidden");
      if(isFiltering) {
        container.innerHTML = `
          <div class="empty-state-premium">
            <div class="empty-state-glow">
              <svg width="48" height="48" style="color: var(--p4); z-index: 2; position: relative" fill="none" stroke="currentColor" stroke-width="1.8" viewBox="0 0 24 24">
                <circle cx="11" cy="11" r="8"/>
                <path d="m21 21-4.35-4.35"/>
              </svg>
            </div>
            <h3>Sin resultados coincidentes</h3>
            <p>Ninguna acta coincide con los filtros de búsqueda aplicados. Intenta con otro término o estado.</p>
            <button class="btn btn-line btnw" onclick="$('filterSearch').value='';$('filterStatus').value='';filterActas()">Limpiar filtros</button>
          </div>
        `;
      } else {
        container.innerHTML = `
          <div class="empty-state-premium">
            <div class="empty-state-glow">
              <svg style="width: 48px; height: 48px; color: var(--p5); z-index: 2; position: relative" fill="none" stroke="currentColor" stroke-width="1.5" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                <path stroke-linecap="round" stroke-linejoin="round" d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 002-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10"></path>
              </svg>
              <div class="empty-state-floating-element">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="var(--ok)" stroke-width="3.2" stroke-linecap="round" stroke-linejoin="round">
                  <polyline points="20 6 9 17 4 12"/>
                </svg>
              </div>
            </div>
            <h3>Todavía no hay actas inteligentes</h3>
            <p>Sube la transcripción de tu próxima reunión y Detto estructurará automáticamente de forma inteligente las decisiones, acuerdos y compromisos.</p>
            <button class="btn btn-primary btnw" onclick="nuevaActa()">
              <svg width="14" height="14" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
              Crear primera acta
            </button>
          </div>
        `;
      }
    }
  } else {
    $("actasTable")?.classList.remove("table-hidden");
    $("emptyStateContainer")?.classList.add("hidden");

    $("actasBody").innerHTML=slice.map(a=>{
      const tpl=TEMPLATES.find(t=>t.id===a.template_id);
      const isDraft=a.status!=="approved";
      const cc=confClass(a.avg_confidence);
      const continuarBtn=isDraft?`<button class="action-btn btn-resume" onclick="resumeActa('${a.id}')" title="Reanudar acta" style="margin-right:6px">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
          <polygon points="5 3 19 12 5 21 5 3"/>
        </svg>
      </button>`:'';
      const descargarBtn=`<button class="action-btn" onclick="descargarActaWord('${a.id}')" title="Descargar Word" style="margin-right:6px">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
          <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
          <polyline points="14 2 14 8 20 8"/>
          <line x1="12" y1="18" x2="12" y2="12"/>
          <polyline points="9 15 12 18 15 15"/>
        </svg>
      </button>`;
      const eliminarBtn=`<button class="action-btn btn-delete" onclick="deleteActa('${a.id}')" title="Eliminar acta">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
          <polyline points="3 6 5 6 21 6"/>
          <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
          <line x1="10" y1="11" x2="10" y2="17"/>
          <line x1="14" y1="11" x2="14" y2="17"/>
        </svg>
      </button>`;
      return `<tr>
        <td><b>${esc(tpl?.name||"Acta")}</b><div style="font-size:11.5px;color:var(--muted);margin-top:2px">${new Date(a.created_at).toLocaleDateString('es-CO',{day:'2-digit',month:'short',year:'numeric'})}</div></td>
        <td>${tag(a.status)}</td>
        <td>
          <div class="conf-bar-wrap">
            <span style="font-weight:700;font-size:13px;min-width:36px">${a.avg_confidence}%</span>
            <div class="conf-bar-track"><div class="conf-bar-fill ${cc}" style="width:${a.avg_confidence}%"></div></div>
          </div>
        </td>
        <td style="font-size:13px;color:var(--sub)">${new Date(a.created_at).toLocaleTimeString([],{hour:'2-digit',minute:'2-digit'})}</td>
        <td style="white-space:nowrap">${continuarBtn}${descargarBtn}${eliminarBtn}</td>
      </tr>`;
    }).join('');
  }
  // Paginación
  const bar=$("paginationBar");
  if(pages<=1){bar.classList.add("hidden");}
  else{
    bar.classList.remove("hidden");
    $("pgInfo").textContent=`Mostrando ${(_pg-1)*PG_SIZE+1}–${Math.min(_pg*PG_SIZE,total)} de ${total}`;
    let btns=`<button class="pg-btn" onclick="goPage(${_pg-1})" ${_pg===1?"disabled":""}>‹</button>`;
    for(let p=1;p<=pages;p++) btns+=`<button class="pg-btn${p===_pg?" active":""}" onclick="goPage(${p})">${p}</button>`;
    btns+=`<button class="pg-btn" onclick="goPage(${_pg+1})" ${_pg===pages?"disabled":""}>›</button>`;
    $("pgBtns").innerHTML=btns;
  }
}

function goPage(p){_pg=p;renderActasTable();}

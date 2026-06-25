function renderTemplates(){
  // Lista compacta en W2
  if($("tplListW2")){
    $("tplListW2").innerHTML=TEMPLATES.map((t,i)=>{
      const fc=t.schema?.sections?.reduce((s,sec)=>s+(sec.fields?.length||0),0)||0;
      return `<div class="tpl-item ${i===0?'sel':''}" onclick="selTplW2('${t.id}',this)">
        <span class="ti">${t.icon}</span>
        <div>
          <h5>${esc(t.name)}</h5>
          <p>${esc(t.description||"")}</p>
          <span class="tpl-item-count">${fc} campo${fc!==1?'s':''}</span>
        </div>
      </div>`;
    }).join("");
  }
  // Grid oculto de compatibilidad
  if($("tpls")) $("tpls").innerHTML=TEMPLATES.map((t,i)=>`<div class="tpl ${i===0?'sel':''}" onclick="selTpl('${t.id}',this)">
    <div class="i">${t.icon}</div><h4>${t.name}</h4><p>${t.description}</p></div>`).join("");
  state.template=TEMPLATES[0];
  if(TEMPLATES[0]) renderTplPreview(TEMPLATES[0]);
}

function selTpl(id,el){document.querySelectorAll(".tpl").forEach(t=>t.classList.remove("sel"));el.classList.add("sel");state.template=TEMPLATES.find(t=>t.id===id);}

function selTplW2(id,el){
  document.querySelectorAll(".tpl-item").forEach(t=>t.classList.remove("sel"));
  el.classList.add("sel");
  state.template=TEMPLATES.find(t=>t.id===id);
  renderTplPreview(state.template);
}

function renderTplPreview(tpl){
  const pane=$("tplPreviewPane"); if(!pane||!tpl) return;
  const sections=tpl.schema?.sections||[];
  const totalFields=sections.reduce((s,sec)=>s+(sec.fields?.length||0),0);
  const totalSecs=sections.length;

  pane.innerHTML=`
    <!-- Cabecera de plantilla -->
    <div style="display:flex;align-items:flex-start;gap:14px;padding-bottom:16px;margin-bottom:16px;border-bottom:1px solid var(--line)">
      <div style="width:48px;height:48px;border-radius:12px;background:linear-gradient(135deg,var(--p1),#dbeafe);border:1px solid var(--p2);display:grid;place-items:center;font-size:26px;flex-shrink:0">
        ${tpl.icon}
      </div>
      <div style="flex:1;min-width:0">
        <div style="font-size:17px;font-weight:700;color:var(--ink);margin-bottom:3px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${esc(tpl.name)}</div>
        <div style="font-size:12.5px;color:var(--muted);margin-bottom:8px">${esc(tpl.description||"Sin descripción")}</div>
        <div style="display:flex;gap:8px;flex-wrap:wrap">
          <span class="tag info">📋 ${totalFields} campos</span>
          <span style="font-size:11px;color:var(--muted);display:flex;align-items:center;gap:4px">
            <svg width="12" height="12" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01"/></svg>
            ${totalSecs} sección${totalSecs!==1?'es':''}
          </span>
        </div>
      </div>
    </div>

    <!-- Estructura del documento -->
    <div style="font-size:10.5px;font-weight:700;text-transform:uppercase;letter-spacing:.1em;color:var(--muted);margin-bottom:12px">Estructura del documento</div>
    <div style="display:grid;grid-template-columns:repeat(auto-fill, minmax(220px, 1fr));gap:12px">
      ${sections.map((sec,si)=>{
        const fields=sec.fields||[];
        return `<div style="background:var(--line2);border:1px solid var(--line);border-radius:8px;padding:12px;display:flex;flex-direction:column;gap:8px">
          <div style="display:flex;align-items:center;gap:7px">
            <div style="width:18px;height:18px;border-radius:50%;background:var(--p5);color:#fff;display:grid;place-items:center;font-size:9px;font-weight:700;flex-shrink:0">${si+1}</div>
            <span style="font-size:11px;font-weight:750;text-transform:uppercase;letter-spacing:.02em;color:var(--p6);white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${esc(sec.title)}</span>
            <span style="font-size:10px;color:var(--muted);background:var(--sur);border-radius:100px;padding:1px 6px;margin-left:auto">${fields.length}</span>
          </div>
          <div style="display:flex;flex-wrap:wrap;gap:4px">
            ${fields.map(f=>`<span style="background:#fff;border:1px solid rgba(59,120,214,0.1);border-radius:4px;padding:2px 6px;font-size:10.5px;color:var(--sub);font-weight:500">${esc(f.label)}</span>`).join("")}
          </div>
        </div>`;
      }).join("")}
    </div>
  `;
}

function step(n){
  document.querySelectorAll(".wstep").forEach(s=>s.classList.remove("active"));
  $("w"+n).classList.add("active");
  for(let i=1;i<=4;i++){const s=$("s"+i);s.classList.remove("cur","done");if(i<n)s.classList.add("done");else if(i===n)s.classList.add("cur");}
  $("b1").classList.toggle("done",n>1);
  $("b2").classList.toggle("done",n>2);
  $("b3").classList.toggle("done",n>3);
}

async function uploadFile(inp){
  const f=inp.files[0]; if(!f)return;
  const fd=new FormData(); fd.append("file",f); fd.append("title",f.name);
  toast("Subiendo y extrayendo texto…");
  const r=await fetch(API+"/api/transcripts/upload",{method:"POST",headers:H(),body:fd});
  if(!r.ok){toast("Error al leer el archivo");return;}
  state.transcript=await r.json(); $("ta").value=state.transcript.content;
  $("trTitle").value=state.transcript.title; toast("✓ "+state.transcript.word_count+" palabras extraídas");
}

async function saveTranscript(){
  if(state.transcript && state.transcript.content===$("ta").value){step(2);return;}
  const r=await fetch(API+"/api/transcripts",{method:"POST",headers:{...H(),"Content-Type":"application/json"},
    body:JSON.stringify({title:$("trTitle").value||"Reunión",content:$("ta").value})});
  state.transcript=await r.json(); step(2);
}

async function generate(){
  const btn=$("genBtn");
  btn.innerHTML='<div class="spinner"></div> Analizando…';
  btn.disabled=true; btn.classList.add("btn-generating");
  try{
    const r=await fetch(API+"/api/actas/generate",{method:"POST",headers:{...H(),"Content-Type":"application/json"},
      body:JSON.stringify({transcript_id:state.transcript.id,template_id:state.template.id})});
    if(!r.ok){const e=await r.json();toast("Error: "+(e.detail||"No se pudo generar"));return;}
    state.acta=await r.json();
    renderW3(); step(3);
  }finally{
    btn.innerHTML="✦ Generar acta"; btn.disabled=false; btn.classList.remove("btn-generating");
  }
}

function confClass(c){return c>=85?"hi":c>=50?"mid":"low";}

function renderW3(){
  const a=state.acta;
  if(!a) return;

  // Calcular progreso
  let total=0,filled=0,missing=0;
  for(const sv of Object.values(a.data)) for(const fv of Object.values(sv.fields)){
    total++;
    const v=fv.value;
    const isEmpty=v==null||v===""||v===undefined||(Array.isArray(v)&&v.length===0);
    if(!isEmpty) filled++; else missing++;
  }
  const pct=total>0?Math.round(filled/total*100):100;
  const barColor=pct===100?"var(--ok)":pct>=70?"var(--p5)":"var(--warn)";

  if($("w3Hdr")) $("w3Hdr").innerHTML=`
    <div style="display:flex;align-items:center;gap:16px;background:var(--sur);border:1px solid var(--line);border-radius:var(--r-lg);padding:12px 18px;margin-bottom:16px;box-shadow:var(--sh-xs)">
      <div style="flex:1">
        <div style="height:6px;background:var(--line);border-radius:4px;overflow:hidden;margin-bottom:6px">
          <div style="height:100%;width:${pct}%;background:${barColor};border-radius:4px;transition:.7s ease"></div>
        </div>
        <div style="font-size:12px;color:var(--muted)">
          <b style="color:${barColor}">${filled}/${total}</b> campos completos
          ${missing?` · <span style="color:var(--warn)">⚠ ${missing} sin información</span>`:""}
        </div>
      </div>
      <div style="font-size:22px;font-weight:700;color:${barColor};min-width:52px;text-align:right">${pct}%</div>
    </div>`;

  // Campos por sección agrupados en un solo cuadro general
  let i=0,html=`<div class="w3-container-card">`;
  for(const[sk,sv] of Object.entries(a.data)){
    i++; html+=`<div class="w3-section"><div class="w3-section-title">${i}. ${esc(sv.title)}</div><div class="w3-grid">`;
    const fieldsEntries = Object.entries(sv.fields);
    const totalFields = fieldsEntries.length;

    for(const[fk,fv] of fieldsEntries){
      const v=fv.value;
      const isStrayTimestamp=(fv.type==="date"||fv.type==="time")&&typeof v==="string"&&/^\d{1,2}:\d{2}(:\d{2})?$/.test(v.trim());
      const isEmpty=v==null||v===""||v===undefined||(Array.isArray(v)&&v.length===0)||isStrayTimestamp;
      let dispVal="";
      if(!isEmpty){
        if(Array.isArray(v)) dispVal=v.map(x=>typeof x==="object"?Object.values(x).filter(Boolean).join(" · "):String(x)).join("<br>");
        else dispVal=esc(String(v));
      }

      // Generar type badge
      let typeBadge = "";
      if (fv.type === "people") {
        typeBadge = `<span class="afield-type-badge people">👥 Grupo</span>`;
      } else if (fv.type === "list") {
        typeBadge = `<span class="afield-type-badge list">🔢 Listado</span>`;
      } else if (fv.type === "date" || fv.type === "time") {
        const isTime = fv.type === "time" || fk.toLowerCase().includes("hora") || fv.label.toLowerCase().includes("hora");
        typeBadge = isTime
          ? `<span class="afield-type-badge date">🕒 Hora</span>`
          : `<span class="afield-type-badge date">📅 Fecha</span>`;
      } else {
        typeBadge = `<span class="afield-type-badge">📝 Texto</span>`;
      }

      // Heurística de campo ancho completo
      const isWide = fv.type==="people" || fv.type==="list" || totalFields === 1 || fv.label.toLowerCase().includes("desarrollo") || fv.label.toLowerCase().includes("objetivo") || fv.label.toLowerCase().includes("conclusión") || fv.label.toLowerCase().includes("observación");
      const wideClass = isWide ? " field-wide" : "";

      html+=`<div class="afield${isEmpty?" field-empty":""}${wideClass}" data-sk="${sk}" data-fk="${fk}">
        <div class="ft">
          <span class="flabel">${esc(fv.label)}</span>
          <div style="display:flex; gap:6px; align-items:center;">
            ${typeBadge}
            ${!isEmpty?`<span class="conf ${confClass(fv.confidence)}">${fv.confidence}%</span>`:""}
          </div>
        </div>
        ${isEmpty?`<div class="no-data">Clic para añadir</div>`:`<div class="fval">${dispVal}</div>`}
      </div>`;
    }
    html+="</div></div>";
  }
  html+=`</div>`;
  if($("w3Fields")) $("w3Fields").innerHTML=html;

  // Edición inline
  document.querySelectorAll(".afield").forEach(el=>{
    el.addEventListener("click",()=>{
      const sk=el.dataset.sk, fk=el.dataset.fk;
      const fv=state.acta.data[sk]?.fields[fk];
      if(fv) makeFieldEditable(el,sk,fk,fv);
    });
  });
}

function renderActa(){ renderW3(); } // compatibilidad con resumeActa

function goToPreview(){ renderPreview(); step(4); }

function renderPreview(){
  const a=state.acta;
  if(!a){if($("docSheet"))$("docSheet").innerHTML="<p style='color:var(--muted);padding:24px'>No hay acta generada.</p>";return;}
  const tplName=state.template?.name||"Acta";
  const today=new Date().toLocaleDateString('es-CO',{year:'numeric',month:'long',day:'numeric'});
  const orgName=USER?.org_name||"";
  const cc=confClass(a.avg_confidence);
  const confColor=cc==="hi"?"#0E9A6A":cc==="mid"?"#D97706":"#DC2626";

  // Buscar datos de la reunión para el bloque superior de metadatos
  let datosReunion = {};
  let otherSections = [];

  for(const[sk,sv] of Object.entries(a.data)){
    const skl = sk.toLowerCase();
    if(skl.includes("reunion") || skl.includes("datos") || skl === "encabezado" || skl.includes("identificacion")){
      datosReunion = sv.fields;
    } else {
      otherSections.push(sv);
    }
  }

  if(Object.keys(datosReunion).length === 0 && Object.keys(a.data).length > 0){
    const keys = Object.keys(a.data);
    datosReunion = a.data[keys[0]].fields;
    otherSections = keys.slice(1).map(k => a.data[k]);
  }

  // Construir tabla de metadatos dinámicamente según la plantilla
  let metadataHtml = "";
  if (Object.keys(datosReunion).length > 0) {
    metadataHtml += `<table style="width:100%; border-collapse:collapse; margin-bottom:24px; border:1.5px solid #111; font-size:11px; color:#111;">`;
    const fields = Object.entries(datosReunion);
    for (let k = 0; k < fields.length; k += 2) {
      const [fkey1, fv1] = fields[k];
      const [fkey2, fv2] = (k + 1 < fields.length) ? fields[k + 1] : [null, null];

      const val1 = fv1.value || "—";
      const val2 = fv2 ? (fv2.value || "—") : "";

      metadataHtml += `<tr>
        <td style="width:15%; border:1px solid #111; padding:7px 10px; font-weight:700; background:#f5f6f8;">${esc(fv1.label)}:</td>
        <td style="width:35%; border:1px solid #111; padding:7px 10px;">${esc(String(val1))}</td>`;

      if (fv2) {
        metadataHtml += `<td style="width:15%; border:1px solid #111; padding:7px 10px; font-weight:700; background:#f5f6f8;">${esc(fv2.label)}:</td>
          <td style="width:35%; border:1px solid #111; padding:7px 10px;">${esc(String(val2))}</td>`;
      } else {
        metadataHtml += `<td style="width:15%; border:1px solid #111; padding:7px 10px; background:#f5f6f8;"></td>
          <td style="width:35%; border:1px solid #111; padding:7px 10px;"></td>`;
      }
      metadataHtml += `</tr>`;
    }
    metadataHtml += `</table>`;
  }

  // Renderizar la previsualización tipo plantilla (con alta fidelidad a la imagen corporativa)
  let html=`<div style="font-family:'Inter', sans-serif; color:#111; max-width:100%; padding:8px; line-height:1.4;">

    <!-- Tabla de Encabezado Corporativo -->
    <table style="width:100%; border-collapse:collapse; margin-bottom:20px; border:1.5px solid #111;">
      <tr>
        <td style="width:25%; border:1.5px solid #111; padding:12px; text-align:center; vertical-align:middle;">
          <div style="display:flex; flex-direction:column; align-items:center; gap:4px;">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#2255A4" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
              <circle cx="12" cy="12" r="10"/>
              <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/>
              <path d="M2 12h20"/>
            </svg>
            <span style="font-size:9.5px; font-weight:800; letter-spacing:0.08em; color:#2255A4;">${esc(orgName.toUpperCase())}</span>
          </div>
        </td>
        <td style="width:50%; border:1.5px solid #111; padding:12px; text-align:center; vertical-align:middle; font-weight:800; font-size:14px; letter-spacing:0.04em; color:#111;">
          ${esc(tplName.toUpperCase())}
          <div style="font-size:10px; font-weight:500; color:#555; margin-top:4px;">ACTA DE REUNIÓN</div>
        </td>
        <td style="width:25%; border:1.5px solid #111; padding:8px 12px; font-size:9.5px; font-weight:700; color:#333; line-height:1.45;">
          <div>Código: DOC-SGI-12</div>
          <div>Versión: 03</div>
          <div>Fecha: ${new Date().toLocaleDateString('es-CO', {year:'numeric', month:'2-digit', day:'2-digit'})}</div>
        </td>
      </tr>
    </table>

    <!-- Tabla de Metadatos de Reunión -->
    ${metadataHtml}`;

  let idx = 0;
  for (const sec of otherSections) {
    idx++;
    html += `<div style="margin-bottom:22px;">
      <h3 style="font-size:12px; font-weight:800; text-transform:uppercase; color:#111; margin-bottom:8px; letter-spacing:0.02em;">
        ${idx}. ${esc(sec.title)}.
      </h3>`;

    for (const fv of Object.values(sec.fields)) {
      const v = fv.value;
      const isEmpty = v == null || v === "" || v === undefined || (Array.isArray(v) && v.length === 0);
      const tblType = fv._table_type || "";
      const cols = fv._columns || [];

      // Caso 1: Participantes (Tabla con columnas dinámicas)
      if (tblType === "participants" || fv.type === "people" || fv.label.toLowerCase().includes("participante")) {
        const tableCols = cols.length ? cols : ["ENTIDAD", "NOMBRE", "CARGO"];
        let hasFirma = tableCols.some(c => c.toLowerCase().includes("firma"));
        let headers = [...tableCols];
        if (!hasFirma) headers.push("FIRMA");

        html += `<table style="width:100%; border-collapse:collapse; margin-top:6px; border:1.5px solid #111; font-size:11px;">
          <thead>
            <tr style="background:#f5f6f8; border-bottom:1.5px solid #111;">`;
        headers.forEach(h => {
          html += `<th style="border:1px solid #111; padding:6px 10px; font-weight:700; text-align:left;">${esc(h)}</th>`;
        });
        html += `</tr>
          </thead>
          <tbody>`;

        if (isEmpty) {
          html += `<tr style="height:26px;">`;
          headers.forEach(h => {
            if (h === "FIRMA") {
              html += `<td style="border:1px solid #111; padding:4px 10px; color:#ccc; font-style:italic;">Firma digital</td>`;
            } else {
              html += `<td style="border:1px solid #111; padding:4px 10px; color:#999;">—</td>`;
            }
          });
          html += `</tr>`;
        } else {
          const items = Array.isArray(v) ? v : [v];
          items.forEach(p => {
            html += `<tr>`;
            headers.forEach(h => {
              if (h === "FIRMA") {
                html += `<td style="border:1px solid #111; padding:5px 10px; color:#999; font-style:italic; font-size:10px;">Firma digital</td>`;
              } else {
                const colKey = h.toLowerCase().replace(/[\s_]+/g, "_").replace(/á/g,"a").replace(/é/g,"e").replace(/í/g,"i").replace(/ó/g,"o").replace(/ú/g,"u");
                const pythonKey = h.toLowerCase().replace(/[^\w]+/g, "_").replace(/^_+|_+$/g, "");
                let val = "";
                if (typeof p === "object" && p !== null) {
                  val = p[pythonKey] || p[colKey] || p[h] || p[h.toLowerCase()] || "";
                  if (!val && colKey === "nombre") val = p.nombre || p.name || Object.values(p)[0] || "";
                  if (!val && colKey === "cargo") val = p.cargo || p.role || "";
                  if (!val && colKey === "entidad") val = p.entidad || p.company || p.org || "";
                } else {
                  val = h.toLowerCase().includes("nombre") ? String(p) : "";
                }
                html += `<td style="border:1px solid #111; padding:5px 10px;">${esc(String(val || "—"))}</td>`;
              }
            });
            html += `</tr>`;
          });
        }
        html += `</tbody>
        </table>
        <div style="font-size:9.5px; color:#555; margin-top:5px; font-style:italic;">*Se determina que se cuenta con Quorum para sesionar.</div>`;
      }

      // Caso 2: Compromisos, Temas o tablas genéricas con columnas definidas
      else if (tblType === "commitments" || tblType === "topics" || tblType === "deliverables" || cols.length > 0 || (fv.type === "list" && (fv.label.toLowerCase().includes("compromiso") || fv.label.toLowerCase().includes("actividad") || fv.label.toLowerCase().includes("tarea") || fv.label.toLowerCase().includes("tema") || fv.label.toLowerCase().includes("desarrollo")))) {
        const tableCols = cols.length ? cols : ["TEMA / COMPROMISO", "DESCRIPCIÓN"];
        html += `<table style="width:100%; border-collapse:collapse; margin-top:6px; border:1.5px solid #111; font-size:11px;">
          <thead>
            <tr style="background:#f5f6f8; border-bottom:1.5px solid #111;">`;
        tableCols.forEach(col => {
          html += `<th style="border:1px solid #111; padding:6px 10px; font-weight:700; text-align:left;">${esc(col)}</th>`;
        });
        html += `</tr>
          </thead>
          <tbody>`;

        if (isEmpty) {
          html += `<tr style="height:26px;">`;
          tableCols.forEach(() => {
            html += `<td style="border:1px solid #111; padding:6px 10px; color:#999;">—</td>`;
          });
          html += `</tr>`;
        } else {
          const items = Array.isArray(v) ? v : [v];
          items.forEach(item => {
            html += `<tr>`;
            tableCols.forEach(col => {
              const colKey = col.toLowerCase().replace(/[\s_]+/g, "_").replace(/á/g,"a").replace(/é/g,"e").replace(/í/g,"i").replace(/ó/g,"o").replace(/ú/g,"u");
              const pythonKey = col.toLowerCase().replace(/[^\w]+/g, "_").replace(/^_+|_+$/g, "");
              let val = "";
              if (typeof item === "object" && item !== null) {
                val = item[pythonKey] || item[colKey] || item[col] || item[col.toLowerCase()] || "";
                if (!val && tableCols.indexOf(col) === 0) val = item.compromiso || item.tarea || item.actividad || item.tema || Object.values(item)[0] || "";
                if (!val && colKey.includes("responsable")) val = item.responsable || item.name || "";
                if (!val && (colKey.includes("fecha") || colKey.includes("plazo"))) val = item.fecha || item.plazo || item.fecha_compromiso || "";
              } else if (typeof item === "string") {
                if (item.includes(":") && tableCols.length === 2) {
                  const parts = item.split(":");
                  const isFirstCol = tableCols.indexOf(col) === 0;
                  val = isFirstCol ? parts[0].trim() : parts.slice(1).join(":").trim();
                } else {
                  const isFirstCol = tableCols.indexOf(col) === 0;
                  val = isFirstCol ? item : "";
                }
              }
              html += `<td style="border:1px solid #111; padding:6px 10px; vertical-align:top;">${esc(String(val || "—")).replace(/\n/g, "<br>")}</td>`;
            });
            html += `</tr>`;
          });
        }
        html += `</tbody></table>`;
      }

      // Caso 3: Listas simples (Agenda, entregables sin tabla, etc. con ❖)
      else if (fv.type === "list" || Array.isArray(v)) {
        if (isEmpty) {
          html += `<div style="padding-left:14px; color:#aaa; font-style:italic; margin-top:4px;">—</div>`;
        } else {
          html += `<div style="margin-top:4px; display:flex; flex-direction:column; gap:4px; padding-left:4px; font-size:11.5px;">`;
          const items = Array.isArray(v) ? v : [v];
          items.forEach(item => {
            html += `<div style="display:flex; gap:8px; align-items:flex-start;">
              <span style="color:#2255A4; font-size:9px; margin-top:2px;">❖</span>
              <div style="flex:1; color:#222;">${esc(String(item))}</div>
            </div>`;
          });
          html += `</div>`;
        }
      }

      // Caso 4: Textos simples
      else {
        if (isEmpty) {
          html += `<div style="padding-left:14px; color:#aaa; font-style:italic; margin-top:4px;">—</div>`;
        } else {
          html += `<div style="margin-top:4px; padding-left:4px; line-height:1.5; white-space:pre-wrap; color:#222; font-size:11.5px;">${esc(String(v))}</div>`;
        }
      }
    }
    html += `</div>`;
  }

  // Notas finales Corporativas
  html += `<div style="margin-top:36px; border-top:1.5px solid #111; padding-top:12px; font-size:9.5px; line-height:1.5; color:#555; font-family:'Inter', sans-serif;">
    <div style="margin-bottom:6px;"><b>Importante:</b> La firma del acta tiene como finalidad dejar constancia de la revisión y conformidad por parte del cliente respecto a los temas tratados y acuerdos alcanzados durante la reunión.</div>
    <div>La ausencia de firma no exime al cliente del conocimiento ni del cumplimiento de la información contenida en el acta, ya que su envío a través de medios electrónicos (correo electrónico / documento adjunto) constituye prueba suficiente de su entrega y comunicación oficial.</div>
  </div></div>`;

  if($("docSheet")) $("docSheet").innerHTML=html;
  if($("avgConf")) $("avgConf").textContent=a.avg_confidence+"%";
  if($("approveBtn")){$("approveBtn").disabled=false;$("approveBtn").style.display="inline-flex";}
  if($("btn-descargar-word")){$("btn-descargar-word").disabled=true;$("btn-descargar-word").classList.replace("btn-primary","btn-line");}
}

function renderFillPanel(){
  const a=state.acta;
  if(!a){$("fillPanel").classList.add("hidden");return;}

  // Todos los campos vacíos (sin distinción de obligatorio/opcional)
  const empty=[];
  for(const[sk,sv] of Object.entries(a.data)){
    for(const[fk,fv] of Object.entries(sv.fields)){
      const v=fv.value;
      const isEmpty=v==null||v===""||v===undefined||(Array.isArray(v)&&v.length===0);
      const isLowConf=fv.confidence<50&&(v!=null&&v!=="");
      if(!isEmpty&&!isLowConf) continue;

      // Pre-poblar si la IA puso algo de baja confianza
      const currentVal = serializeFieldVal(fv);
      empty.push({sk,fk,label:fv.label,type:fv.type||"text",sec:sv.title,currentVal});
    }
  }

  // Banner de éxito: todo completo
  if(empty.length===0){
    $("fillPanel").innerHTML=`<div class="fp-done-banner">
      <div class="fp-done-icon">✓</div>
      <div><div style="font-weight:700;color:var(--ok);font-size:15px">Toda la información está completa</div>
        <div style="font-size:12.5px;color:var(--ok);margin-top:2px">El acta está lista para ser aprobada.</div></div>
    </div>`;
    $("fillPanel").classList.remove("hidden");
    return;
  }

  // Progreso general: cuántos campos tienen valor vs total
  let totalFields=0,filledFields=0;
  for(const sv of Object.values(a.data)) for(const fv of Object.values(sv.fields)){
    totalFields++;
    const v=fv.value;
    if(v!=null&&v!==""&&!(Array.isArray(v)&&v.length===0)&&fv.confidence>=50) filledFields++;
  }
  const pct=totalFields>0?Math.round(filledFields/totalFields*100):100;
  const totalEmpty=empty.length;

  // Card de cada campo: input sin borde propio, la tarjeta es el contenedor
  const makeCard=(item)=>{
    const{sk,fk,type,label,sec,currentVal}=item;
    const id=`fp-${sk}-${fk}`;
    const isHora=fk.includes("hora")||label.toLowerCase().includes("hora");
    const hasPreFill=currentVal&&currentVal.length>0;
    const preFillNote=hasPreFill
      ?`<div class="fp-prefill-note">⚠ Revisa el valor sugerido</div>`
      :``;
    let inp;
    if(type==="date"){
      inp=isHora
        ?`<input class="fp-input" type="time" id="${id}" value="${esc(currentVal)}" oninput="updateFpCounter()">`
        :`<input class="fp-input" type="date" id="${id}" value="${esc(currentVal)}" oninput="updateFpCounter()">`;
    }else if(type==="list"){
      inp=`<textarea class="fp-input" id="${id}" rows="2" placeholder="Un elemento por línea" oninput="updateFpCounter()">${esc(currentVal)}</textarea>`;
    }else if(type==="people"){
      inp=`<textarea class="fp-input" id="${id}" rows="2" placeholder="Nombre, Cargo, Entidad" oninput="updateFpCounter()">${esc(currentVal)}</textarea>`;
    }else{
      inp=`<input class="fp-input" type="text" id="${id}" value="${esc(currentVal)}" placeholder="Escribe aquí…" oninput="updateFpCounter()">`;
    }
    return `<div class="fp-card${hasPreFill?" fp-card-prefill":""}">
      <div class="fp-card-lbl"><span class="fp-card-lbl-dot"></span>${esc(label)}</div>
      ${preFillNote}${inp}
    </div>`;
  };

  let html=`<div class="fp-header">
    <div class="fp-header-top">
      <div>
        <div class="fp-title"><div class="fp-title-icon">✎</div>Registro manual de información</div>
        <div class="fp-subtitle">${totalEmpty} campo${totalEmpty!==1?"s":""} sin información — puedes completarlos antes de aprobar el acta.</div>
      </div>
      <div class="fp-counter-box">
        <div class="fp-counter-num">${filledFields}<span style="font-size:15px;font-weight:400;color:var(--muted)">/${totalFields}</span></div>
        <div class="fp-counter-lbl">completados</div>
      </div>
    </div>
    <div class="fp-prog-track"><div class="fp-prog-bar" style="width:${pct}%"></div></div>
  </div>
  <div class="fp-body">
    <div class="fp-group-lbl">Campos a completar</div>
    <div class="fp-grid">`;
  empty.forEach(item=>{html+=makeCard(item);});
  html+=`</div>`;

  html+=`</div>
  <div class="fp-footer">
    <div class="fp-footer-hint"><b id="fp-typed-count">0</b> de ${totalEmpty} campos diligenciados</div>
    <button class="fp-save-btn" id="fp-save-btn" onclick="saveAllFields()">Guardar información ✓</button>
  </div>`;

  $("fillPanel").innerHTML=html;
  $("fillPanel").classList.remove("hidden");
}

function updateFpCounter(){
  const inputs=document.querySelectorAll(".fp-input");
  const count=[...inputs].filter(el=>el.value.trim().length>0).length;
  const el=$("fp-typed-count");
  if(el) el.textContent=count;
}

async function saveAllFields(){
  const a=state.acta;
  if(!a) return;
  const btn=$("fp-save-btn");
  if(btn){btn.disabled=true;btn.textContent="Guardando…";}

  // Recopilar todos los campos con valor del panel
  const updates=[];
  for(const[sk,sv] of Object.entries(a.data)){
    for(const[fk,fv] of Object.entries(sv.fields)){
      const el=$(`fp-${sk}-${fk}`);
      if(!el||!el.value.trim()) continue;
      const raw = el.value.trim();
      const v = parseFieldVal(raw, fv);
      if(Array.isArray(v) && v.length === 0) continue;
      updates.push({section_key:sk,field_key:fk,value:v});
    }
  }

  if(!updates.length){
    toast("No hay campos con información para guardar");
    if(btn){btn.disabled=false;btn.textContent="Guardar información ✓";}
    return;
  }

  // Enviar en secuencia
  for(const upd of updates){
    const r=await fetch(API+"/api/actas/"+a.id+"/field",{
      method:"PATCH",headers:{...H(),"Content-Type":"application/json"},
      body:JSON.stringify(upd)
    });
    if(r.ok) state.acta=await r.json();
  }

  renderW3();
  toast(`✓ ${updates.length} campo${updates.length>1?"s":""} guardado${updates.length>1?"s":""}`);
}

async function approve(){
  const btn=$("approveBtn");
  btn.innerHTML='<div class="spinner"></div> Aprobando…'; btn.disabled=true;
  const r=await fetch(API+"/api/actas/"+state.acta.id+"/approve",{method:"POST",headers:H()});
  btn.innerHTML="Aprobar acta ✓"; btn.disabled=false;
  if(r.ok){
    state.acta.status="approved";
    if($("btn-descargar-word")){$("btn-descargar-word").disabled=false;$("btn-descargar-word").classList.replace("btn-line","btn-primary");}
    if($("approveBtn")) $("approveBtn").style.display="none";
    launchConfetti();
    $("approveOverlay").classList.remove("hidden");
  } else toast("No se pudo aprobar el acta");
}

function closeApproveOverlay(){
  $("approveOverlay").classList.add("hidden");
}

function launchConfetti(){
  const colors=["#2255A4","#3B78D6","#0E9A6A","#6FA3E8","#FCD34D","#F472B6"];
  for(let i=0;i<42;i++){
    const el=document.createElement("div");
    el.className="confetti-piece";
    el.style.cssText=`
      left:${Math.random()*100}vw;
      top:-10px;
      background:${colors[Math.floor(Math.random()*colors.length)]};
      width:${6+Math.random()*6}px;
      height:${6+Math.random()*6}px;
      border-radius:${Math.random()>0.5?"50%":"2px"};
      animation-duration:${1.5+Math.random()*1.5}s;
      animation-delay:${Math.random()*0.5}s;
    `;
    document.body.appendChild(el);
    el.addEventListener("animationend",()=>el.remove());
  }
}

/* ══ RESALTADO DE FUENTE ═════════════════════════════ */
function highlightSource(src){
  const panel=$("trPanel");
  if(!panel||!src)return;
  const text=state.transcript?.content||"";
  const escaped=src.replace(/[.*+?^${}()|[\]\\]/g,"\\$&");
  const highlighted=text.replace(new RegExp(`(${escaped})`,"gi"),'<mark>$1</mark>');
  panel.innerHTML=highlighted;
  panel.querySelector("mark")?.scrollIntoView({behavior:"smooth",block:"center"});
  setTimeout(()=>{panel.innerHTML=text;},3500);
}

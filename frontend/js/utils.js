let tm; function toast(m){const t=$("toast");t.textContent=m;t.classList.add("show");clearTimeout(tm);tm=setTimeout(()=>t.classList.remove("show"),2800);}

/* ══ 1. PDF EXPORT ══════════════════════════════════════ */
async function exportPDF(){
  if(!state.acta){toast("Genera un acta primero");return;}
  toast("Generando PDF…");
  const a=state.acta;
  const tplName=state.template?.name||"Acta";
  let html=`<div style="font-family:Inter,sans-serif;color:#0D1829;padding:0">
    <div style="border-bottom:3px solid #2255A4;padding-bottom:16px;margin-bottom:24px">
      <div style="font-size:11px;font-weight:700;letter-spacing:.12em;text-transform:uppercase;color:#2255A4;margin-bottom:6px">Detto · Acta de Reunión</div>
      <div style="font-size:22px;font-weight:700;margin-bottom:4px">${esc(tplName)}</div>
      <div style="font-size:12px;color:#8896A8">Generada el ${new Date().toLocaleDateString('es-CO',{year:'numeric',month:'long',day:'numeric'})}</div>
    </div>`;
  let i=0;
  for(const[,sv] of Object.entries(a.data)){
    i++;
    html+=`<div style="margin-bottom:22px">
      <div style="font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.1em;color:#8896A8;border-bottom:1px solid #E8EEF6;padding-bottom:6px;margin-bottom:12px">${i}. ${esc(sv.title)}</div>`;
    for(const[,fv] of Object.entries(sv.fields)){
      const v=fv.value;
      const isEmpty=v==null||v===""||v===undefined||(Array.isArray(v)&&v.length===0);
      let dispVal=isEmpty?"—":Array.isArray(v)?v.map(x=>typeof x==="object"?Object.values(x).filter(Boolean).join(" · "):String(x)).join(", "):String(v);
      html+=`<div style="margin-bottom:10px;padding:10px 12px;border:1px solid #E8EEF6;border-radius:8px;break-inside:avoid">
        <div style="font-size:10px;font-weight:600;text-transform:uppercase;letter-spacing:.06em;color:#8896A8;margin-bottom:4px">${esc(fv.label)}</div>
        <div style="font-size:13px;color:${isEmpty?'#AAB4BF':'#0D1829'}">${esc(dispVal)}</div>
      </div>`;
    }
    html+="</div>";
  }
  html+=`<div style="margin-top:32px;padding-top:14px;border-top:1px solid #E8EEF6;font-size:11px;color:#AAB4BF;display:flex;justify-content:space-between">
    <span>Detto · ${esc(USER.org_name||"")}</span><span>Confianza de análisis: ${a.avg_confidence}%</span>
  </div></div>`;
  const el=$("print-area");
  el.innerHTML=html; el.classList.remove("hidden");
  await html2pdf().set({
    margin:[14,14,14,14],filename:`Acta_${tplName}_${new Date().toISOString().slice(0,10)}.pdf`,
    html2canvas:{scale:2,useCORS:true},
    jsPDF:{unit:'mm',format:'a4',orientation:'portrait'}
  }).from(el).save();
  el.classList.add("hidden"); el.innerHTML="";
  toast("✓ PDF descargado");
}

/* ══ 2. EDICIÓN INLINE ══════════════════════════════════ */
function serializeFieldVal(fv) {
  const v = fv.value;
  if (v == null) return "";
  if (!Array.isArray(v)) return String(v);

  const cols = fv._columns || [];
  if (cols.length > 0) {
    const colKeys = cols.map(c => c.toLowerCase().replace(/[^\w]+/g, "_").replace(/^_+|_+$/g, ""));
    return v.map(row => {
      if (typeof row === "object" && row !== null) {
        return colKeys.map(key => (row[key] !== undefined && row[key] !== null) ? row[key] : "").join(", ");
      }
      return String(row);
    }).join("\n");
  }

  if (fv.type === "people") {
    return v.map(p => {
      if (typeof p === "object" && p !== null) {
        return [p.nombre || "", p.cargo || "", p.entidad || ""].filter(Boolean).join(", ");
      }
      return String(p);
    }).join("\n");
  }

  return v.map(String).join("\n");
}

function parseFieldVal(raw, fv) {
  const rawClean = raw.trim();
  if (!rawClean) return fv.type === "list" || fv.type === "people" ? [] : "";

  const cols = fv._columns || [];
  if (cols.length > 0) {
    const colKeys = cols.map(c => c.toLowerCase().replace(/[^\w]+/g, "_").replace(/^_+|_+$/g, ""));
    return rawClean.split("\n").map(line => {
      const parts = line.split(",").map(x => x.trim());
      const obj = {};
      colKeys.forEach((key, idx) => {
        obj[key] = parts[idx] || "";
      });
      return obj;
    });
  }

  if (fv.type === "people") {
    return rawClean.split("\n").map(line => {
      const parts = line.split(",").map(x => x.trim());
      return {
        nombre: parts[0] || "",
        cargo: parts[1] || "",
        entidad: parts[2] || ""
      };
    }).filter(p => p.nombre);
  }

  if (fv.type === "list") {
    return rawClean.split("\n").map(s => s.trim()).filter(Boolean);
  }

  return rawClean;
}

function makeFieldEditable(el,sk,fk,fv){
  if(el.querySelector(".field-inline-edit")) return;
  const current = serializeFieldVal(fv);
  const isArray = Array.isArray(fv.value);
  const inp=document.createElement(isArray||current.length>80?"textarea":"input");
  inp.className="field-inline-edit";
  inp.value=current;
  if(inp.tagName==="TEXTAREA"){inp.rows=3;}
  el.querySelector(".fval,.no-data").replaceWith(inp);
  inp.focus();
  const save=async()=>{
    const raw=inp.value.trim();
    if(!raw&&!current){inp.closest(".afield").querySelector(".field-inline-edit").replaceWith(Object.assign(document.createElement("div"),{className:"no-data",textContent:"— sin información —"}));return;}
    if(raw===current){renderActa();return;}
    const val = parseFieldVal(raw, fv);
    inp.disabled=true; inp.classList.add("inline-saving");
    const r=await fetch(API+"/api/actas/"+state.acta.id+"/field",{
      method:"PATCH",headers:{...H(),"Content-Type":"application/json"},
      body:JSON.stringify({section_key:sk,field_key:fk,value:val})
    });
    if(r.ok){state.acta=await r.json();renderActa();toast("✓ Campo actualizado");}
    else{inp.disabled=false;inp.classList.remove("inline-saving");toast("No se pudo guardar");}
  };
  inp.addEventListener("blur",save);
  inp.addEventListener("keydown",e=>{if(!isArray&&e.key==="Enter"){e.preventDefault();save();}if(e.key==="Escape"){renderActa();}});
}

async function descargarActaWord(actaId) {
    if(!actaId) return;
    try {
        toast("Generando documento...");
        const r = await fetch(API+"/api/actas/"+actaId+"/download", { method: "GET", headers: H() });
        if (!r.ok) { alert("No se pudo descargar: " + (await r.json()).detail); return; }
        const blob = await r.blob(); const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a'); a.href = url; a.download = `Acta_${actaId}.docx`;
        document.body.appendChild(a); a.click(); a.remove(); window.URL.revokeObjectURL(url);
        toast("✓ Descarga completada");
    } catch (error) { alert("Ocurrió un error de red al intentar descargar."); }
}

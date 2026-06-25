async function subirPlantillaWord(event) {
    event.preventDefault();
    const fileInput = $("templateFile");
    const btn = $("btn-upload-tpl");
    if (fileInput.files.length === 0) return;
    btn.textContent = "Subiendo..."; btn.disabled = true;
    const formData = new FormData();
    formData.append("name", $("templateName").value);
    formData.append("description", $("templateDesc").value);
    formData.append("file", fileInput.files[0]);
    try {
        const r = await fetch(API+"/api/templates/upload", { method: "POST", headers: { "Authorization": "Bearer " + TOKEN }, body: formData });
        if (r.ok) {
            toast("✓ Plantilla creada con éxito");
            $("form-upload-template").reset();
            TEMPLATES = await (await fetch(API+"/api/templates", {headers: H()})).json();
            renderTemplates(); loadTemplatesPage();
        } else { toast("Error: " + (await r.json()).detail); }
    } catch(e) { toast("Error de red al subir"); }
    btn.textContent = "Subir Plantilla Word"; btn.disabled = false;
}

function openEditTpl(id){
  const t=TEMPLATES.find(x=>x.id===id);
  if(!t) return;
  $("editTplId").value=id;
  $("editTplName").value=t.name;
  $("editTplDesc").value=t.description||"";
  const m=$("editTplModal");
  m.classList.remove("hidden");
  m.style.display="flex";
  setTimeout(()=>$("editTplName").focus(),50);
}

function closeEditTpl(){
  const m=$("editTplModal");
  m.classList.add("hidden");
  m.style.display="none";
}

async function saveEditTpl(){
  const id=$("editTplId").value;
  const name=$("editTplName").value.trim();
  if(!name){$("editTplName").focus();return;}
  const r=await fetch(API+"/api/templates/"+id,{
    method:"PATCH",headers:{...H(),"Content-Type":"application/json"},
    body:JSON.stringify({name,description:$("editTplDesc").value.trim()})
  });
  if(r.ok){closeEditTpl();toast("Plantilla actualizada");loadTemplatesPage();}
  else toast("No se pudo guardar");
}

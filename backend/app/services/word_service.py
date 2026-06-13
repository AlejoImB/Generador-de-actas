"""Extracción de schema y renderizado de plantillas Word.

Soporta dos tipos de plantilla:
  - Jinja2: contienen {{ variable }} — se extraen las variables y su contexto.
  - Estructural: plantillas corporativas con tablas y encabezados en MAYÚSCULAS,
    sin placeholders — se analiza la estructura (tablas + secciones) para
    generar un schema rico que la IA pueda llenar desde la transcripción.
"""
import io
import re
import copy
from docxtpl import DocxTemplate
from docx import Document
from docx.oxml.ns import qn


# ─────────────────────────────────────────────────────────────────────────────
# Entrada pública
# ─────────────────────────────────────────────────────────────────────────────

def extract_schema_from_docx(file_bytes: bytes) -> dict:
    tpl = DocxTemplate(io.BytesIO(file_bytes))
    jinja_vars = tpl.get_undeclared_template_variables()
    if jinja_vars:
        schema = _extract_jinja2_schema(file_bytes, jinja_vars)
        schema["_tpl_type"] = "jinja2"
    else:
        schema = _extract_structural_schema(file_bytes)
        schema["_tpl_type"] = "structural"
    return schema


def render_acta_to_docx(template_path: str, acta_data: dict, tpl_type: str = "auto") -> bytes:
    """Elige el método de renderizado según el tipo de plantilla."""
    if tpl_type == "auto":
        with open(template_path, "rb") as f:
            raw = f.read()
        tpl = DocxTemplate(io.BytesIO(raw))
        tpl_type = "jinja2" if tpl.get_undeclared_template_variables() else "structural"

    if tpl_type == "jinja2":
        return _render_jinja2(template_path, acta_data)
    else:
        return _render_structural(template_path, acta_data)


# ─────────────────────────────────────────────────────────────────────────────
# Extracción: plantillas Jinja2
# ─────────────────────────────────────────────────────────────────────────────

def _extract_jinja2_schema(file_bytes: bytes, all_vars: set) -> dict:
    doc = Document(io.BytesIO(file_bytes))
    var_info = {v: {"surrounding": "", "section": "General"} for v in all_vars}
    section_order = ["General"]
    section_vars: dict[str, list] = {"General": []}
    current_section = "General"

    def _process(text: str):
        for var in re.findall(r"\{\{\s*(\w+)\s*\}\}", text):
            if var not in all_vars:
                continue
            clean = re.sub(r"\{\{[^}]*\}\}", "", text).strip(" :-–—\t\n")
            if not var_info[var]["surrounding"]:
                var_info[var]["surrounding"] = clean[:150]
            var_info[var]["section"] = current_section
            bucket = section_vars.setdefault(current_section, [])
            if var not in bucket:
                bucket.append(var)

    for para in doc.paragraphs:
        text = para.text.strip()
        if not text:
            continue
        style = para.style.name if para.style else ""
        if any(k in style for k in ("Heading", "Título", "Title", "Header")):
            current_section = text
            if current_section not in section_order:
                section_order.append(current_section)
            section_vars.setdefault(current_section, [])
        else:
            _process(text)

    for table in doc.tables:
        for row in table.rows:
            for cell in table.cells:
                for para in cell.paragraphs:
                    _process(para.text.strip())

    assigned = {v for vs in section_vars.values() for v in vs}
    for v in sorted(all_vars):
        if v not in assigned:
            section_vars["General"].append(v)

    sections = []
    for sec_title in section_order:
        vars_here = section_vars.get(sec_title, [])
        if not vars_here:
            continue
        fields = []
        for var in vars_here:
            sur = var_info[var]["surrounding"]
            ftype = _infer_type(var, sur)
            label = sur if sur else var.replace("_", " ").title()
            fields.append({
                "key": var, "label": label[:100], "type": ftype,
                "required": _is_required(var, sur),
                "hint": _build_hint(var, sur, ftype),
            })
        sec_key = _to_key(sec_title)
        sections.append({"key": sec_key, "title": sec_title, "fields": fields})

    if not sections:
        sections = [{"key": "contenido", "title": "Contenido", "fields": [
            {"key": v, "label": v.replace("_", " ").title(),
             "type": _infer_type(v, ""), "required": _is_required(v, ""),
             "hint": _build_hint(v, "", _infer_type(v, ""))}
            for v in sorted(all_vars)
        ]}]

    return {"sections": sections}


# ─────────────────────────────────────────────────────────────────────────────
# Extracción: plantillas estructurales (tablas corporativas)
# ─────────────────────────────────────────────────────────────────────────────

def _extract_structural_schema(file_bytes: bytes) -> dict:
    """Lee el documento elemento a elemento (párrafos y tablas en orden)
    para construir un schema fiel a la estructura corporativa."""
    doc = Document(io.BytesIO(file_bytes))
    body = doc.element.body
    para_tag, tbl_tag = qn("w:p"), qn("w:tbl")

    # Índices para correlacionar elementos XML con objetos python-docx
    para_list = list(doc.paragraphs)
    tbl_list = list(doc.tables)
    para_idx = tbl_idx = 0

    elements: list[tuple[str, object]] = []
    for child in body:
        if child.tag == para_tag and para_idx < len(para_list):
            elements.append(("para", para_list[para_idx]))
            para_idx += 1
        elif child.tag == tbl_tag and tbl_idx < len(tbl_list):
            elements.append(("table", tbl_list[tbl_idx]))
            tbl_idx += 1

    sections: list[dict] = []
    header_table_done = False
    i = 0

    while i < len(elements):
        kind, elem = elements[i]

        # ── Primera tabla siempre = encabezado (metadata) ──────────────────
        if kind == "table" and not header_table_done:
            header_table_done = True
            fields = _parse_header_table(elem)
            if fields:
                sections.append({
                    "key": "encabezado",
                    "title": "Datos de la Reunión",
                    "fields": fields,
                })
            i += 1
            continue

        # ── Párrafo de encabezado ───────────────────────────────────────────
        if kind == "para" and _is_section_heading(elem):
            heading = elem.text.strip().rstrip(".").strip()

            # ¿Le sigue una tabla?
            if i + 1 < len(elements) and elements[i + 1][0] == "table":
                sec = _parse_table_section(heading, elements[i + 1][1])
                if sec:
                    sections.append(sec)
                i += 2
            else:
                sec = _make_text_section(heading)
                if sec:
                    sections.append(sec)
                i += 1
            continue

        i += 1

    return {"sections": sections}


def _is_section_heading(para) -> bool:
    text = para.text.strip()
    if not text or len(text) < 3:
        return False
    style = para.style.name if para.style else ""
    if any(k in style for k in ("Heading", "Título", "Title")):
        return True
    clean = text.rstrip(".")
    return clean.isupper() and len(clean) > 3


def _parse_header_table(tbl) -> list:
    """Tabla tipo: | Etiqueta: | [valor] | Etiqueta: | [valor] |"""
    fields, seen = [], set()
    for row in tbl.rows:
        cells = row.cells
        j = 0
        while j < len(cells) - 1:
            label = cells[j].text.strip().rstrip(":").strip()
            if label and label not in seen and len(label) > 1:
                seen.add(label)
                key = _to_key(label)
                ftype = _infer_type(key, label)
                fields.append({
                    "key": key,
                    "label": label,
                    "type": ftype,
                    "required": _is_required(key, label),
                    "hint": _build_hint(key, label, ftype),
                })
            j += 2
    return fields


def _parse_table_section(heading: str, tbl) -> dict | None:
    """Convierte una sección con tabla en campos del schema según los headers."""
    if not tbl.rows:
        return None
    headers = [c.text.strip() for c in tbl.rows[0].cells]
    h_join = " ".join(h.lower() for h in headers if h)
    sec_key = _to_key(heading)

    # ── Tabla de participantes ─────────────────────────────────────────────
    if any(k in h_join for k in ("nombre", "entidad", "firma", "participante", "cargo")):
        cols = [h for h in headers if h and "firma" not in h.lower()]
        return {
            "key": sec_key, "title": heading,
            "fields": [{
                "key": sec_key,
                "label": f"Participantes ({' | '.join(cols)})",
                "type": "people",
                "required": True,
                "hint": (
                    f"Extrae de la transcripción TODOS los participantes presentes. "
                    f"Para cada uno indica: {', '.join(cols)}. "
                    f"Devuelve un array con un objeto por persona: "
                    f'{{"nombre": "...", "cargo": "...", "entidad": "..."}}.'
                ),
                "_table_type": "participants",
                "_columns": cols,
            }],
        }

    # ── Tabla de compromisos / actividades ────────────────────────────────
    if any(k in h_join for k in ("actividad", "responsable", "estado", "tarea", "comprom")):
        cols = [h for h in headers if h]
        return {
            "key": sec_key, "title": heading,
            "fields": [{
                "key": sec_key,
                "label": f"Compromisos ({' | '.join(cols)})",
                "type": "list",
                "required": False,
                "hint": (
                    f"Extrae los compromisos o tareas mencionados en la transcripción. "
                    f"Para cada compromiso devuelve: {', '.join(cols)}. "
                    f"Devuelve un array: "
                    f'{[{c.lower().replace(" ","_"): "..." for c in cols}]}.'
                ),
                "_table_type": "commitments",
                "_columns": cols,
            }],
        }

    # ── Tabla de entregables (antes de temas para evitar falso match con "descripci") ──
    if (any(k in h_join for k in ("entregable", "material")) or
            ("tipo" in h_join and "tema" not in h_join)):
        return {
            "key": sec_key, "title": heading,
            "fields": [{
                "key": sec_key,
                "label": "Entregables o documentos compartidos",
                "type": "list",
                "required": False,
                "hint": (
                    "Lista de documentos, materiales o entregables mencionados. "
                    "Devuelve un array de strings."
                ),
                "_table_type": "deliverables",
            }],
        }

    # ── Tabla de temas / agenda ───────────────────────────────────────────
    if any(k in h_join for k in ("tema", "descripci", "punto", "agenda")):
        return {
            "key": sec_key, "title": heading,
            "fields": [{
                "key": sec_key,
                "label": "Temas tratados",
                "type": "list",
                "required": False,
                "hint": (
                    "Lista de temas, puntos de agenda o actividades abordados durante la reunión. "
                    "Devuelve un array de strings, uno por tema."
                ),
                "_table_type": "topics",
            }],
        }

    # ── Tabla genérica ────────────────────────────────────────────────────
    fields = []
    for h in headers:
        if not h:
            continue
        key = _to_key(h)
        ftype = _infer_type(key, h)
        fields.append({
            "key": key, "label": h, "type": ftype,
            "required": False, "hint": _build_hint(key, h, ftype),
        })
    return {"key": sec_key, "title": heading, "fields": fields} if fields else None


def _make_text_section(heading: str) -> dict | None:
    h_low = heading.lower()
    skip = {"evidencias", "cierre", "firma", "elaboro", "elaboró", "aprobado", "proxima", "siguiente"}
    if any(k in h_low for k in skip):
        return None
    sec_key = _to_key(heading)
    ftype = "people" if any(k in h_low for k in ("participante", "asistente")) else \
            "list" if any(k in h_low for k in ("agenda", "puntos", "temas", "anexo")) else "text"
    return {
        "key": sec_key, "title": heading,
        "fields": [{
            "key": sec_key,
            "label": heading.title(),
            "type": ftype,
            "required": any(k in h_low for k in ("objetivo", "desarrollo", "proposit", "alcance")),
            "hint": _build_hint(sec_key, heading, ftype),
        }],
    }


# ─────────────────────────────────────────────────────────────────────────────
# Renderizado
# ─────────────────────────────────────────────────────────────────────────────

def _render_jinja2(template_path: str, acta_data: dict) -> bytes:
    doc = DocxTemplate(template_path)
    context: dict = {}
    for sec_val in acta_data.values():
        for field_key, field_val in sec_val.get("fields", {}).items():
            value = field_val.get("value", "") or ""
            if isinstance(value, list):
                value = ", ".join(str(v) for v in value)
            context[field_key] = str(value)
    doc.render(context)
    out = io.BytesIO()
    doc.save(out)
    return out.getvalue()


def _render_structural(template_path: str, acta_data: dict) -> bytes:
    """Rellena plantillas corporativas usando python-docx.
    Usa un índice por tipo de tabla para tolerar múltiples secciones del mismo tipo."""
    doc = Document(template_path)
    tables = doc.tables

    # Aplanar todos los campos para la tabla de encabezado y párrafos de texto
    flat: dict = {}
    for sec_val in acta_data.values():
        for fk, fv in sec_val.get("fields", {}).items():
            if fk not in flat:  # primera ocurrencia gana para texto libre
                flat[fk] = fv.get("value")

    # Índice tipado: agrupa valores por categoría semántica en orden de sección
    typed: dict[str, list] = {"people": [], "commits": [], "topics": [], "deliverables": []}
    for sec_val in acta_data.values():
        for fk, fv in sec_val.get("fields", {}).items():
            v = fv.get("value")
            if not v:
                continue
            ftype = fv.get("type", "")
            flabel = (fv.get("label", "") + " " + fk).lower()
            if ftype == "people":
                typed["people"].append(v)
            elif ftype == "list":
                if any(k in flabel for k in ("comprom", "actividad", "tarea", "responsabl")):
                    typed["commits"].append(v)
                elif any(k in flabel for k in ("entregable", "document", "material")):
                    typed["deliverables"].append(v)
                else:
                    typed["topics"].append(v)

    # Punteros para ir consumiendo valores de cada categoría en orden
    ptr = {k: 0 for k in typed}

    # ── Tabla 0: header metadata ──────────────────────────────────────────
    if tables:
        hdr_tbl = tables[0]
        for row in hdr_tbl.rows:
            cells = row.cells
            j = 0
            while j < len(cells) - 1:
                label = cells[j].text.strip().rstrip(":").strip()
                key = _to_key(label)
                value = flat.get(key)
                if value is not None and not cells[j + 1].text.strip():
                    _set_cell_text(cells[j + 1], str(value))
                j += 2

    # ── Tablas siguientes: rellenar por tipo de tabla ─────────────────────
    for tbl in tables[1:]:
        if not tbl.rows:
            continue
        headers = [c.text.strip().lower() for c in tbl.rows[0].cells]
        h_join = " ".join(headers)

        if any(k in h_join for k in ("nombre", "entidad", "participante")):
            vals = typed["people"]
            if ptr["people"] < len(vals):
                _fill_list_table(tbl, vals[ptr["people"]], ["entidad", "nombre", "cargo"])
                ptr["people"] += 1

        elif any(k in h_join for k in ("actividad", "responsable", "estado")):
            vals = typed["commits"]
            if ptr["commits"] < len(vals):
                _fill_list_table(tbl, vals[ptr["commits"]], ["actividad", "estado", "responsable", "fecha"])
                ptr["commits"] += 1

        elif any(k in h_join for k in ("entregable", "material")) or \
                ("tipo" in h_join and "tema" not in h_join):
            vals = typed["deliverables"]
            if ptr["deliverables"] < len(vals):
                _fill_list_table(tbl, vals[ptr["deliverables"]], ["descripcion", "tipo"])
                ptr["deliverables"] += 1

        elif any(k in h_join for k in ("tema",)):
            vals = typed["topics"]
            if ptr["topics"] < len(vals):
                _fill_list_table(tbl, vals[ptr["topics"]], ["tema", "descripcion"])
                ptr["topics"] += 1

    # ── Párrafos de texto libre (OBJETIVO, DESARROLLO, etc.) ─────────────
    _fill_text_paragraphs(doc, flat)

    out = io.BytesIO()
    doc.save(out)
    return out.getvalue()


def _fill_list_table(tbl, value, col_keys: list[str]):
    """Añade filas de datos a una tabla, después de la fila de headers."""
    if not value:
        return
    items = value if isinstance(value, list) else [value]
    # Usar la primera fila de datos (si existe) como plantilla de formato
    template_row = tbl.rows[1] if len(tbl.rows) > 1 else tbl.rows[0]

    for item in items:
        new_row = copy.deepcopy(template_row._tr)
        tbl._tbl.append(new_row)
        # Acceder a la fila recién añadida
        row_obj = tbl.rows[-1]
        if isinstance(item, dict):
            for ci, key in enumerate(col_keys):
                if ci < len(row_obj.cells):
                    cell_val = item.get(key, item.get(key.replace("_", " "), ""))
                    _set_cell_text(row_obj.cells[ci], str(cell_val or ""))
        else:
            _set_cell_text(row_obj.cells[0], str(item))


def _fill_text_paragraphs(doc, flat: dict):
    """Busca párrafos en MAYÚSCULAS seguidos de vacío y rellena con el texto del acta."""
    paras = doc.paragraphs
    for idx, para in enumerate(paras):
        text = para.text.strip().rstrip(".")
        if not _is_section_heading(para):
            continue
        key = _to_key(text)
        value = flat.get(key)
        if value and idx + 1 < len(paras):
            next_para = paras[idx + 1]
            if not next_para.text.strip():
                next_para.text = str(value) if not isinstance(value, list) else "\n".join(str(v) for v in value)


def _set_cell_text(cell, text: str):
    if cell.paragraphs:
        cell.paragraphs[0].text = text
    else:
        cell.add_paragraph(text)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _to_key(text: str) -> str:
    return re.sub(r"\W+", "_", text.lower()).strip("_") or "campo"


def _infer_type(var: str, ctx: str) -> str:
    n, c = var.lower(), ctx.lower()
    if any(k in n for k in ("fecha", "date", "hora", "dia", "periodo", "plazo", "vencimiento")):
        return "date"
    if any(k in n for k in ("participante", "asistente", "integrante", "miembro", "equipo",
                             "firmante", "convocado", "nombre", "presente")):
        return "people"
    if any(k in n for k in ("lista", "items", "temas", "compromisos", "acuerdos",
                             "acciones", "tareas", "entregables", "agenda", "puntos")):
        return "list"
    if any(k in c for k in ("fecha", "date", "día", "hora")):
        return "date"
    if any(k in c for k in ("asistentes", "participantes", "presentes", "convocados")):
        return "people"
    return "text"


def _is_required(var: str, ctx: str) -> bool:
    keywords = ("fecha", "titulo", "tipo", "participante", "asistente",
                 "decision", "responsable", "acuerdo", "reunion", "objeto",
                 "lugar", "objetivo", "nombre")
    n, c = var.lower(), ctx.lower()
    return any(k in n or k in c for k in keywords)


def _build_hint(var: str, surrounding: str, ftype: str) -> str:
    name = var.replace("_", " ")
    if surrounding and surrounding.lower() != var.lower():
        return f'Buscar en la transcripción información sobre: "{surrounding}"'
    return {
        "date": f"Fecha o momento de {name}",
        "people": f"Personas o participantes de {name}",
        "list": f"Lista de elementos para {name}",
        "text": f"Información sobre {name}",
    }.get(ftype, name)

"""Estrategia de IA para extracción y generación del acta.

Principios clave:
- Prompt DINÁMICO: se arma a partir del schema de la plantilla (secciones,
  campos, etiquetas reales del documento y hints de contexto).
- Salida ESTRUCTURADA: JSON que calza exactamente con el schema.
- ANTI-ALUCINACIÓN: cada campo trae `confidence` (0-100) y `source` (cita
  textual). Si no hay evidencia → value=null, confidence=0 → se marca faltante.
- Sin API key → extractor mock semántico que usa las etiquetas del schema.
"""
from __future__ import annotations
import json
import logging
import re
from app.core.config import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()


def _clean_transcript(transcript: str) -> str:
    """Elimina artefactos de timestamp de transcripciones automáticas (Meet, Zoom, Teams).

    Formatos eliminados:
      - "0:27"  /  "1:19"  /  "33:57"  (líneas de solo HH:MM o MM:SS)
      - "0 minutos 27 segundos"  (línea de duración hablada generada por el servicio)
    """
    cleaned = []
    for line in transcript.split('\n'):
        s = line.strip()
        if re.match(r'^\d{1,2}:\d{2}(:\d{2})?$', s):
            continue
        if re.match(r'^\d+\s+minutos?\s+\d+\s+segundos?$', s, re.I):
            continue
        cleaned.append(line)
    # Colapsar más de dos líneas en blanco consecutivas
    result = re.sub(r'\n{3,}', '\n\n', '\n'.join(cleaned))
    return result.strip()


def build_prompt(template_schema: dict, transcript: str) -> tuple[str, str]:
    """Construye el prompt dinámico a partir del schema de la plantilla.
    Incluye instrucciones explícitas de columnas cuando el campo las define."""
    transcript = _clean_transcript(transcript)

    lines: list[str] = []
    for sec in template_schema.get("sections", []):
        lines.append(f'\n### Sección "{sec["title"]}" (clave: {sec["key"]})')
        for f in sec.get("fields", []):
            ftype = f["type"]
            hint = f.get("hint", "")
            cols = f.get("_columns", [])
            tbl_type = f.get("_table_type", "")

            field_spec = (
                f'  Campo: {f["key"]}\n'
                f'  Etiqueta visible: "{f.get("label", "")}"\n'
                f'  Tipo de dato: {ftype}\n'
            )

            # Si el campo tiene columnas definidas por la plantilla, generar
            # instrucciones explícitas con la estructura JSON esperada
            if cols:
                col_keys = [re.sub(r"\W+", "_", c.lower()).strip("_") for c in cols]
                example_obj = ", ".join(f'"{k}": "..."' for k in col_keys)
                field_spec += (
                    f'  COLUMNAS DE LA PLANTILLA: {", ".join(cols)}\n'
                    f'  Tipo de tabla: {tbl_type}\n'
                    f'  Instrucción: {hint}\n'
                    f'  ESTRUCTURA OBLIGATORIA de cada elemento del array:\n'
                    f'    {{{example_obj}}}\n'
                    f'  Las claves del objeto deben coincidir EXACTAMENTE con las '
                    f'columnas indicadas. Si no hay dato para una columna, pon "—".'
                )
            else:
                field_spec += (
                    f'  Instrucción: {hint if hint else "Extrae el valor correspondiente de la transcripción."}'
                )
            lines.append(field_spec)
    spec = "\n".join(lines)

    system = (
        "Eres un redactor experto en actas de reunión empresariales en español formal.\n"
        "Tu tarea es analizar una transcripción de reunión y extraer información precisa "
        "para completar ÚNICAMENTE los campos definidos en la plantilla seleccionada.\n\n"
        "REGLAS ESTRICTAS — DEBES SEGUIRLAS SIN EXCEPCIÓN:\n"
        "0. RESPETA LA PLANTILLA: el JSON de respuesta debe contener SOLO y EXACTAMENTE las\n"
        "   secciones y campos listados en la sección '=== DEFINICIÓN DE CAMPOS ==='. No añadas\n"
        "   campos extra ni omitas ninguno. La estructura del acta la define la plantilla, no tú.\n"
        "1. NUNCA copies texto crudo de la transcripción. Siempre interpreta, sintetiza y redacta.\n"
        "2. Extrae solo información que esté claramente expresada en la transcripción.\n"
        "   Si un dato no aparece con claridad, devuelve value=null y confidence=0.\n"
        "3. 'confidence' es tu certeza real (0=ninguna, 100=absoluta). Sé conservador.\n"
        "4. 'source' es una cita corta (máx 100 chars) del fragmento que respalda el valor.\n"
        "5. CAMPOS CON COLUMNAS (tienen 'COLUMNAS DE LA PLANTILLA'):\n"
        "   - El value DEBE ser un array de objetos.\n"
        "   - Cada objeto DEBE tener EXACTAMENTE las claves indicadas en 'ESTRUCTURA OBLIGATORIA'.\n"
        "   - Las claves deben coincidir exactamente (en minúsculas, sin acentos, con _ en vez de espacios).\n"
        "   - Si no hay información para una columna, usa \"—\" como valor.\n"
        "   - Tipo 'people': cada objeto representa una persona.\n"
        "   - Tipo 'list' con columnas: cada objeto representa un registro de la tabla.\n"
        "6. Tipo 'list' SIN columnas: array de strings, uno por elemento.\n"
        "7. Tipo 'date': fecha CALENDARIO (ej. '15 de junio de 2025').\n"
        "   NUNCA uses valores como '2:01' o '0:27' como fecha.\n"
        "   Tipo 'time': hora del día en formato HH:MM (ej. '09:30').\n"
        "8. Tipo 'text': REDACTA un resumen ejecutivo conciso en español formal.\n"
        "9. Para campos de 'objetivo': redacta 1-2 oraciones que describan el propósito\n"
        "   de la reunión en lenguaje formal, basándote en lo discutido.\n"
        "10. Responde EXCLUSIVAMENTE con el JSON solicitado. Sin explicaciones ni markdown."
    )

    user = f"""Analiza la transcripción y completa la plantilla de acta.

=== DEFINICIÓN DE CAMPOS ===
{spec}

=== FORMATO DE RESPUESTA (JSON estricto) ===
{{
  "<clave_seccion>": {{
    "<clave_campo>": {{
      "value": <valor sintetizado o null>,
      "confidence": <0-100>,
      "source": "<fragmento breve que lo respalda>"
    }}
  }}
}}

=== TRANSCRIPCIÓN ===
{transcript}

JSON:"""
    return system, user


def _call_groq(system: str, user: str) -> dict:
    from groq import Groq
    client = Groq(api_key=settings.GROQ_API_KEY)
    model = settings.GROQ_MODEL
    logger.info("Llamando a Groq model=%s", model)
    resp = client.chat.completions.create(
        model=model,
        max_tokens=8192,
        temperature=0.1,
        messages=[
            {"role": "system", "content": system},
            {"role": "user",   "content": user},
        ],
    )
    text = resp.choices[0].message.content or ""
    logger.info("Respuesta Groq recibida (%d chars)", len(text))
    result = _safe_json(text)
    if not result:
        logger.warning("No se pudo parsear JSON de Groq: %s", text[:300])
    return result


def _call_ollama(system: str, user: str) -> dict:
    import urllib.request
    import json as _json
    model = settings.OLLAMA_MODEL
    base  = settings.OLLAMA_BASE_URL.rstrip("/")
    url   = f"{base}/api/chat"
    logger.info("Llamando a Ollama model=%s en %s", model, base)
    payload = _json.dumps({
        "model": model,
        "stream": False,
        "options": {"temperature": 0.1},
        "messages": [
            {"role": "system",  "content": system},
            {"role": "user",    "content": user},
        ],
    }).encode()
    req = urllib.request.Request(url, data=payload,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=180) as resp:
        data = _json.loads(resp.read())
    text = data.get("message", {}).get("content", "")
    logger.info("Respuesta Ollama recibida (%d chars)", len(text))
    result = _safe_json(text)
    if not result:
        logger.warning("No se pudo parsear JSON de Ollama: %s", text[:300])
    return result


def _call_anthropic(system: str, user: str) -> dict:
    import anthropic
    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    logger.info("Llamando a Anthropic model=%s", settings.AI_MODEL)
    msg = client.messages.create(
        model=settings.AI_MODEL,
        max_tokens=8192,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    text = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")
    logger.info("Respuesta Anthropic recibida (%d chars)", len(text))
    result = _safe_json(text)
    if not result:
        logger.warning("No se pudo parsear JSON de la respuesta: %s", text[:300])
    return result


def _safe_json(text: str) -> dict:
    text = text.strip()
    text = re.sub(r"^```(?:json)?|```$", "", text, flags=re.MULTILINE).strip()
    start, depth = text.find("{"), 0
    if start == -1:
        return {}
    for i in range(start, len(text)):
        depth += (text[i] == "{") - (text[i] == "}")
        if depth == 0:
            try:
                return json.loads(text[start : i + 1])
            except json.JSONDecodeError:
                return {}
    return {}


def _is_valid_person_name(name: str) -> bool:
    name_lower = name.lower()
    exclude = {
        "proyecto", "fecha", "implementación", "implementacion", "aplicación", "aplicacion",
        "cliente", "portal", "reunión", "reunion", "acta", "organización", "organizacion",
        "comité", "comite", "gerencia", "salud", "empresarial", "asistentes", "participantes",
        "nombre", "cargo", "entidad", "presentes", "orden", "día", "dia", "tema", "desarrollo",
        "compromiso", "compromisos", "observaciones", "entregables", "evidencias", "soporte",
        "técnico", "tecnico", "líder", "lider", "operativa", "consultor", "proveedor", "coordinador",
        "junta", "directiva", "operadores", "bienvenido", "de", "vuelta", "panel"
    }
    words = name_lower.split()
    if len(words) < 2 or len(words) > 4:
        return False
    for w in words:
        if w in exclude:
            return False
    return True


def _is_valid_candidate_sentence(text: str) -> bool:
    clean = text.strip()
    if not clean or len(clean) < 10:
        return False
    lower_text = clean.lower()
    metadata_keys = {
        "cliente:", "proyecto:", "fecha:", "hora:", "elaboro:", "elaboró:",
        "modalidad:", "lugar:", "comite:", "comité:", "acta:", "participantes:",
        "asistentes:", "código:", "codigo:", "versión:", "version:", "nro:",
        "número:", "numero:", "área:", "area:", "sprint:"
    }
    for k in metadata_keys:
        if k in lower_text:
            return False
    return True


def _extract_role_near_name(name: str, text: str) -> str:
    """Busca un cargo/rol cerca del nombre del participante en el texto."""
    roles = (
        "coordinador", "líder", "lider", "gerente", "director", "jefe",
        "analista", "ingeniero", "consultor", "supervisor", "administrador",
        "especialista", "técnico", "tecnico", "asesor", "auditor",
        "desarrollador", "arquitecto", "soporte", "operador", "gestor",
        "representante", "delegado", "secretario", "presidente", "vicepresidente",
        "contador", "abogado", "médico", "enfermero", "coordinadora",
        "directora", "jefa", "analista", "asistente", "auxiliar",
        "implementación", "implementacion", "proyecto", "calidad",
    )
    # Buscar el nombre en el texto y extraer contexto alrededor
    idx = text.lower().find(name.lower())
    if idx == -1:
        return "—"
    # Tomar un rango de 120 caracteres después del nombre
    context = text[idx:idx + len(name) + 120].lower()
    for role in roles:
        if role in context:
            # Buscar la frase completa del rol
            m = re.search(r"\b(\w*" + re.escape(role) + r"\w*(?:\s+(?:de|del|en)\s+\w+)*)\b", context, re.I)
            if m:
                return m.group(1).strip().title()
    return "—"


def _extract_entity_near_name(name: str, text: str) -> str:
    """Busca una organización/entidad cerca del nombre del participante."""
    idx = text.lower().find(name.lower())
    if idx == -1:
        return "—"
    # Contexto: 100 chars antes y 100 después del nombre
    start = max(0, idx - 100)
    end = min(len(text), idx + len(name) + 100)
    context = text[start:end]
    # Buscar entidades comunes (siglas, S.A.S, S.A., etc.)
    m = re.search(r"\b([A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑ\s\.]{2,}(?:S\.?A\.?S\.?|S\.?A\.?|LTDA\.?|E\.?S\.?E\.?)?)\b", context)
    if m and len(m.group(1).strip()) > 2:
        entity = m.group(1).strip()
        # Excluir si es el mismo nombre de la persona
        if entity.lower() != name.lower():
            return entity
    return "—"


def _extract_email_near_name(name: str, text: str) -> str:
    """Busca un correo electrónico cerca del nombre."""
    idx = text.lower().find(name.lower())
    if idx == -1:
        return "—"
    context = text[max(0, idx - 50):min(len(text), idx + len(name) + 100)]
    m = re.search(r"[\w.+-]+@[\w.-]+\.\w{2,}", context)
    return m.group(0) if m else "—"


def _map_sentence_to_columns(sentence: str, col_keys: list[str], full_text: str) -> dict:
    """Distribuye el contenido de una oración entre las columnas de la plantilla
    usando heurísticas de clasificación semántica."""
    row = {ck: "—" for ck in col_keys}
    clean = sentence.strip()
    if not clean:
        return row

    # Identificar la columna principal (la primera que no sea fecha/responsable/estado)
    primary_key = col_keys[0]

    for ck in col_keys:
        # Fecha / plazo
        if any(k in ck for k in ("fecha", "plazo", "limite", "vencimiento", "entrega")):
            m = re.search(
                r"\b(\d{1,2}\s+de\s+\w+(?:\s+de\s+\d{4})?|\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\b",
                clean, re.I)
            if m:
                row[ck] = m.group(1)

        # Responsable / encargado
        elif any(k in ck for k in ("responsable", "encargado", "asignado", "nombre", "autor")):
            names = re.findall(
                r"\b([A-ZÁÉÍÓÚÑ][a-záéíóúñ]+\s[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+)\b", clean)
            valid = [n for n in names if _is_valid_person_name(n)]
            if valid:
                row[ck] = valid[0]

        # Estado / avance
        elif any(k in ck for k in ("estado", "status", "avance", "progreso")):
            status_kw = {
                "pendiente", "completado", "en proceso", "en curso", "en progreso",
                "abierto", "cerrado", "cancelado", "realizado", "hecho", "ejecutado",
                "no iniciado", "en desarrollo", "por iniciar"
            }
            lower = clean.lower()
            for kw in status_kw:
                if kw in lower:
                    row[ck] = kw.capitalize()
                    break

        # Descripción / detalle / observación (el texto completo)
        elif any(k in ck for k in ("descripcion", "detalle", "observacion", "contenido", "desarrollo")):
            row[ck] = clean[:300]

        # N° / número / ítem
        elif any(k in ck for k in ("n_", "numero", "item", "no_", "nro")):
            continue  # se rellena luego

        # Tema / actividad / compromiso / tarea (columna principal de contenido)
        elif any(k in ck for k in ("tema", "actividad", "compromiso", "tarea", "accion", "punto", "agenda")):
            row[ck] = clean[:300]

    # Si la columna principal sigue vacía, poner el texto completo
    if row.get(primary_key, "—") == "—":
        row[primary_key] = clean[:300]

    return row


def _mock_extract(template_schema: dict, transcript: str) -> dict:
    """Extractor mock semántico que opera sobre la transcripción ya limpia.
    Usa las columnas (_columns) definidas en el schema de la plantilla para
    generar objetos estructurados que coincidan con los encabezados de las tablas."""
    t = _clean_transcript(transcript)
    out: dict = {}

    for sec in template_schema.get("sections", []):
        out[sec["key"]] = {}
        for f in sec["fields"]:
            value, conf, src = None, 0, ""
            ftype = f["type"]
            ctx = (f["key"] + " " + f.get("label", "") + " " + f.get("hint", "")).lower()
            tbl_type = f.get("_table_type", "")
            columns = f.get("_columns", [])
            col_keys = [re.sub(r"\W+", "_", c.lower()).strip("_") for c in columns] if columns else []

            # ── Participantes (guiado por columnas) ──────────────────────
            if ftype == "people" or tbl_type == "participants" or any(
                    k in ctx for k in ("participante", "asistente", "integrante",
                                       "presentes", "convocado", "miembro", "equipo")):
                # Buscar pares de palabras capitalizadas (Nombre Apellido)
                raw_names = re.findall(
                    r"\b([A-ZÁÉÍÓÚÑ][a-záéíóúñ]+\s[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+(?:\s[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+)?)\b", t)
                names = [n for n in raw_names if _is_valid_person_name(n)]
                names = list(dict.fromkeys(names))[:10]
                if names:
                    if col_keys:
                        # Mapear cada nombre a las columnas de la plantilla
                        value = []
                        for name in names:
                            row = {}
                            for ck in col_keys:
                                if any(k in ck for k in ("nombre", "participante", "asistente", "integrante")):
                                    row[ck] = name
                                elif any(k in ck for k in ("cargo", "rol", "puesto", "funcion")):
                                    row[ck] = _extract_role_near_name(name, t)
                                elif any(k in ck for k in ("entidad", "empresa", "organizacion", "compania", "institucion")):
                                    row[ck] = _extract_entity_near_name(name, t)
                                elif any(k in ck for k in ("correo", "email", "e_mail")):
                                    row[ck] = _extract_email_near_name(name, t)
                                elif any(k in ck for k in ("telefono", "tel", "celular", "movil")):
                                    row[ck] = "—"
                                else:
                                    row[ck] = "—"
                            value.append(row)
                    else:
                        value = [{"nombre": n, "cargo": "—", "entidad": "—"} for n in names]
                    conf, src = 88, "Participantes detectados en la transcripción."

            # ── Compromisos / actividades (guiado por columnas) ──────────
            elif tbl_type == "commitments" or any(
                    k in ctx for k in ("comprom", "actividad", "tarea", "responsabl")):
                lines_split = re.split(r"[.;\n]", t)
                matches = []
                for line in lines_split:
                    line_clean = line.strip()
                    if len(line_clean) > 15 and any(k in line_clean.lower() for k in (
                            "comprom", "entregar", "responsable", "tarea", "actividad",
                            "validar", "confirmar", "revisar", "enviar", "realizar",
                            "coordinar", "gestionar", "verificar", "implementar")):
                        if _is_valid_candidate_sentence(line_clean):
                            matches.append(line_clean[:200])
                matches = list(dict.fromkeys(matches))[:6]
                if matches:
                    if col_keys:
                        value = []
                        for match in matches:
                            row = _map_sentence_to_columns(match, col_keys, t)
                            value.append(row)
                    else:
                        value = matches
                    conf, src = 82, "Compromisos detectados en la transcripción."

            # ── Temas / agenda (guiado por columnas) ─────────────────────
            elif tbl_type == "topics" or any(k in ctx for k in ("tema", "agenda", "punto", "abordado")):
                lines_split = re.split(r"[.;\n]", t)
                candidates = []
                for s in lines_split:
                    s_clean = s.strip()
                    if 15 < len(s_clean) < 120 and not re.match(r'^\d', s_clean):
                        if _is_valid_candidate_sentence(s_clean):
                            candidates.append(s_clean)
                candidates = list(dict.fromkeys(candidates))[:5]
                if candidates:
                    if col_keys:
                        value = []
                        for cand in candidates:
                            row = _map_sentence_to_columns(cand, col_keys, t)
                            value.append(row)
                    else:
                        value = candidates
                    conf, src = 55, "Temas extraídos de la transcripción."

            # ── Entregables (guiado por columnas) ────────────────────────
            elif tbl_type == "deliverables" or any(k in ctx for k in ("entregable", "documento", "material")):
                lines_split = re.split(r"[.;\n]", t)
                val_list = []
                for line in lines_split:
                    line_clean = line.strip()
                    if any(k in line_clean.lower() for k in ("entregable", "documento", "material", "manual", "guia")):
                        if _is_valid_candidate_sentence(line_clean):
                            val_list.append(line_clean[:150])
                if val_list:
                    if col_keys:
                        value = []
                        for item in val_list:
                            row = _map_sentence_to_columns(item, col_keys, t)
                            value.append(row)
                    else:
                        value = val_list
                    conf, src = 70, val_list[0]

            # ── Tabla genérica con columnas ──────────────────────────────
            elif tbl_type == "generic" and col_keys:
                lines_split = re.split(r"[.;\n]", t)
                candidates = []
                for s in lines_split:
                    s_clean = s.strip()
                    if 10 < len(s_clean) < 200 and not re.match(r'^\d', s_clean):
                        if _is_valid_candidate_sentence(s_clean):
                            candidates.append(s_clean)
                candidates = list(dict.fromkeys(candidates))[:5]
                if candidates:
                    value = [_map_sentence_to_columns(c, col_keys, t) for c in candidates]
                    conf, src = 50, "Datos extraídos de la transcripción."

            # ── Fecha / hora ─────────────────────────────────────────────
            elif ftype == "date" or any(k in ctx for k in ("fecha", "hora", "dia", "cuando", "plazo")):
                is_time_field = any(k in ctx for k in
                    ("inicio", "start", "final", "fin", "cierre", "termino", "término", "hora"))
                if is_time_field:
                    times = re.findall(r"\b(\d{1,2}:\d{2})\b", t, re.I)
                    if times:
                        is_end = any(k in ctx for k in ("final", "fin", "cierre", "termino", "término"))
                        val = times[-1] if is_end else times[0]
                        value, conf, src = val, 82, val
                    m = None
                else:
                    m = re.search(
                        r"\b(\d{1,2}\s+de\s+\w+(?:\s+de\s+\d{4})?|\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\b",
                        t, re.I)
                if m:
                    value, conf, src = m.group(1), 82, m.group(0)

            # ── Decisiones / acuerdos ────────────────────────────────────
            elif any(k in ctx for k in ("decis", "acuerd", "aprob", "resoluci")):
                m = re.search(r"([^.]*(?:aprob\w+|decidi\w+|acord\w+|resolv\w+)[^.]*\.)", t, re.I)
                if m:
                    value, conf, src = m.group(1).strip(), 87, m.group(1).strip()[:150]

            # ── Riesgos / bloqueos ───────────────────────────────────────
            elif any(k in ctx for k in ("riesgo", "alert", "problem", "bloqueo")):
                m = re.search(r"([^.]*(?:riesgo|alerta|problema|bloqueo)[^.]*\.)", t, re.I)
                if m:
                    value, conf, src = m.group(1).strip(), 74, m.group(1).strip()[:150]

            # ── Título / tipo de reunión ──────────────────────────────────
            elif any(k in ctx for k in ("titulo", "tipo", "nombre", "reunion", "comite", "objeto")):
                m = re.search(
                    r"\b((?:reuni[oó]n|comit[eé]|sesi[oó]n|taller|capacitaci[oó]n)"
                    r"(?:\s+de\s+\w+)?)",
                    t, re.I)
                if m:
                    value, conf, src = m.group(1).strip().rstrip(",."), 78, m.group(1).strip()[:80]

            # ── Lugar / modalidad ────────────────────────────────────────
            elif any(k in ctx for k in ("lugar", "sede", "sala", "modalidad", "ubicacion")):
                m = re.search(r"([^.]*(?:sala|sede|lugar|virtual|zoom|meet|teams|presencial)[^.]*\.?)", t, re.I)
                if m:
                    value, conf, src = m.group(1).strip(), 70, m.group(1).strip()[:150]

            # ── Objetivo / alcance ───────────────────────────────────────
            elif any(k in ctx for k in ("objetivo", "proposit", "finalidad", "meta", "alcance")):
                sentences = [s.strip() for s in re.split(r"[.!?]", t)
                             if 20 < len(s.strip()) < 300 and not re.match(r'^\d', s.strip())]
                obj_sent = None
                for sent in sentences:
                    sl = sent.lower()
                    if any(k in sl for k in ("objetivo", "finalidad", "prop", "revisar",
                                             "evaluar", "informar", "verificar", "socializar")):
                        obj_sent = sent[:250]
                        break
                if not obj_sent:
                    for sent in sentences:
                        if re.search(r"\bpara\s+\w", sent, re.I):
                            obj_sent = sent[:250]
                            break
                if obj_sent:
                    value, conf, src = obj_sent, 65, obj_sent[:120]

            # ── Observaciones / desarrollo ───────────────────────────────
            elif any(k in ctx for k in ("observaci", "desarrollo", "resumen", "detalle")):
                long_sents = [s.strip() for s in re.split(r"[.!?]", t)
                              if 30 < len(s.strip()) < 250 and not re.match(r'^\d', s.strip())]
                if long_sents:
                    value, conf, src = " ".join(long_sents[:2]), 50, long_sents[0][:120]

            # ── Genérico ─────────────────────────────────────────────────
            else:
                key_words = [w for w in re.split(r"[\s_]+", f["key"].lower()) if len(w) > 3]
                for word in key_words[:3]:
                    m = re.search(r"([^.]*\b" + re.escape(word) + r"\b[^.]*\.)", t, re.I)
                    if m:
                        value, conf, src = m.group(1).strip(), 50, m.group(1).strip()[:150]
                        break

            out[sec["key"]][f["key"]] = {"value": value, "confidence": conf, "source": src}
    return out


MIN_CONFIDENCE = 50


def validate_and_score(template_schema: dict, raw: dict) -> tuple[dict, list, int]:
    data, missing, confs = {}, [], []
    for sec in template_schema.get("sections", []):
        data[sec["key"]] = {"title": sec["title"], "fields": {}}
        for f in sec["fields"]:
            cell = (raw.get(sec["key"], {}) or {}).get(f["key"], {}) or {}
            value = cell.get("value")
            conf = int(cell.get("confidence", 0) or 0)
            src = cell.get("source", "") or ""

            # Normalizar claves de objetos en arrays para coincidir con _columns
            columns = f.get("_columns", [])
            if columns and isinstance(value, list):
                col_keys = [re.sub(r"\W+", "_", c.lower()).strip("_") for c in columns]
                value = [_normalize_row_keys(item, col_keys) for item in value]

            ok = value not in (None, "", []) and conf >= MIN_CONFIDENCE
            field_data = {
                "label": f["label"], "type": f["type"], "value": value,
                "confidence": conf, "source": src, "required": f.get("required", False),
            }
            for k, val in f.items():
                if k.startswith("_"):
                    field_data[k] = val
            data[sec["key"]]["fields"][f["key"]] = field_data
            if f.get("required") and not ok:
                missing.append({"section": sec["key"], "field": f["key"], "label": f["label"]})
            if value not in (None, "", []):
                confs.append(conf)
    avg = round(sum(confs) / len(confs)) if confs else 0
    return data, missing, avg


def _normalize_row_keys(item, col_keys: list[str]) -> dict:
    """Normaliza las claves de un objeto para que coincidan con las columnas de la plantilla."""
    if not isinstance(item, dict):
        # Si es un string, ponerlo en la primera columna
        return {ck: (str(item) if i == 0 else "—") for i, ck in enumerate(col_keys)}

    item_norm = {re.sub(r"\W+", "_", k.lower()).strip("_"): v for k, v in item.items()}
    result = {}

    # Aliases comunes para normalización
    aliases = {
        "entidad": ("organizacion", "empresa", "compania", "institution", "org"),
        "nombre": ("participante", "persona", "asistente", "integrante", "name"),
        "cargo": ("rol", "puesto", "posicion", "funcion", "role", "position"),
        "actividad": ("tarea", "compromiso", "accion", "item", "task", "activity"),
        "responsable": ("encargado", "asignado", "responsible", "owner"),
        "estado": ("status", "avance", "progreso", "state"),
        "descripcion": ("detalle", "contenido", "tema", "observacion", "description"),
        "fecha": ("date", "plazo", "limite", "deadline"),
    }

    for ck in col_keys:
        if ck in item_norm:
            result[ck] = item_norm[ck]
            continue
        # Buscar por alias
        found = False
        for canonical, syns in aliases.items():
            group = {canonical} | set(syns)
            if ck in group:
                for alias in group:
                    if alias in item_norm:
                        result[ck] = item_norm[alias]
                        found = True
                        break
            if found:
                break
        if not found:
            # Buscar por substring
            for ik, iv in item_norm.items():
                if ik in ck or ck in ik:
                    result[ck] = iv
                    found = True
                    break
        if not found:
            result[ck] = "—"
    return result


def generate_acta(template_schema: dict, transcript: str) -> tuple[dict, list, int]:
    """Orquesta: prompt dinámico → LLM (anthropic|groq|ollama|mock) → validación → scoring."""
    provider = (settings.AI_PROVIDER or "mock").lower()
    system, user = build_prompt(template_schema, transcript)
    raw: dict = {}
    try:
        if provider == "anthropic":
            if not settings.ANTHROPIC_API_KEY:
                raise ValueError("ANTHROPIC_API_KEY no configurada")
            raw = _call_anthropic(system, user)
        elif provider == "groq":
            if not settings.GROQ_API_KEY:
                raise ValueError("GROQ_API_KEY no configurada")
            raw = _call_groq(system, user)
        elif provider == "ollama":
            raw = _call_ollama(system, user)
        else:
            logger.info("AI_PROVIDER=%s — usando extractor mock", provider)
            raw = _mock_extract(template_schema, transcript)
    except Exception as e:
        logger.error("Fallo proveedor '%s': %s — usando mock como fallback", provider, e)
        raw = _mock_extract(template_schema, transcript)
    return validate_and_score(template_schema, raw)

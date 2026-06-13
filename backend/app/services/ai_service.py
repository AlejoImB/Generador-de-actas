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
import re
from app.core.config import get_settings

settings = get_settings()


def build_prompt(template_schema: dict, transcript: str) -> tuple[str, str]:
    """Construye el prompt dinámico a partir del schema de la plantilla."""
    tpl_type = template_schema.get("_tpl_type", "jinja2")
    lines: list[str] = []
    for sec in template_schema.get("sections", []):
        lines.append(f'\n### Sección: "{sec["title"]}"')
        for f in sec.get("fields", []):
            req = "OBLIGATORIO" if f.get("required") else "opcional"
            ftype = f["type"]
            hint = f.get("hint", "")
            # Para campos de tabla estructurada, el hint ya incluye el formato esperado
            lines.append(
                f'  • {sec["key"]}.{f["key"]}  [{req}]  tipo={ftype}\n'
                f'    Etiqueta: "{f.get("label", "")}"\n'
                f'    Instrucción: {hint}'
            )
    spec = "\n".join(lines)

    system = (
        "Eres un experto redactor de actas de reunión empresariales. "
        "Tu tarea es leer una transcripción y extraer información para completar una plantilla de acta. "
        "REGLAS:\n"
        "1. Extrae ÚNICAMENTE lo que aparece en la transcripción. NUNCA inventes datos.\n"
        "2. Si no hay información para un campo, devuelve value=null y confidence=0.\n"
        "3. Cada campo devuelve: 'value', 'confidence' (0-100) y 'source' (cita breve).\n"
        "4. Campos tipo 'people': devuelve array de objetos JSON con los atributos solicitados.\n"
        "5. Campos tipo 'list': devuelve array de strings o array de objetos según las instrucciones.\n"
        "6. Campos tipo 'date': usa el formato exacto del texto.\n"
        "7. Responde SOLO con JSON válido, sin texto adicional."
    )

    user = f"""Analiza la transcripción y completa TODOS los campos de la plantilla.

CAMPOS A COMPLETAR:
{spec}

FORMATO DE RESPUESTA (JSON exacto):
{{
  "<clave_seccion>": {{
    "<clave_campo>": {{"value": <valor extraído o null>, "confidence": <0-100>, "source": "<cita>"}}
  }}
}}

TRANSCRIPCIÓN:
\"\"\"
{transcript}
\"\"\"
"""
    return system, user


def _call_anthropic(system: str, user: str) -> dict:
    import anthropic
    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    msg = client.messages.create(
        model=settings.AI_MODEL,
        max_tokens=4096,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    text = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")
    return _safe_json(text)


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


def _mock_extract(template_schema: dict, transcript: str) -> dict:
    """Extractor mock semántico: usa etiqueta, hint y tipo del campo para
    encontrar información relevante en la transcripción."""
    t = transcript
    out: dict = {}

    for sec in template_schema.get("sections", []):
        out[sec["key"]] = {}
        for f in sec["fields"]:
            value, conf, src = None, 0, ""
            ftype = f["type"]
            ctx = (f["key"] + " " + f.get("label", "") + " " + f.get("hint", "")).lower()
            tbl_type = f.get("_table_type", "")

            # ── Participantes ────────────────────────────────────────────
            if ftype == "people" or tbl_type == "participants" or any(
                    k in ctx for k in ("participante", "asistente", "integrante",
                                       "presentes", "convocado", "miembro", "equipo")):
                names = re.findall(
                    r"\b([A-ZÁÉÍÓÚÑ][a-záéíóúñ]+(?:\s[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+)+)\b", t)
                names = list(dict.fromkeys(names))[:10]
                if names:
                    # Para plantillas estructurales devolver objetos {nombre, cargo, entidad}
                    if tbl_type == "participants":
                        value = [{"nombre": n, "cargo": "", "entidad": ""} for n in names]
                    else:
                        value = names
                    conf, src = 88, "Participantes detectados en la transcripción."

            # ── Compromisos / actividades ────────────────────────────────
            elif tbl_type == "commitments" or any(
                    k in ctx for k in ("comprom", "actividad", "tarea", "responsabl")):
                matches = re.findall(
                    r"([^.]*(?:comprom\w+|entregar\w*|responsable|tarea|actividad)[^.]*\.)", t, re.I)
                if matches:
                    value = [m.strip()[:200] for m in matches[:6]]
                    conf, src = 82, "Compromisos detectados en la transcripción."
                else:
                    m = re.search(r"([^.]*(?:comprom\w+|entregar\w*|responsable)[^.]*\.)", t, re.I)
                    if m:
                        value, conf, src = m.group(1).strip(), 80, m.group(1).strip()[:150]

            # ── Temas / agenda ───────────────────────────────────────────
            elif tbl_type == "topics" or any(k in ctx for k in ("tema", "agenda", "punto", "abordado")):
                # Buscar oraciones que parezcan temas
                sentences = [s.strip() for s in re.split(r"[.;]", t) if 10 < len(s.strip()) < 200]
                if sentences:
                    value, conf, src = sentences[:5], 65, "Temas extraídos de la transcripción."

            # ── Entregables ──────────────────────────────────────────────
            elif tbl_type == "deliverables" or any(k in ctx for k in ("entregable", "documento", "material")):
                m = re.search(r"([^.]*(?:entregable|documento|material|manual|guia)\w*[^.]*\.)", t, re.I)
                if m:
                    value, conf, src = [m.group(1).strip()], 70, m.group(1).strip()[:150]

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
                sentences = [s.strip() for s in re.split(r"[.!?]", t) if len(s.strip()) > 20]
                obj_sent = None
                for sent in sentences:
                    sl = sent.lower()
                    if any(k in sl for k in ("objetivo", "finalidad", "prop", "revisar",
                                             "evaluar", "informar", "verificar", "socializar")):
                        obj_sent = sent
                        break
                if not obj_sent:
                    for sent in sentences:
                        if re.search(r"\bpara\s+\w", sent, re.I):
                            obj_sent = sent
                            break
                if obj_sent:
                    value, conf, src = obj_sent, 72, obj_sent[:150]
                elif sentences:
                    value, conf, src = sentences[0], 40, sentences[0][:150]

            # ── Observaciones / desarrollo ───────────────────────────────
            elif any(k in ctx for k in ("observaci", "desarrollo", "resumen", "detalle")):
                long_sents = [s.strip() for s in re.split(r"[.!?]", t) if len(s.strip()) > 30]
                if long_sents:
                    value, conf, src = " ".join(long_sents[:3]), 55, long_sents[0][:150]

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
            ok = value not in (None, "", []) and conf >= MIN_CONFIDENCE
            data[sec["key"]]["fields"][f["key"]] = {
                "label": f["label"], "type": f["type"], "value": value,
                "confidence": conf, "source": src, "required": f.get("required", False),
            }
            if f.get("required") and not ok:
                missing.append({"section": sec["key"], "field": f["key"], "label": f["label"]})
            if value not in (None, "", []):
                confs.append(conf)
    avg = round(sum(confs) / len(confs)) if confs else 0
    return data, missing, avg


def generate_acta(template_schema: dict, transcript: str) -> tuple[dict, list, int]:
    """Orquesta: prompt dinámico → LLM (o mock) → validación → scoring."""
    if settings.AI_PROVIDER == "anthropic" and settings.ANTHROPIC_API_KEY:
        system, user = build_prompt(template_schema, transcript)
        try:
            raw = _call_anthropic(system, user)
        except Exception:
            raw = _mock_extract(template_schema, transcript)
    else:
        raw = _mock_extract(template_schema, transcript)
    return validate_and_score(template_schema, raw)

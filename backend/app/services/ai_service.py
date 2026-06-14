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
    """Construye el prompt dinámico a partir del schema de la plantilla."""
    transcript = _clean_transcript(transcript)

    lines: list[str] = []
    for sec in template_schema.get("sections", []):
        lines.append(f'\n### Sección "{sec["title"]}" (clave: {sec["key"]})')
        for f in sec.get("fields", []):
            ftype = f["type"]
            hint = f.get("hint", "")
            lines.append(
                f'  Campo: {f["key"]}\n'
                f'  Etiqueta visible: "{f.get("label", "")}"\n'
                f'  Tipo de dato: {ftype}\n'
                f'  Instrucción: {hint if hint else "Extrae el valor correspondiente de la transcripción."}'
            )
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
        "5. Tipo 'people': array de objetos {\"nombre\": \"...\", \"cargo\": \"...\", \"entidad\": \"...\"}.\n"
        "   Incluye solo personas claramente nombradas como participantes de la reunión.\n"
        "6. Tipo 'list': array de strings. Cada ítem es un elemento independiente y conciso.\n"
        "   Para agenda o temas: extrae los puntos tratados, NO oraciones del diálogo.\n"
        "   Para compromisos/actividades: cada ítem debe tener estructura clara.\n"
        "7. Tipo 'date': fecha CALENDARIO de la reunión (ej. '15 de junio de 2025').\n"
        "   NUNCA uses valores como '2:01' o '0:27' como fecha — son contadores de tiempo de la\n"
        "   transcripción, no fechas. Si la fecha no aparece claramente en el texto, devuelve null.\n"
        "   Tipo 'time': hora del día en formato HH:MM (ej. '09:30'). No uses contadores de\n"
        "   transcripción como hora salvo que el hablante la mencione explícitamente.\n"
        "8. Tipo 'text': REDACTA un resumen ejecutivo conciso en español formal.\n"
        "   NO copies oraciones literales. Sintetiza y profesionaliza el lenguaje.\n"
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


def _mock_extract(template_schema: dict, transcript: str) -> dict:
    """Extractor mock semántico que opera sobre la transcripción ya limpia."""
    t = _clean_transcript(transcript)
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
                # Filtrar candidatos: ni muy cortos ni texto crudo de diálogo
                candidates = [
                    s.strip() for s in re.split(r"[.;]", t)
                    if 15 < len(s.strip()) < 120
                    and not re.match(r'^\d', s.strip())
                ]
                if candidates:
                    value, conf, src = candidates[:5], 55, "Temas extraídos de la transcripción."

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
                # Solo oraciones que contengan palabras clave de propósito (limitar a 200 chars)
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

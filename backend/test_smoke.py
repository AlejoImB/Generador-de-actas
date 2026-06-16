import io
from fastapi.testclient import TestClient
from app.main import app
c = TestClient(app)

assert c.get("/api/health").json()["status"] == "ok"

r = c.post("/api/auth/login", data={"username": "ana.torres@empresa.com", "password": "Demo1234"})
assert r.status_code == 200, r.text
H = {"Authorization": "Bearer " + r.json()["access_token"]}
print("LOGIN ok ·", r.json()["user"]["name"])

assert c.post("/api/auth/login", data={"username": "x@x.com", "password": "no"}).status_code == 401
print("LOGIN invalido rechazado ok")

tpls = c.get("/api/templates", headers=H).json()
print("PLANTILLAS:", [t["name"] for t in tpls])

txt = b"Reunion el 5 de mayo de 2026. Asisten Pedro Gomez y Laura Diaz. Se decidio aprobar el proceso. Pedro se compromete a documentarlo el 10 de mayo."
r = c.post("/api/transcripts/upload", headers=H,
           files={"file": ("acta.txt", io.BytesIO(txt), "text/plain")}, data={"title": "Prueba TXT"})
assert r.status_code == 200, r.text
tr = r.json()
print("UPLOAD TXT ok ·", tr["word_count"], "palabras · v", tr["current_version"])

r = c.put(f"/api/transcripts/{tr['id']}", headers=H, json={"content": txt.decode() + " Nota adicional."})
assert r.json()["current_version"] == 2
vers = c.get(f"/api/transcripts/{tr['id']}/versions", headers=H).json()
print("HISTORIAL VERSIONES:", len(vers), "versiones")

acta = c.post("/api/actas/generate", headers=H,
              json={"transcript_id": tr["id"], "template_id": tpls[0]["id"]}).json()
print("GENERAR ok · confianza", acta["avg_confidence"], "% · faltantes:",
      [m["label"] for m in acta["missing_fields"]])

if acta["missing_fields"]:
    print("Campos faltantes detectados. Completando uno...")
    m = acta["missing_fields"][0]
    c.patch(f"/api/actas/{acta['id']}/field", headers=H,
            json={"section_key": m["section"], "field_key": m["field"], "value": "valor validado"})

assert c.post(f"/api/actas/{acta['id']}/approve", headers=H).status_code == 200
print("APROBAR ok tras validar")

nueva = {"name": "Acta Junta Directiva", "icon": "*", "description": "Plantilla creada por API",
         "schema": {"sections": [{"key": "id", "title": "Datos", "fields": [
             {"key": "tema", "label": "Tema", "type": "text", "required": True, "hint": "tema"}]}]}}
nt = c.post("/api/templates", headers=H, json=nueva).json()
print("PLANTILLA NUEVA (sin codigo):", nt["name"], "· total:",
      len(c.get("/api/templates", headers=H).json()))

print("\n*** TODOS LOS TESTS PASARON ***")

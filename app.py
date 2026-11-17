# -*- coding: utf-8 -*-
"""Los Lakers Barbershop - versión web (Flask + SQLite). Mismas reglas del prototipo de escritorio."""
import datetime as dt, json, os, secrets, sqlite3, time, hmac
from flask import Flask, jsonify, request, session

app = Flask(__name__, static_folder="static", static_url_path="/static")
app.secret_key = os.environ.get("SECRET_KEY") or secrets.token_hex(16)
app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax")
DB = os.environ.get("DB_PATH", os.path.join(os.path.dirname(os.path.abspath(__file__)), "lakers.db"))
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "lakers2026")   # cámbiala en Render
TZ = dt.timezone(dt.timedelta(hours=-5))                          # hora de Colombia

# ---------------- Reglas del negocio (idénticas al prototipo) ----------------
PRECIO_PLAN, PORC_BARBERO, INSUMOS, COSTO_PREMIUM = 80000, 0.50, 2000, 0.62
UMBRAL_ABONO, ABONO, PASO, DIAS_ADELANTE = 30000, 5000, 15, 7
BARBEROS = ["Yeison Doria", "Brayan Pastrana", "Dubán Hoyos"]
TURNOS = {BARBEROS[0]: (480, 960), BARBEROS[1]: (840, 1320), BARBEROS[2]: (660, 1140)}
DESCANSO = {BARBEROS[0]: 0, BARBEROS[1]: 1, BARBEROS[2]: 2}
ESPECIALES = {(BARBEROS[2], 0): (480, 960), (BARBEROS[2], 1): (840, 1320)}
SERVICIOS = [(i, c, n, p, d) for i, c, n, p, d in [
    ("S01", "Cortes", "Corte Tijera", 20000, 50), ("S02", "Cortes", "Corte Kids con Tijera", 20000, 40),
    ("S03", "Cortes", "Basic Men", 20000, 40), ("S04", "Cortes", "Basic Kids (0 - 8 años)", 20000, 40),
    ("S05", "Cortes", "Cerquillos", 10000, 20), ("S06", "Barba", "Tinte Barba", 25000, 20),
    ("S07", "Barba", "Barba", 15000, 30), ("S08", "Combos", "Basic Men + Barba", 30000, 60),
    ("S09", "Combos", "Cera Nariz + Oído", 8000, 15), ("S10", "Otros", "Tinte Cabello", 35000, 20),
    ("S11", "Otros", "Cejas Semi", 15000, 30), ("S12", "Otros", "Cejas Básico", 8000, 10),
    ("S13", "Otros", "Cera Nariz", 5000, 15), ("S14", "Otros", "Cera Oídos", 5000, 15),
    ("S15", "Planes", "Plan Lakers 5 cortes", PRECIO_PLAN, 40)]]
SERV = {s[0]: s for s in SERVICIOS}
_P = [("P01", "Crema de peinar 250 ml", "Cuidado y estilo", 25000, 120, "consumible"),
      ("P02", "Cera para cabello 100 g", "Cuidado y estilo", 22000, 120, "consumible"),
      ("P03", "Polvo texturizador", "Cuidado y estilo", 30000, 80, "consumible"),
      ("P04", "Loción refrescante con alcohol 500 ml", "Cuidado y estilo", 18000, 100, "consumible"),
      ("P05", "Minoxidil 5% barba", "Cuidado y estilo", 45000, 60, "consumible"),
      ("P06", "Aceite para barba 30 ml", "Cuidado y estilo", 26000, 80, "consumible"),
      ("H01", "Guantes de nitrilo (caja x100)", "Higiene y limpieza", 30000, 150, "consumible"),
      ("H02", "Tiras de cuello (paquete x100)", "Higiene y limpieza", 14000, 200, "consumible"),
      ("H03", "Desinfectante de herramientas 500 ml", "Higiene y limpieza", 38000, 90, "consumible"),
      ("H04", "Alcohol antiséptico 700 ml", "Higiene y limpieza", 9000, 200, "consumible"),
      ("H05", "Toallas desechables (paquete x50)", "Higiene y limpieza", 22000, 150, "consumible"),
      ("E01", "Máquina clipper profesional", "Equipos", 380000, 25, "equipo"),
      ("E02", "Máquina shaver (afeitadora)", "Equipos", 260000, 25, "equipo"),
      ("E03", "Trimmer de detalle", "Equipos", 180000, 30, "equipo"),
      ("E04", "Secador de cabello profesional", "Equipos", 150000, 20, "equipo"),
      ("A01", "Capa de corte profesional", "Accesorios", 40000, 60, "equipo"),
      ("A02", "Navaja shavette + 100 cuchillas", "Accesorios", 32000, 70, "consumible"),
      ("M01", "Silla de barbería hidráulica", "Mobiliario", 1350000, 10, "mobiliario")]
PRODUCTOS = [dict(id=a, nombre=b, cat=c, precio=d, stock=e, tipo=f) for a, b, c, d, e, f in _P]
PROD = {p["id"]: p for p in PRODUCTOS}
PREMIUM = {p["id"] for p in PRODUCTOS if p["cat"] == "Cuidado y estilo"}
ESCALAS = {"consumible": [(12, .15), (6, .10)], "equipo": [(5, .12), (3, .08)], "mobiliario": [(4, .12), (2, .07)]}
COMBOS = [dict(nombre="Combo Barbero Inicial (clipper + shaver + cera + crema)", items=["E01", "E02", "P02", "P01"], pct=.10),
          dict(nombre="Combo Higiene Total (guantes + tiras + desinfectante + alcohol)", items=["H01", "H02", "H03", "H04"], pct=.08),
          dict(nombre="Combo Estilo (crema + cera + polvo + loción)", items=["P01", "P02", "P03", "P04"], pct=.07)]
ESC_PEDIDO = [(3_000_000, .08), (1_000_000, .05)]

# ---------------- Base de datos ----------------
def db():
    c = sqlite3.connect(DB); c.row_factory = sqlite3.Row; return c

def init():
    with db() as c:
        c.execute("CREATE TABLE IF NOT EXISTS citas(id INTEGER PRIMARY KEY AUTOINCREMENT, d TEXT)")
        c.execute("CREATE TABLE IF NOT EXISTS ventas(id INTEGER PRIMARY KEY AUTOINCREMENT, d TEXT)")
        c.execute("CREATE TABLE IF NOT EXISTS stock(id TEXT PRIMARY KEY, q INTEGER)")
        for p in PRODUCTOS:
            c.execute("INSERT OR IGNORE INTO stock VALUES(?,?)", (p["id"], p["stock"]))
init()

def rows(t):
    with db() as c:
        return [dict(json.loads(r["d"]), id=r["id"]) for r in c.execute(f"SELECT * FROM {t} ORDER BY id")]

def now(): return dt.datetime.now(TZ)

# ---------------- Turnos y disponibilidad ----------------
def turno(b, f):
    if f.weekday() == DESCANSO.get(b): return None
    return ESPECIALES.get((b, f.weekday()), TURNOS[b])

def duracion(ids): return sum(SERV[i][4] for i in ids)

def libres(f, ids, barbero):
    t, dur = turno(barbero, f), duracion(ids)
    if not t: return []
    ocupadas = [(c["ini"], c["ini"] + c["dur"]) for c in rows("citas")
                if c["fecha"] == f.isoformat() and c["barbero"] == barbero and c["estado"] in ("pendiente", "confirmada")]
    n, out = now(), []
    for ini in range(t[0], t[1] - dur + 1, PASO):
        if f == n.date() and ini <= n.hour * 60 + n.minute: continue
        if any(ini < b and a < ini + dur for a, b in ocupadas): continue
        out.append(ini)
    return out

def hhmm(m): return f"{m // 60:02d}:{m % 60:02d}"

def fecha_ok(s):
    try: f = dt.date.fromisoformat(s)
    except Exception: return None
    return f if 0 <= (f - now().date()).days <= DIAS_ADELANTE else None

# ---------------- Precios de tienda ----------------
def calcular(car):
    lineas, sub, dvol = [], 0, 0
    for pid, q in car.items():
        p = PROD[pid]; pct = next((x for m, x in ESCALAS[p["tipo"]] if q >= m), 0.0)
        bruto = p["precio"] * q; d = round(bruto * pct)
        lineas.append(dict(id=pid, nombre=p["nombre"], cant=q, unit=p["precio"], pct=pct, neto=bruto - d))
        sub += bruto; dvol += d
    combos, dcombo = [], 0
    for c in COMBOS:
        if all(i in car for i in c["items"]):
            j = min(car[i] for i in c["items"]); d = round(sum(PROD[i]["precio"] for i in c["items"]) * j * c["pct"])
            combos.append(dict(nombre=c["nombre"].split(" (")[0], juegos=j, desc=d)); dcombo += d
    tras = sub - dvol - dcombo
    pp = next((x for m, x in ESC_PEDIDO if tras >= m), 0.0); dp = round(tras * pp)
    return dict(lineas=lineas, subtotal=sub, desc_vol=dvol, combos=combos, desc_combo=dcombo,
                pct_pedido=pp, desc_pedido=dp, total=tras - dp)

def carrito_ok(raw):
    try: car = {k: int(v) for k, v in (raw or {}).items() if int(v) > 0}
    except Exception: return None
    return car if car and all(k in PROD and v <= 999 for k, v in car.items()) else None

# ---------------- API pública ----------------
@app.get("/")
def home(): return app.send_static_file("index.html")

@app.get("/api/config")
def config():
    return jsonify(servicios=[dict(id=a, cat=b, nombre=c, precio=d, dur=e) for a, b, c, d, e in SERVICIOS],
                   barberos=BARBEROS, productos=PRODUCTOS, combos=COMBOS, escalas=ESCALAS,
                   esc_pedido=ESC_PEDIDO, umbral_abono=UMBRAL_ABONO, abono=ABONO, dias=DIAS_ADELANTE,
                   hoy=now().date().isoformat())

@app.get("/api/disponibilidad")
def disponibilidad():
    f = fecha_ok(request.args.get("fecha", "")); ids = [i for i in request.args.get("servicios", "").split(",") if i in SERV]
    if not f or not ids: return jsonify(error="Datos inválidos"), 400
    return jsonify({b: [hhmm(m) for m in libres(f, ids, b)] for b in BARBEROS})

@app.post("/api/cotizar")
def cotizar():
    car = carrito_ok((request.json or {}).get("items"))
    return jsonify(calcular(car)) if car else (jsonify(error="Carrito vacío"), 400)

@app.post("/api/citas")
def crear_cita():
    d = request.json or {}; ids = [i for i in d.get("servicios", []) if i in SERV]
    f, b, nombre, tel = fecha_ok(d.get("fecha", "")), d.get("barbero"), str(d.get("nombre", "")).strip()[:60], str(d.get("telefono", ""))
    if not (ids and f and b in BARBEROS and nombre and tel.isdigit() and len(tel) == 10):
        return jsonify(error="Revisa tus datos: nombre y WhatsApp de 10 dígitos."), 400
    try: h, m = map(int, d["hora"].split(":")); ini = h * 60 + m
    except Exception: return jsonify(error="Hora inválida"), 400
    if ini not in libres(f, ids, b): return jsonify(error="Esa hora ya no está disponible. Elige otra."), 409
    total = sum(SERV[i][3] for i in ids)
    cita = dict(nombre=nombre, telefono=tel, correo=str(d.get("correo", ""))[:80], servicios=ids, barbero=b,
                fecha=f.isoformat(), ini=ini, dur=duracion(ids), total=total, estado="pendiente",
                abono=ABONO if total > UMBRAL_ABONO else 0, creada=now().isoformat(timespec="minutes"))
    with db() as c: cur = c.execute("INSERT INTO citas(d) VALUES(?)", (json.dumps(cita),))
    return jsonify(ok=True, id=cur.lastrowid, total=total, abono=cita["abono"], hora=hhmm(ini))

@app.post("/api/pedidos")
def crear_pedido():
    d = request.json or {}; car = carrito_ok(d.get("items")); comp = str(d.get("comprador", "")).strip()[:80]
    if not car or not comp: return jsonify(error="Escribe el nombre de la barbería y agrega productos."), 400
    with db() as c:
        for pid, q in car.items():
            if c.execute("SELECT q FROM stock WHERE id=?", (pid,)).fetchone()["q"] < q:
                return jsonify(error=f"Stock insuficiente de {PROD[pid]['nombre']}"), 409
        for pid, q in car.items(): c.execute("UPDATE stock SET q=q-? WHERE id=?", (q, pid))
        r = calcular(car)
        c.execute("INSERT INTO ventas(d) VALUES(?)", (json.dumps(dict(fecha=now().isoformat(timespec="minutes"),
                  comprador=comp, total=r["total"], items=car, lineas=r["lineas"])),))
    return jsonify(ok=True, total=r["total"])

# ---------------- Admin (solo con sesión) ----------------
def admin_only(f):
    def w(*a, **k):
        if not session.get("admin"): return jsonify(error="No autorizado"), 401
        return f(*a, **k)
    w.__name__ = f.__name__; return w

@app.post("/api/admin/login")
def login():
    if hmac.compare_digest(str((request.json or {}).get("password", "")), ADMIN_PASSWORD):
        session["admin"] = True; return jsonify(ok=True)
    time.sleep(.8); return jsonify(error="Contraseña incorrecta"), 401

@app.post("/api/admin/logout")
def logout(): session.clear(); return jsonify(ok=True)

@app.get("/api/admin/sesion")
def sesion(): return jsonify(admin=bool(session.get("admin")))

def margen_cita(c):
    if c["estado"] == "cancelada": return 0, 0, 0, 0
    if c["estado"] == "no_asistio": return c["abono"], 0, 0, c["abono"]
    n = sum(5 if i == "S15" else 1 for i in c["servicios"])
    com, ins = round(c["total"] * PORC_BARBERO), INSUMOS * n
    return c["total"], com, ins, c["total"] - com - ins

@app.get("/api/admin/resumen")
@admin_only
def resumen():
    per, hoy = request.args.get("periodo", "mes"), now().date()
    ini = {"dia": hoy, "semana": hoy - dt.timedelta(days=hoy.weekday()), "mes": hoy.replace(day=1)}.get(per, dt.date(2000, 1, 1))
    cs = [c for c in rows("citas") if dt.date.fromisoformat(c["fecha"]) >= ini]
    vs = [v for v in rows("ventas") if dt.date.fromisoformat(v["fecha"][:10]) >= ini]
    ing = com = ins = mar = 0; por_b = {b: 0 for b in BARBEROS}; por_dia = {}
    for c in cs:
        a, b_, i_, m = margen_cita(c); ing += a; com += b_; ins += i_; mar += m
        por_b[c["barbero"]] += a; por_dia[c["fecha"]] = por_dia.get(c["fecha"], 0) + a
    prem = sum(l["neto"] for v in vs for l in v["lineas"] if l["id"] in PREMIUM)
    for c in cs: c["servicios_txt"] = ", ".join(SERV[i][2] for i in c["servicios"]); c["hora"] = hhmm(c["ini"])
    return jsonify(ingresos=ing, comision=com, insumos=ins, margen_servicios=mar, citas=len(cs),
                   premium_ingreso=prem, premium_margen=round(prem * (1 - COSTO_PREMIUM)),
                   tienda_total=sum(v["total"] for v in vs), por_barbero=por_b,
                   por_dia=dict(sorted(por_dia.items())[-14:]), ultimas_citas=cs[::-1][:40],
                   ultimas_ventas=[dict(v, lineas=None) for v in vs[::-1][:15]])

@app.post("/api/admin/cita/<int:cid>")
@admin_only
def estado_cita(cid):
    e = (request.json or {}).get("estado")
    if e not in ("pendiente", "confirmada", "cancelada", "no_asistio"): return jsonify(error="Estado inválido"), 400
    with db() as c:
        r = c.execute("SELECT d FROM citas WHERE id=?", (cid,)).fetchone()
        if not r: return jsonify(error="No existe"), 404
        d = json.loads(r["d"]); d["estado"] = e; c.execute("UPDATE citas SET d=? WHERE id=?", (json.dumps(d), cid))
    return jsonify(ok=True)

if __name__ == "__main__": app.run(debug=True)

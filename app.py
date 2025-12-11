
from flask import Flask, request, jsonify, session, redirect, url_for, render_template_string
from functools import wraps
from datetime import datetime
from conexion import getConexion

app = Flask(__name__)
app.secret_key = "llaveultrasecreta"


# -------------------- Utilidades --------------------
def json_error(message, status=400):
    return jsonify({"error": message}), status

def validate_estado(estado):
    return estado in {"Pendiente", "En Curso", "Cerrado"}

def parse_date(date_str):
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").date()
    except Exception:
        return None

def fk_exists(table, fk_id):
    conn = getConexion()
    cur = conn.cursor(buffered=True)
    cur.execute(f"SELECT 1 FROM {table} WHERE id = %s", (fk_id,))
    ok = cur.fetchone() is not None
    cur.close()
    conn.close()
    return ok

def is_admin():
    return session.get("username") == "admin"

def require_auth(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get("user_id"):
            return jsonify({"error": "No autenticado"}), 401
        return f(*args, **kwargs)
    return wrapper

def require_admin(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get("user_id"):
            return jsonify({"error": "No autenticado"}), 401
        if not is_admin():
            return jsonify({"error": "No autorizado"}), 403
        return f(*args, **kwargs)
    return wrapper

def ensure_admin_user():
    """
    Garantiza que exista el usuario admin/admin.
    Inserta si no está. (Texto plano según tu esquema actual).
    """
    try:
        conn = getConexion()
        cur = conn.cursor(buffered=True, dictionary=True)
        cur.execute("SELECT id FROM usuario WHERE username = %s", ("admin",))
        row = cur.fetchone()
        if not row:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO usuario (nombre, apellido, username, pass) VALUES (%s, %s, %s, %s)",
                ("Admin", "User", "admin", "admin"),
            )
            conn.commit()
    except Exception as e:
        try:
            conn.rollback()
        except:
            pass
        print("No se pudo crear admin:", e)
    finally:
        try:
            cur.close()
            conn.close()
        except:
            pass

# -------------------- Health/Inicio --------------------
@app.route("/", methods=["GET"])
def root_redirect():
    # si hay sesión, lleva a la UI; si no, al login
    if session.get("user_id"):
        return redirect(url_for("ui"), code=302)
    return redirect(url_for("login_ui"), code=302)

@app.route("/status", methods=["GET"])
def status():
    try:
        conn = getConexion()
        cur = conn.cursor(buffered=True)
        cur.execute("SELECT 1")
        cur.fetchone()
        cur.close()
        conn.close()
        return jsonify({"status": "ok", "db": "conectada"}), 200
    except Exception as e:
        return jsonify({"status": "error", "db_error": str(e)}), 500

# -------------------- Auth: login/logout/me --------------------
@app.route("/login", methods=["POST"])
def login():
    datos = request.json or {}
    username = datos.get("username")
    password = datos.get("pass")  # en tu UI el campo se llama 'pass'
    if not username or not password:
        return json_error("username y pass son obligatorios", 400)

    conn = getConexion()
    cur = conn.cursor(buffered=True, dictionary=True)
    cur.execute(
        "SELECT id, nombre, apellido, username, pass FROM usuario WHERE username = %s",
        (username,),
    )
    user = cur.fetchone()
    cur.close()
    conn.close()

    if not user or user["pass"] != password:
        return json_error("Credenciales inválidas", 401)

    session["user_id"] = user["id"]
    session["username"] = user["username"]
    session["nombre"] = user["nombre"]
    session["apellido"] = user["apellido"]
    return jsonify({
        "mensaje": "Login correcto",
        "usuario": {
            "id": user["id"],
            "nombre": user["nombre"],
            "apellido": user["apellido"],
            "username": user["username"],
            "rol": "admin" if user["username"] == "admin" else "usuario"
        }
    }), 200

@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"mensaje": "Logout correcto"}), 200

@app.route("/me", methods=["GET"])
def me():
    if not session.get("user_id"):
        return jsonify({"autenticado": False}), 200
    return jsonify({
        "autenticado": True,
        "usuario": {
            "id": session["user_id"],
            "username": session["username"],
            "nombre": session["nombre"],
            "apellido": session["apellido"],
            "rol": "admin" if is_admin() else "usuario"
        }
    }), 200

# -------------------- Lecturas auxiliares (listas para UI) --------------------
@app.route("/aseguradoras", methods=["GET"])
@require_auth
def listar_aseguradoras():
    conn = getConexion()
    cur = conn.cursor(buffered=True, dictionary=True)
    cur.execute("SELECT id, nombre_aseguradora FROM aseguradora ORDER BY id ASC")
    data = cur.fetchall()
    cur.close()
    conn.close()
    return jsonify(data), 200

@app.route("/juzgados", methods=["GET"])
@require_auth
def listar_juzgados():
    conn = getConexion()
    cur = conn.cursor(buffered=True, dictionary=True)
    cur.execute("SELECT id, nombre_juzgado FROM juzgado ORDER BY id ASC")
    data = cur.fetchall()
    cur.close()
    conn.close()
    return jsonify(data), 200

@app.route("/casos", methods=["GET"])
@require_auth
def listar_casos():
    conn = getConexion()
    cur = conn.cursor(buffered=True, dictionary=True)
    cur.execute("SELECT id, nombre_caso FROM caso ORDER BY id ASC")
    data = cur.fetchall()
    cur.close()
    conn.close()
    return jsonify(data), 200

@app.route("/usuarios", methods=["GET"])
@require_auth
def listar_usuarios():
    # Nota: sólo lectura para poblar combos (no devolvemos 'pass')
    conn = getConexion()
    cur = conn.cursor(buffered=True, dictionary=True)
    cur.execute("SELECT id, nombre, apellido, username FROM usuario ORDER BY id ASC")
    data = cur.fetchall()
    cur.close()
    conn.close()
    return jsonify(data), 200

# -------------------- EXPEDIENTES (lectura: todos; CRUD: solo admin) --------------------
@app.route("/expedientes", methods=["GET"])
@require_auth
def listar_expedientes():
    # Paginación
    page = request.args.get("page", default=1, type=int)
    page_size = request.args.get("page_size", default=50, type=int)
    offset = (page - 1) * page_size

    # Filtros
    estado = request.args.get("estado")  # Pendiente | En Curso | Cerrado
    aseguradora_id = request.args.get("aseguradora_id", type=int)
    usuario_id = request.args.get("usuario_id", type=int)
    juzgado_id = request.args.get("juzgado_id", type=int)
    caso_id = request.args.get("caso_id", type=int)  # <-- NUEVO
    fecha_desde = request.args.get("fecha_desde")  # YYYY-MM-DD
    fecha_hasta = request.args.get("fecha_hasta")  # YYYY-MM-DD

    where = []
    params = []

    if estado:
        if not validate_estado(estado):
            return json_error("Estado inválido. Use: Pendiente | En Curso | Cerrado", 400)
        where.append("e.estado = %s")
        params.append(estado)

    if aseguradora_id is not None:
        where.append("e.aseguradora_id = %s"); params.append(aseguradora_id)
    if usuario_id is not None:
        where.append("e.usuario_id = %s"); params.append(usuario_id)
    if juzgado_id is not None:
        where.append("e.juzgado_id = %s"); params.append(juzgado_id)
    if caso_id is not None:  # <-- NUEVO
        where.append("e.caso_id = %s"); params.append(caso_id)

    if fecha_desde:
        try:
            _ = datetime.strptime(fecha_desde, "%Y-%m-%d").date()
        except Exception:
            return json_error("fecha_desde inválida. Use YYYY-MM-DD", 400)
        where.append("e.fecha >= %s"); params.append(fecha_desde)

    if fecha_hasta:
        try:
            _ = datetime.strptime(fecha_hasta, "%Y-%m-%d").date()
        except Exception:
            return json_error("fecha_hasta inválida. Use YYYY-MM-DD", 400)
        where.append("e.fecha <= %s"); params.append(fecha_hasta)

    where_clause = ("WHERE " + " AND ".join(where)) if where else ""

    conn = getConexion()
    cur = conn.cursor(buffered=True, dictionary=True)

    # Total con filtros
    cur.execute(f"SELECT COUNT(*) AS total FROM expediente e {where_clause}", tuple(params))
    total = cur.fetchone()["total"]

    # Selección con joins y filtros
    cur.execute(f"""
        SELECT
            e.id,
            e.estado,
            e.fecha,
            e.aseguradora_id,
            a.nombre_aseguradora AS aseguradora,
            e.usuario_id,
            u.nombre AS usuario_nombre,
            u.apellido AS usuario_apellido,
            u.username AS usuario_username,
            e.juzgado_id,
            j.nombre_juzgado AS juzgado,
            e.caso_id,
            c.nombre_caso AS caso
        FROM expediente e
        JOIN aseguradora a ON e.aseguradora_id = a.id
        JOIN usuario u ON e.usuario_id = u.id
        JOIN juzgado j ON e.juzgado_id = j.id
        JOIN caso c ON e.caso_id = c.id
        {where_clause}
        ORDER BY e.id DESC
        LIMIT %s OFFSET %s
    """, tuple(params + [page_size, offset]))
    data = cur.fetchall()
    cur.close()
    conn.close()

    return jsonify({"page": page, "page_size": page_size, "total": total, "data": data}), 200

@app.route("/expedientes/<int:e_id>", methods=["GET"])
@require_auth
def obtener_expediente(e_id):
    conn = getConexion()
    cur = conn.cursor(buffered=True, dictionary=True)
    cur.execute("""
        SELECT
            e.id,
            e.estado,
            e.fecha,
            e.aseguradora_id,
            a.nombre_aseguradora AS aseguradora,
            e.usuario_id,
            u.nombre AS usuario_nombre,
            u.apellido AS usuario_apellido,
            u.username AS usuario_username,
            e.juzgado_id,
            j.nombre_juzgado AS juzgado,
            e.caso_id,
            c.nombre_caso AS caso
        FROM expediente e
        JOIN aseguradora a ON e.aseguradora_id = a.id
        JOIN usuario u ON e.usuario_id = u.id
        JOIN juzgado j ON e.juzgado_id = j.id
        JOIN caso c ON e.caso_id = c.id
        WHERE e.id = %s
    """, (e_id,))
    row = cur.fetchone()
    cur.close()
    conn.close()

    if not row:
        return json_error("Expediente no encontrado", 404)
    return jsonify(row), 200

@app.route("/expedientes", methods=["POST"])
@require_admin
def crear_expediente():
    datos = request.json or {}
    required = ["aseguradora_id", "usuario_id", "juzgado_id", "caso_id", "estado", "fecha"]  # <-- caso_id
    if any(k not in datos for k in required):
        return json_error(f"Campos obligatorios: {', '.join(required)}")

    if not validate_estado(datos["estado"]):
        return json_error("Estado inválido. Use: Pendiente | En Curso | Cerrado")

    fecha = parse_date(datos["fecha"])
    if not fecha:
        return json_error("Formato de fecha inválido. Use YYYY-MM-DD")

    # Validar FKs
    if not fk_exists("aseguradora", datos["aseguradora_id"]): return json_error("aseguradora_id no existe")
    if not fk_exists("usuario", datos["usuario_id"]): return json_error("usuario_id no existe")
    if not fk_exists("juzgado", datos["juzgado_id"]): return json_error("juzgado_id no existe")
    if not fk_exists("caso", datos["caso_id"]): return json_error("caso_id no existe")  # <-- NUEVO

    conn = getConexion()
    cur = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO expediente (aseguradora_id, usuario_id, juzgado_id, caso_id, estado, fecha)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (datos["aseguradora_id"], datos["usuario_id"], datos["juzgado_id"],
              datos["caso_id"], datos["estado"], fecha))
        conn.commit()
        return jsonify({"mensaje": "Expediente creado", "id": cur.lastrowid}), 201
    except Exception as e:
        conn.rollback()
        return json_error(str(e))
    finally:
        cur.close()
        conn.close()

@app.route("/expedientes/<int:e_id>", methods=["PUT"])
@require_admin
def actualizar_expediente(e_id):
    datos = request.json or {}
    fields, values = [], []

    if "aseguradora_id" in datos:
        if not fk_exists("aseguradora", datos["aseguradora_id"]): return json_error("aseguradora_id no existe")
        fields.append("aseguradora_id = %s"); values.append(datos["aseguradora_id"])

    if "usuario_id" in datos:
        if not fk_exists("usuario", datos["usuario_id"]): return json_error("usuario_id no existe")
        fields.append("usuario_id = %s"); values.append(datos["usuario_id"])

    if "juzgado_id" in datos:
        if not fk_exists("juzgado", datos["juzgado_id"]): return json_error("juzgado_id no existe")
        fields.append("juzgado_id = %s"); values.append(datos["juzgado_id"])

    if "caso_id" in datos:  # <-- NUEVO
        if not fk_exists("caso", datos["caso_id"]): return json_error("caso_id no existe")
        fields.append("caso_id = %s"); values.append(datos["caso_id"])

    if "estado" in datos:
        if not validate_estado(datos["estado"]): return json_error("Estado inválido. Use: Pendiente | En Curso | Cerrado")
        fields.append("estado = %s"); values.append(datos["estado"])

    if "fecha" in datos:
        fecha = parse_date(datos["fecha"])
        if not fecha: return json_error("Formato de fecha inválido. Use YYYY-MM-DD")
        fields.append("fecha = %s"); values.append(fecha)

    if not fields:
        return json_error("Sin cambios", 400)

    values.append(e_id)

    conn = getConexion()
    cur = conn.cursor()
    try:
        cur.execute(f"UPDATE expediente SET {', '.join(fields)} WHERE id = %s", tuple(values))
        if cur.rowcount == 0:
            conn.rollback()
            return json_error("Expediente no encontrado", 404)
        conn.commit()
        return jsonify({"mensaje": "Expediente actualizado"}), 200
    except Exception as e:
        conn.rollback()
        return json_error(str(e))
    finally:
        cur.close()
        conn.close()

@app.route("/expedientes/<int:e_id>", methods=["DELETE"])
@require_admin
def eliminar_expediente(e_id):
    conn = getConexion()
    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM expediente WHERE id = %s", (e_id,))
        if cur.rowcount == 0:
            conn.rollback()
            return json_error("Expediente no encontrado", 404)
        conn.commit()
        return jsonify({"mensaje": "Expediente eliminado"}), 200
    except Exception as e:
        conn.rollback()
        return json_error(str(e))
    finally:
        cur.close()
        conn.close()

# -------------------- UI: Login y Vista de Expedientes --------------------
@app.route("/login-ui", methods=["GET"])
def login_ui():
    html = """
<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<title>Login</title>
<style>
  body { font-family: Arial, sans-serif; margin: 24px; }
  form { max-width: 360px; display: grid; gap: 12px; }
  input { padding: 8px; font-size: 16px; }
  button { padding: 10px; }
  .msg { margin-top: 12px; }
  .hint { margin-top: 8px; color: #555; }
</style>
</head>
<body>
<h1>Iniciar sesión</h1>
<form id="f">
  <input name="username" placeholder="Usuario" required />
  <input name="pass" type="password" placeholder="Contraseña" required />
  <button type="submit">Entrar</button>
</form>
<div class="msg" id="msg"></div>
<div class="hint">Tip: admin/admin para gestionar expedientes.</div>
<script>
const f = document.getElementById('f');
const msg = document.getElementById('msg');
f.addEventListener('submit', async (e) => {
  e.preventDefault();
  const payload = {
    username: f.username.value.trim(),
    pass: f.pass.value
  };
  msg.textContent = 'Validando...';
  try {
    const r = await fetch('/login', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(payload)
    });
    const j = await r.json();
    if (r.ok) {
      msg.textContent = 'Login correcto. Redirigiendo...';
      setTimeout(() => { window.location.href = '/ui'; }, 500);
    } else {
      msg.textContent = 'Error: ' + (j.error ?? 'Error desconocido');
    }
  } catch (err) {
    msg.textContent = 'Error de red';
  }
});
</script>
</body>
</html>
    """
    return html

@app.route("/ui", methods=["GET"])
def ui():
    html = """
<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<title>Expedientes</title>
<style>
  body { font-family: Arial, sans-serif; margin: 24px; }
  table { border-collapse: collapse; width: 100%; }
  th, td { border: 1px solid #ddd; padding: 8px; }
  th { background: #f3f3f3; }
  .top { display: flex; gap: 12px; align-items: center; margin-bottom: 12px; }
  button { padding: 8px 12px; cursor: pointer; }
  .btn-danger { background: #dc2626; color: #fff; border: none; border-radius: 4px; }
  .btn-secondary { background: #6b7280; color: #fff; border: none; border-radius: 4px; }
  .btn { background: #2563eb; color: #fff; border: none; border-radius: 4px; }
  .card { border: 1px solid #ddd; padding: 12px; border-radius: 8px; margin-top: 10px; }
  form.grid { display: grid; grid-template-columns: repeat(6, 1fr); gap: 8px; align-items: end; }
  form.grid label { font-size: 12px; color: #555; }
  select, input { padding: 6px; }
  #adminPanel { border: 1px dashed #0a8; }
  #editPanel { border: 1px dashed #d97706; }
  .msg { margin-top: 8px; color: #555; }
  .actions { display: flex; gap: 8px; }
</style>
</head>
<body>
<div class="top">
  <h1 style="flex:1">Expedientes</h1>
  <div id="user">Verificando sesión...</div>
  <button id="logout" class="btn-secondary">Cerrar sesión</button>
</div>

<!-- Panel de filtros (visible para todos los autenticados) -->
<div class="card" id="filterPanel">
  <h3>Filtros</h3>
  <form class="grid" id="formFiltros">
    <div>
      <label>Estado</label>
      <select id="f_estado">
        <option value="">Todos</option>
        <option value="Pendiente">Pendiente</option>
        <option value="En Curso">En Curso</option>
        <option value="Cerrado">Cerrado</option>
      </select>
    </div>
    <div>
      <label>Aseguradora</label>
      <select id="f_aseguradora_id">
        <option value="">Todas</option>
      </select>
    </div>
    <div>
      <label>Usuario</label>
      <select id="f_usuario_id">
        <option value="">Todos</option>
      </select>
    </div>
    <div>
      <label>Juzgado</label>
      <select id="f_juzgado_id">
        <option value="">Todos</option>
      </select>
    </div>
    <div>
      <label>Caso</label>
      <select id="f_caso_id">
        <option value="">Todos</option>
      </select>
    </div>
    <div>
      <label>Fecha desde</label>
      <input id="f_fecha_desde" type="date" />
    </div>
    <div>
      <label>Fecha hasta</label>
      <input id="f_fecha_hasta" type="date" />
    </div>
    <div style="grid-column: span 6; display:flex; gap:8px; justify-content:flex-end; margin-top:6px;">
      <button type="button" id="btnFiltrar" class="btn">Aplicar filtros</button>
      <button type="button" id="btnLimpiar" class="btn-secondary">Limpiar</button>
    </div>
  </form>
  <div id="filterMsg" class="msg"></div>
</div>

<!-- Panel de creación -->
<div id="adminPanel" class="card" style="display:none;">
  <h3>Crear expediente </h3>
  <form id="formNuevo" class="grid">
    <div>
      <label>Aseguradora</label>
      <select id="aseguradora_id"></select>
    </div>
    <div>
      <label>Usuario</label>
      <select id="usuario_id"></select>
    </div>
    <div>
      <label>Juzgado</label>
      <select id="juzgado_id"></select>
    </div>
    <div>
      <label>Caso</label>
      <select id="caso_id"></select>
    </div>
    <div>
      <label>Estado</label>
      <select id="estado">
        <option>Pendiente</option>
        <option>En Curso</option>
        <option>Cerrado</option>
      </select>
    </div>
    <div>
      <label>Fecha</label>
      <input id="fecha" type="date" />
    </div>
    <button type="submit" class="btn">Crear</button>
  </form>
  <div id="adminMsg" class="msg"></div>
</div>

<!-- Panel de edición -->
<div id="editPanel" class="card" style="display:none;">
  <h3>Editar expediente </h3>
  <form id="formEdit" class="grid">
    <input type="hidden" id="edit_id" />
    <div>
      <label>Aseguradora</label>
      <select id="edit_aseguradora_id"></select>
    </div>
    <div>
      <label>Usuario</label>
      <select id="edit_usuario_id"></select>
    </div>
    <div>
      <label>Juzgado</label>
      <select id="edit_juzgado_id"></select>
    </div>
    <div>
      <label>Caso</label>
      <select id="edit_caso_id"></select>
    </div>
    <div>
      <label>Estado</label>
      <select id="edit_estado">
        <option>Pendiente</option>
        <option>En Curso</option>
        <option>Cerrado</option>
      </select>
    </div>
    <div>
      <label>Fecha</label>
      <input id="edit_fecha" type="date" />
    </div>
    <button type="submit" class="btn">Guardar cambios</button>
    <button type="button" id="cancelEdit" class="btn-secondary">Cancelar</button>
  </form>
  <div id="editMsg" class="msg"></div>
</div>

<!-- Tabla de expedientes -->
<div class="card">
  <table id="tabla">
    <thead>
      <tr>
        <th>ID</th>
        <th>Estado</th>
        <th>Fecha</th>
        <th>Aseguradora</th>
        <th>Usuario</th>
        <th>Juzgado</th>
        <th>Caso</th>
        <th id="th-acciones">Acciones</th>
      </tr>
    </thead>
    <tbody></tbody>
  </table>
  <div id="tableMsg" class="msg"></div>
</div>

<script>
async function fetchJSON(url, opts = {}) {
  const r = await fetch(url, opts);
  const j = await r.json().catch(() => ({}));
  if (!r.ok) {
    const err = new Error(j.error ?? ('HTTP ' + r.status));
    err.status = r.status;
    err.payload = j;
    throw err;
  }
  return j;
}

async function me() { return fetchJSON('/me'); }

// Carga catálogos para filtros y para paneles admin
async function cargarCatalogos() {
  const [ases, usrs, juzgs, casos] = await Promise.all([
    fetchJSON('/aseguradoras'),
    fetchJSON('/usuarios'),
    fetchJSON('/juzgados'),
    fetchJSON('/casos')
  ]);

  // Filtros (con opción "Todos/Todas")
  const fA = document.getElementById('f_aseguradora_id');
  const fU = document.getElementById('f_usuario_id');
  const fJ = document.getElementById('f_juzgado_id');
  const fC = document.getElementById('f_caso_id');

  fA.innerHTML = '<option value="">Todas</option>' +
    ases.map(a => `<option value="${a.id}">${a.nombre_aseguradora}</option>`).join('');
  fU.innerHTML = '<option value="">Todos</option>' +
    usrs.map(u => `<option value="${u.id}">${u.nombre} ${u.apellido}</option>`).join('');
  fJ.innerHTML = '<option value="">Todos</option>' +
    juzgs.map(j => `<option value="${j.id}">${j.nombre_juzgado}</option>`).join('');
  fC.innerHTML = '<option value="">Todos</option>' +
    casos.map(c => `<option value="${c.id}">${c.nombre_caso}</option>`).join('');

  // Panel crear/editar (copiamos las opciones)
  document.getElementById('aseguradora_id').innerHTML =
    ases.map(a => `<option value="${a.id}">${a.nombre_aseguradora}</option>`).join('');
  document.getElementById('usuario_id').innerHTML =
    usrs.map(u => `<option value="${u.id}">${u.nombre} ${u.apellido}</option>`).join('');
  document.getElementById('juzgado_id').innerHTML =
    juzgs.map(j => `<option value="${j.id}">${j.nombre_juzgado}</option>`).join('');
  document.getElementById('caso_id').innerHTML =
    casos.map(c => `<option value="${c.id}">${c.nombre_caso}</option>`).join('');

  document.getElementById('edit_aseguradora_id').innerHTML = document.getElementById('aseguradora_id').innerHTML;
  document.getElementById('edit_usuario_id').innerHTML = document.getElementById('usuario_id').innerHTML;
  document.getElementById('edit_juzgado_id').innerHTML = document.getElementById('juzgado_id').innerHTML;
  document.getElementById('edit_caso_id').innerHTML = document.getElementById('caso_id').innerHTML;
}

function buildQueryFromFilters() {
  const params = new URLSearchParams();
  params.set('page', '1');
  params.set('page_size', '100');

  const estado = document.getElementById('f_estado').value;
  const aseguradora_id = document.getElementById('f_aseguradora_id').value;
  const usuario_id = document.getElementById('f_usuario_id').value;
  const juzgado_id = document.getElementById('f_juzgado_id').value;
  const caso_id = document.getElementById('f_caso_id').value;
  const fecha_desde = document.getElementById('f_fecha_desde').value;
  const fecha_hasta = document.getElementById('f_fecha_hasta').value;

  if (estado) params.set('estado', estado);
  if (aseguradora_id) params.set('aseguradora_id', aseguradora_id);
  if (usuario_id) params.set('usuario_id', usuario_id);
  if (juzgado_id) params.set('juzgado_id', juzgado_id);
  if (caso_id) params.set('caso_id', caso_id);
  if (fecha_desde) params.set('fecha_desde', fecha_desde);
  if (fecha_hasta) params.set('fecha_hasta', fecha_hasta);

  return params.toString();
}

function renderFila(row, rol) {
  const accionesHTML = (rol === 'admin')
    ? `<div class="actions">
         <button class="btn btn-edit" data-id="${row.id}">Editar</button>
         <button class="btn-danger btn-del" data-id="${row.id}">Eliminar</button>
       </div>`
    : '';
  const celdaAcciones = (rol === 'admin') ? `<td>${accionesHTML}</td>` : '';
  return `
    <tr data-rowid="${row.id}">
      <td>${row.id ?? ''}</td>
      <td>${row.estado ?? ''}</td>
      <td>${row.fecha ?? ''}</td>
      <td>${row.aseguradora ?? ''}</td>
      <td>${(row.usuario_nombre ?? '') + ' ' + (row.usuario_apellido ?? '')}</td>
      <td>${row.juzgado ?? ''}</td>
      <td>${row.caso ?? ''}</td>
      ${celdaAcciones}
    </tr>
  `;
}

async function cargarExpedientes(rol) {
  const tbody = document.querySelector('#tabla tbody');
  const tableMsg = document.getElementById('tableMsg');
  const colspan = (rol === 'admin') ? 8 : 7; // con columna Caso

  tbody.innerHTML = `<tr><td colspan="${colspan}">Cargando...</td></tr>`;
  tableMsg.textContent = '';
  try {
    const qs = buildQueryFromFilters();
    const j = await fetchJSON('/expedientes?' + qs);
    tbody.innerHTML = '';
    j.data.forEach(row => {
      tbody.insertAdjacentHTML('beforeend', renderFila(row, rol));
    });
    if (j.data.length === 0) {
      tbody.innerHTML = `<tr><td colspan="${colspan}">Sin datos</td></tr>`;
    }
  } catch (e) {
    if (e.status === 401) window.location.href = '/login-ui';
    tableMsg.textContent = 'Error cargando expedientes: ' + (e.payload?.error ?? e.message ?? 'desconocido');
  }
}

async function abrirEditar(id) {
  const editPanel = document.getElementById('editPanel');
  const editMsg = document.getElementById('editMsg');
  editMsg.textContent = 'Cargando expediente ' + id + '...';
  try {
    const exp = await fetchJSON('/expedientes/' + id);
    document.getElementById('edit_id').value = exp.id;
    document.getElementById('edit_aseguradora_id').value = exp.aseguradora_id;
    document.getElementById('edit_usuario_id').value = exp.usuario_id;
    document.getElementById('edit_juzgado_id').value = exp.juzgado_id;
    document.getElementById('edit_caso_id').value = exp.caso_id; // <-- NUEVO
    document.getElementById('edit_estado').value = exp.estado;
    document.getElementById('edit_fecha').value = exp.fecha ?? '';
    editMsg.textContent = '';
    editPanel.style.display = 'block';
    editPanel.scrollIntoView({behavior:'smooth'});
  } catch (e) {
    editMsg.textContent = 'Error cargando: ' + (e.payload?.error ?? e.message ?? 'desconocido');
  }
}

async function init() {
  try {
    const info = await me();
    if (!info.autenticado) { window.location.href = '/login-ui'; return; }
    const rol = info.usuario.rol;
    const userText = `Sesión: ${info.usuario.nombre} ${info.usuario.apellido} (@${info.usuario.username}) [${rol}]`;
    document.getElementById('user').textContent = userText;

    const adminPanel = document.getElementById('adminPanel');
    const thAcciones = document.getElementById('th-acciones');
    if (rol === 'admin') {
      adminPanel.style.display = 'block';
      thAcciones.style.display = ''; // visible
    } else {
      adminPanel.style.display = 'none';
      thAcciones.style.display = 'none'; // oculta columna Acciones para usuarios
    }

    // Cargar catálogos para filtros y paneles
    await cargarCatalogos();

    // Cargar expedientes con filtros iniciales (vacíos)
    await cargarExpedientes(rol);

    // Eventos: filtro, limpiar, editar/eliminar
    document.getElementById('btnFiltrar').addEventListener('click', async () => {
      await cargarExpedientes(rol);
    });

    document.getElementById('btnLimpiar').addEventListener('click', async () => {
      document.getElementById('f_estado').value = '';
      document.getElementById('f_aseguradora_id').value = '';
      document.getElementById('f_usuario_id').value = '';
      document.getElementById('f_juzgado_id').value = '';
      document.getElementById('f_caso_id').value = '';
      document.getElementById('f_fecha_desde').value = '';
      document.getElementById('f_fecha_hasta').value = '';
      await cargarExpedientes(rol);
    });

    // Acciones admin en tabla
    document.addEventListener('click', async (ev) => {
      if (ev.target.classList.contains('btn-edit')) {
        const id = ev.target.getAttribute('data-id');
        await abrirEditar(id);
      }
      if (ev.target.classList.contains('btn-del')) {
        const id = ev.target.getAttribute('data-id');
        if (!confirm('¿Eliminar expediente ' + id + '?')) return;
        const tableMsg = document.getElementById('tableMsg');
        tableMsg.textContent = 'Eliminando...';
        try {
          await fetchJSON('/expedientes/' + id, { method: 'DELETE' });
          tableMsg.textContent = 'Eliminado';
          await cargarExpedientes(rol);
        } catch (e) {
          tableMsg.textContent = 'Error: ' + (e.payload?.error ?? e.message ?? 'desconocido');
        }
      }
    });
  } catch (e) {
    window.location.href = '/login-ui';
  }
}

// Crear expediente
document.getElementById('formNuevo').addEventListener('submit', async (e) => {
  e.preventDefault();
  const adminMsg = document.getElementById('adminMsg');
  adminMsg.textContent = 'Creando...';
  const payload = {
    aseguradora_id: parseInt(document.getElementById('aseguradora_id').value),
    usuario_id: parseInt(document.getElementById('usuario_id').value),
    juzgado_id: parseInt(document.getElementById('juzgado_id').value),
    caso_id: parseInt(document.getElementById('caso_id').value),   // <-- NUEVO
    estado: document.getElementById('estado').value,
    fecha: document.getElementById('fecha').value
  };
  try {
    const j = await fetchJSON('/expedientes', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(payload)
    });
    adminMsg.textContent = 'Creado: ID ' + j.id;
    const info = await me();
    await cargarExpedientes(info.usuario.rol);
  } catch (e) {
    adminMsg.textContent = 'Error: ' + (e.payload?.error ?? e.message ?? 'desconocido');
  }
});

// Guardar edición (PUT)
document.getElementById('formEdit').addEventListener('submit', async (e) => {
  e.preventDefault();
  const editMsg = document.getElementById('editMsg');
  editMsg.textContent = 'Guardando cambios...';
  const id = document.getElementById('edit_id').value;
  const payload = {
    aseguradora_id: parseInt(document.getElementById('edit_aseguradora_id').value),
    usuario_id: parseInt(document.getElementById('edit_usuario_id').value),
    juzgado_id: parseInt(document.getElementById('edit_juzgado_id').value),
    caso_id: parseInt(document.getElementById('edit_caso_id').value),   // <-- NUEVO
    estado: document.getElementById('edit_estado').value,
    fecha: document.getElementById('edit_fecha').value
  };
  try {
    await fetchJSON('/expedientes/' + id, {
      method: 'PUT',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(payload)
    });
    editMsg.textContent = 'Cambios guardados';
    document.getElementById('editPanel').style.display = 'none';
    const info = await me();
    await cargarExpedientes(info.usuario.rol);
  } catch (e) {
    editMsg.textContent = 'Error: ' + (e.payload?.error ?? e.message ?? 'desconocido');
  }
});

// Cancelar edición
document.getElementById('cancelEdit').addEventListener('click', () => {
  document.getElementById('editPanel').style.display = 'none';
  document.getElementById('editMsg').textContent = '';
});

// Logout
document.getElementById('logout').addEventListener('click', async () => {
  try { await fetchJSON('/logout', {method:'POST'}); } catch {}
  window.location.href = '/login-ui';
});

// Arranque
init();
</script>
</body>
</html>
    """
    return html

# -------------------- Arranque --------------------

if __name__ == "__main__":
    ensure_admin_user()  # crea admin si no existe
    app.run(host="0.0.0.0", port=5000, debug=True)

from flask import Flask, render_template, request, jsonify, redirect, url_for, session
from functools import wraps
import sqlite3
import os

# ── App ──────────────────────────────────────────────
app = Flask(__name__)

# !! CAMBIÁ ESTO por una clave secreta larga y aleatoria !!
app.secret_key = 'cambia-esto-por-una-clave-secreta-larga'

app.config.update(
    SESSION_COOKIE_SECURE=True,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
)

# ── Credenciales de la agenda ─────────────────────────
# Cambiá estos valores por los que quieras usar
AGENDA_USER     = 'admin'
AGENDA_PASSWORD = 'clubpilates2025'

# Código secreto para recuperar la contraseña (solo vos lo sabés)
RECOVERY_CODE   = 'sanjuan2025'

# ── Decorador: requiere login ─────────────────────────
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('logged_in'):
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

# ── Base de datos ─────────────────────────────────────
DB_PATH = os.path.join(os.path.dirname(__file__), 'agenda.db')

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db() as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS reservas (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                slot_key  TEXT    NOT NULL UNIQUE,
                nombre    TEXT    NOT NULL,
                apellido  TEXT    NOT NULL,
                tel       TEXT    NOT NULL,
                created_at DATETIME DEFAULT (datetime('now','-3 hours'))
            )
        ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS alumnas (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre      TEXT    NOT NULL,
                apellido    TEXT    NOT NULL,
                tel         TEXT,
                email       TEXT,
                fecha_nac   TEXT,
                notas       TEXT,
                activa      INTEGER DEFAULT 1,
                created_at  DATETIME DEFAULT (datetime('now','-3 hours'))
            )
        ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS movimientos (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                tipo        TEXT    NOT NULL CHECK(tipo IN ('ingreso','gasto')),
                categoria   TEXT    NOT NULL,
                descripcion TEXT    NOT NULL,
                monto       REAL    NOT NULL,
                fecha       TEXT    NOT NULL,
                alumna_id   INTEGER REFERENCES alumnas(id) ON DELETE SET NULL,
                created_at  DATETIME DEFAULT (datetime('now','-3 hours'))
            )
        ''')
        # Migraciones automáticas
        cols_mov = [r[1] for r in conn.execute("PRAGMA table_info(movimientos)").fetchall()]
        if 'alumna_id' not in cols_mov:
            conn.execute("ALTER TABLE movimientos ADD COLUMN alumna_id INTEGER REFERENCES alumnas(id) ON DELETE SET NULL")

        cols_alum = [r[1] for r in conn.execute("PRAGMA table_info(alumnas)").fetchall()]
        if 'plan' not in cols_alum:
            conn.execute("ALTER TABLE alumnas ADD COLUMN plan TEXT DEFAULT NULL")

        cols_res = [r[1] for r in conn.execute("PRAGMA table_info(reservas)").fetchall()]
        if 'alumna_id' not in cols_res:
            conn.execute("ALTER TABLE reservas ADD COLUMN alumna_id INTEGER REFERENCES alumnas(id) ON DELETE SET NULL")

        conn.commit()

# Inicializar DB al arrancar
init_db()

# ── Rutas principales ─────────────────────────────────
@app.route('/favicon.ico')
def favicon():
    return redirect(url_for('static', filename='img/favicon.svg'))

@app.route('/')
def index():
    contact_data = {
        "whatsapp_link": "https://wa.me/5492645551234",
        "email": "clubpilatesanjuan@gmail.com",
        "address": "San Roque Sur 1044, Rawson, San Juan",
        "google_maps_api_key": "TU_API_KEY_AQUI"
    }
    return render_template('index.html', data=contact_data)

# ── Login / Logout ────────────────────────────────────
@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        user = request.form.get('usuario', '').strip()
        pwd  = request.form.get('password', '').strip()
        if user == AGENDA_USER and pwd == AGENDA_PASSWORD:
            session['logged_in'] = True
            return redirect(url_for('agenda'))
        else:
            error = 'Usuario o contraseña incorrectos'
    return render_template('login.html', error=error)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/recuperar', methods=['GET', 'POST'])
def recuperar():
    error   = None
    success = None
    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'verificar':
            code = request.form.get('codigo', '').strip()
            if code == RECOVERY_CODE:
                session['recovery_verified'] = True
                return render_template('recuperar.html', step='nueva', error=None)
            else:
                error = 'Código incorrecto'
                return render_template('recuperar.html', step='codigo', error=error)

        elif action == 'cambiar':
            if not session.get('recovery_verified'):
                return redirect(url_for('recuperar'))
            nueva    = request.form.get('nueva', '').strip()
            confirma = request.form.get('confirma', '').strip()
            if not nueva or len(nueva) < 6:
                return render_template('recuperar.html', step='nueva', error='La contraseña debe tener al menos 6 caracteres')
            if nueva != confirma:
                return render_template('recuperar.html', step='nueva', error='Las contraseñas no coinciden')
            # Actualizar en memoria (hasta el próximo restart)
            global AGENDA_PASSWORD
            AGENDA_PASSWORD = nueva
            session.pop('recovery_verified', None)
            return render_template('recuperar.html', step='ok')

    return render_template('recuperar.html', step='codigo', error=None)


@app.route('/agenda')
@login_required
def agenda():
    return render_template('agenda.html')

# ── API de Reservas ───────────────────────────────────

@app.route('/api/reservas', methods=['GET'])
@login_required
def get_reservas():
    desde = request.args.get('desde', '')
    hasta = request.args.get('hasta', '')
    try:
        with get_db() as conn:
            if desde and hasta:
                rows = conn.execute(
                    'SELECT * FROM reservas WHERE slot_key BETWEEN ? AND ? ORDER BY slot_key',
                    (desde, hasta + '_99')
                ).fetchall()
            else:
                rows = conn.execute('SELECT * FROM reservas ORDER BY slot_key').fetchall()

        result = {}
        for row in rows:
            result[row['slot_key']] = {
                'id':        row['id'],
                'nombre':    row['nombre'],
                'apellido':  row['apellido'],
                'tel':       row['tel'],
                'createdAt': row['created_at']
            }
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/reservas', methods=['POST'])
@login_required
def create_reserva():
    data      = request.get_json()
    slot_key  = data.get('slot_key',  '').strip()
    nombre    = data.get('nombre',    '').strip()
    apellido  = data.get('apellido',  '').strip()
    tel       = data.get('tel',       '').strip()
    alumna_id = data.get('alumna_id', None)

    if not all([slot_key, nombre, apellido, tel]):
        return jsonify({'error': 'Faltan campos obligatorios'}), 400

    try:
        with get_db() as conn:
            conn.execute(
                'INSERT INTO reservas (slot_key, nombre, apellido, tel, alumna_id) VALUES (?, ?, ?, ?, ?)',
                (slot_key, nombre, apellido, tel, alumna_id if alumna_id else None)
            )
            conn.commit()
        return jsonify({'ok': True}), 201
    except sqlite3.IntegrityError:
        return jsonify({'error': 'Ese turno ya está reservado'}), 409
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/reservas/<path:slot_key>', methods=['DELETE'])
@login_required
def delete_reserva(slot_key):
    try:
        with get_db() as conn:
            conn.execute('DELETE FROM reservas WHERE slot_key = ?', (slot_key,))
            conn.commit()
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ── API de Alumnas ────────────────────────────────────

@app.route('/api/alumnas', methods=['GET'])
@login_required
def get_alumnas():
    activa = request.args.get('activa', '')
    try:
        with get_db() as conn:
            query = 'SELECT * FROM alumnas'
            params = []
            if activa != '':
                query += ' WHERE activa = ?'
                params.append(int(activa))
            query += ' ORDER BY apellido, nombre'
            rows = conn.execute(query, params).fetchall()
        return jsonify([dict(r) for r in rows])
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/alumnas', methods=['POST'])
@login_required
def create_alumna():
    data     = request.get_json()
    nombre   = data.get('nombre',    '').strip()
    apellido = data.get('apellido',  '').strip()
    tel      = data.get('tel',       '').strip()
    email    = data.get('email',     '').strip()
    fecha_nac= data.get('fecha_nac', '').strip()
    notas    = data.get('notas',     '').strip()
    plan     = data.get('plan',      None)
    if not nombre or not apellido:
        return jsonify({'error': 'Nombre y apellido son obligatorios'}), 400
    try:
        with get_db() as conn:
            cur = conn.execute(
                'INSERT INTO alumnas (nombre, apellido, tel, email, fecha_nac, notas, plan) VALUES (?,?,?,?,?,?,?)',
                (nombre, apellido, tel, email, fecha_nac, notas, plan)
            )
            conn.commit()
            row = conn.execute('SELECT * FROM alumnas WHERE id = ?', (cur.lastrowid,)).fetchone()
        return jsonify(dict(row)), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# IMPORTANTE: estas rutas deben estar ANTES de /<int:alumna_id>
@app.route('/api/alumnas/pagos', methods=['GET'])
@login_required
def get_pagos():
    mes = request.args.get('mes', '')
    try:
        with get_db() as conn:
            rows = conn.execute('''
                SELECT alumna_id, MIN(fecha) as fecha_pago
                FROM movimientos
                WHERE tipo = 'ingreso'
                  AND alumna_id IS NOT NULL
                  AND fecha LIKE ?
                GROUP BY alumna_id
            ''', (f'{mes}%',)).fetchall()
        return jsonify({str(r['alumna_id']): r['fecha_pago'] for r in rows})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/alumnas/clases', methods=['GET'])
@login_required
def get_clases():
    mes = request.args.get('mes', '')
    try:
        with get_db() as conn:
            rows = conn.execute('''
                SELECT alumna_id, COUNT(*) as usadas
                FROM reservas
                WHERE alumna_id IS NOT NULL
                  AND substr(slot_key, 1, 7) = ?
                GROUP BY alumna_id
            ''', (mes,)).fetchall()
        return jsonify({str(r['alumna_id']): r['usadas'] for r in rows})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/alumnas/<int:alumna_id>', methods=['PUT'])
@login_required
def update_alumna(alumna_id):
    data = request.get_json()
    try:
        with get_db() as conn:
            conn.execute('''
                UPDATE alumnas SET nombre=?, apellido=?, tel=?, email=?, fecha_nac=?, notas=?, activa=?, plan=?
                WHERE id=?
            ''', (
                data.get('nombre','').strip(),
                data.get('apellido','').strip(),
                data.get('tel','').strip(),
                data.get('email','').strip(),
                data.get('fecha_nac','').strip(),
                data.get('notas','').strip(),
                int(data.get('activa', 1)),
                data.get('plan', None),
                alumna_id
            ))
            conn.commit()
            row = conn.execute('SELECT * FROM alumnas WHERE id = ?', (alumna_id,)).fetchone()
        return jsonify(dict(row))
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/alumnas/<int:alumna_id>', methods=['DELETE'])
@login_required
def delete_alumna(alumna_id):
    try:
        with get_db() as conn:
            conn.execute('DELETE FROM alumnas WHERE id = ?', (alumna_id,))
            conn.commit()
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ── API de Finanzas ───────────────────────────────────

@app.route('/api/movimientos', methods=['GET'])
@login_required
def get_movimientos():
    mes  = request.args.get('mes', '')
    tipo = request.args.get('tipo', '')
    try:
        with get_db() as conn:
            query  = '''SELECT m.*, a.nombre || ' ' || a.apellido as alumna_nombre
                        FROM movimientos m LEFT JOIN alumnas a ON m.alumna_id = a.id
                        WHERE 1=1'''
            params = []
            if mes:
                query  += ' AND m.fecha LIKE ?'
                params.append(f'{mes}%')
            if tipo:
                query  += ' AND m.tipo = ?'
                params.append(tipo)
            query += ' ORDER BY m.fecha DESC, m.id DESC'
            rows = conn.execute(query, params).fetchall()
        return jsonify([dict(r) for r in rows])
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/movimientos', methods=['POST'])
@login_required
def create_movimiento():
    data        = request.get_json()
    tipo        = data.get('tipo', '').strip()
    categoria   = data.get('categoria', '').strip()
    descripcion = data.get('descripcion', '').strip()
    monto       = data.get('monto', 0)
    fecha       = data.get('fecha', '').strip()
    alumna_id   = data.get('alumna_id', None)

    if not all([tipo, categoria, descripcion, monto, fecha]):
        return jsonify({'error': 'Faltan campos obligatorios'}), 400
    if tipo not in ('ingreso', 'gasto'):
        return jsonify({'error': 'Tipo inválido'}), 400

    try:
        with get_db() as conn:
            cur = conn.execute(
                'INSERT INTO movimientos (tipo, categoria, descripcion, monto, fecha, alumna_id) VALUES (?, ?, ?, ?, ?, ?)',
                (tipo, categoria, descripcion, float(monto), fecha, alumna_id if alumna_id else None)
            )
            conn.commit()
            row = conn.execute(
                '''SELECT m.*, a.nombre || ' ' || a.apellido as alumna_nombre
                   FROM movimientos m LEFT JOIN alumnas a ON m.alumna_id = a.id
                   WHERE m.id = ?''', (cur.lastrowid,)
            ).fetchone()
        return jsonify(dict(row)), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/movimientos/<int:mov_id>', methods=['DELETE'])
@login_required
def delete_movimiento(mov_id):
    try:
        with get_db() as conn:
            conn.execute('DELETE FROM movimientos WHERE id = ?', (mov_id,))
            conn.commit()
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/movimientos/resumen', methods=['GET'])
@login_required
def resumen_movimientos():
    mes = request.args.get('mes', '')
    try:
        with get_db() as conn:
            params = [f'{mes}%'] if mes else ['%']
            ingresos = conn.execute(
                'SELECT COALESCE(SUM(monto),0) as total FROM movimientos WHERE tipo="ingreso" AND fecha LIKE ?',
                params
            ).fetchone()['total']
            gastos = conn.execute(
                'SELECT COALESCE(SUM(monto),0) as total FROM movimientos WHERE tipo="gasto" AND fecha LIKE ?',
                params
            ).fetchone()['total']
        return jsonify({'ingresos': ingresos, 'gastos': gastos, 'balance': ingresos - gastos})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ── Arranque ──────────────────────────────────────────
if __name__ == '__main__':
    app.run(debug=True)
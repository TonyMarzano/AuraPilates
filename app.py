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
                created_at DATETIME DEFAULT (datetime('now','localtime'))
            )
        ''')
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


    contact_data = {
        "whatsapp_link": "https://wa.me/5492645551234",
        "email": "clubpilatesanjuan@gmail.com",
        "address": "San Roque Sur 1044, Rawson, San Juan",
        "google_maps_api_key": "TU_API_KEY_AQUI"
    }
    return render_template('index.html', data=contact_data)

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
    data     = request.get_json()
    slot_key = data.get('slot_key', '').strip()
    nombre   = data.get('nombre',   '').strip()
    apellido = data.get('apellido', '').strip()
    tel      = data.get('tel',      '').strip()

    if not all([slot_key, nombre, apellido, tel]):
        return jsonify({'error': 'Faltan campos obligatorios'}), 400

    try:
        with get_db() as conn:
            conn.execute(
                'INSERT INTO reservas (slot_key, nombre, apellido, tel) VALUES (?, ?, ?, ?)',
                (slot_key, nombre, apellido, tel)
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

# ── Arranque ──────────────────────────────────────────
if __name__ == '__main__':
    app.run(debug=True)
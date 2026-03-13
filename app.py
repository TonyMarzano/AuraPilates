from flask import Flask, render_template, request, jsonify, redirect, url_for, session
from functools import wraps
import sqlite3
import os
import smtplib
import threading
import json
from datetime import date, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

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
AGENDA_USER     = 'admin'
AGENDA_PASSWORD = 'clubpilates2025'
RECOVERY_CODE   = 'sanjuan2025'

# ── Configuración de email ────────────────────────────
# Obtené tu App Password en: myaccount.google.com → Seguridad → Contraseñas de aplicaciones
EMAIL_FROM     = 'clubpilatesanjuan@gmail.com'
EMAIL_PASSWORD = os.environ.get('EMAIL_PASSWORD', '')
EMAIL_ENABLED  = True

# ── Configuración del Bot de WhatsApp (Twilio) ────────
TWILIO_ACCOUNT_SID  = os.environ.get('TWILIO_ACCOUNT_SID', '')
TWILIO_AUTH_TOKEN   = os.environ.get('TWILIO_AUTH_TOKEN', '')
TWILIO_WA_NUMBER    = os.environ.get('TWILIO_WA_NUMBER', 'whatsapp:+14155238886')
ANTHROPIC_API_KEY   = os.environ.get('ANTHROPIC_API_KEY', '')

# ── Decorador: requiere login ─────────────────────────
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('logged_in'):
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

# ── Email de bienvenida ───────────────────────────────

PLAN_INFO = {
    'plan8':      ('Plan 8 clases',      '2 clases por semana', '$45.000'),
    'plan4':      ('Plan 4 clases',      '1 clase por semana',  '$25.000'),
    'individual': ('Clase individual',   '1 clase',             '$6.000'),
}

def _build_welcome_html(nombre, apellido, plan):
    plan_nombre, plan_detalle, plan_precio = PLAN_INFO.get(plan, ('—', '—', '—')) if plan else ('Sin plan asignado', '', '')

    plan_block = ''
    if plan:
        plan_block = f'''
        <div style="background:#eaf3e8;border-left:3px solid #8aab85;border-radius:6px;padding:16px 20px;margin:24px 0;">
            <div style="font-size:11px;letter-spacing:0.2em;text-transform:uppercase;color:#7a8f79;margin-bottom:6px;">Tu plan</div>
            <div style="font-size:20px;font-weight:500;color:#3d4f3c;">{plan_nombre}</div>
            <div style="font-size:14px;color:#7a8f79;margin-top:4px;">{plan_detalle} &nbsp;·&nbsp; {plan_precio} / mes</div>
        </div>'''

    return f'''<!DOCTYPE html>
<html lang="es">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#f2f7f1;font-family:'Helvetica Neue',Arial,sans-serif;">
<div style="max-width:560px;margin:40px auto;background:white;border-radius:12px;overflow:hidden;box-shadow:0 4px 24px rgba(61,79,60,0.10);">

    <!-- Header -->
    <div style="background:#8aab85;padding:36px 40px 28px;text-align:center;">
        <div style="font-size:11px;letter-spacing:0.35em;text-transform:uppercase;color:rgba(255,255,255,0.75);margin-bottom:8px;">Club Pilates San Juan</div>
        <div style="font-size:28px;color:white;font-weight:300;letter-spacing:0.05em;">Bienvenida,<br><strong style="font-weight:500">{nombre}</strong></div>
    </div>

    <!-- Cuerpo -->
    <div style="padding:32px 40px;">
        <p style="font-size:15px;color:#3d4f3c;line-height:1.7;margin:0 0 16px;">
            Nos alegra mucho que te hayas sumado a nuestra comunidad 🌿<br>
            En Club Pilates San Juan trabajamos para que cada clase sea un espacio de bienestar, movimiento y conexión con tu cuerpo.
        </p>

        {plan_block}

        <!-- Cómo agendar -->
        <div style="margin:28px 0 0;">
            <div style="font-size:11px;letter-spacing:0.2em;text-transform:uppercase;color:#7a8f79;margin-bottom:12px;">¿Cómo agendar tu turno?</div>

            <table cellpadding="0" cellspacing="0" border="0" width="100%" style="margin-bottom:14px;">
                <tr>
                    <td width="44" valign="top" style="padding-right:12px;">
                        <div style="background:#eaf3e8;border-radius:50%;width:36px;height:36px;text-align:center;line-height:36px;font-size:16px;">💬</div>
                    </td>
                    <td valign="top">
                        <div style="font-size:14px;font-weight:500;color:#3d4f3c;padding-top:2px;">Por WhatsApp</div>
                        <div style="font-size:13px;color:#7a8f79;margin-top:3px;">Envianos un mensaje al <a href="https://wa.me/542645797486" style="color:#8aab85;font-weight:500;text-decoration:none;">+54 9 264 579-7486</a> indicando el día y horario que preferís.</div>
                    </td>
                </tr>
            </table>

            <table cellpadding="0" cellspacing="0" border="0" width="100%" style="margin-bottom:14px;">
                <tr>
                    <td width="44" valign="top" style="padding-right:12px;">
                        <div style="background:#eaf3e8;border-radius:50%;width:36px;height:36px;text-align:center;line-height:36px;font-size:16px;">📅</div>
                    </td>
                    <td valign="top">
                        <div style="font-size:14px;font-weight:500;color:#3d4f3c;padding-top:2px;">Horarios disponibles</div>
                        <div style="font-size:13px;color:#7a8f79;margin-top:3px;">Lunes a viernes de 8:00 a 21:00 hs · Sábados de 9:00 a 12:00 hs</div>
                    </td>
                </tr>
            </table>

            <table cellpadding="0" cellspacing="0" border="0" width="100%">
                <tr>
                    <td width="44" valign="top" style="padding-right:12px;">
                        <div style="background:#eaf3e8;border-radius:50%;width:36px;height:36px;text-align:center;line-height:36px;font-size:16px;">📍</div>
                    </td>
                    <td valign="top">
                        <div style="font-size:14px;font-weight:500;color:#3d4f3c;padding-top:2px;">Dónde estamos</div>
                        <div style="font-size:13px;color:#7a8f79;margin-top:3px;">San Roque Sur 1044, Rawson, San Juan</div>
                    </td>
                </tr>
            </table>
        </div>

        <!-- Importante -->
        <div style="background:#f7f4ef;border-radius:6px;padding:14px 18px;margin-top:28px;font-size:12px;color:#7a8f79;line-height:1.6;">
            <strong style="color:#3d4f3c;">Recordá:</strong> Los planes son mensuales e intransferibles.
            Si necesitás cancelar un turno, avisanos con al menos 2 horas de anticipación por WhatsApp.
        </div>
    </div>

    <!-- Footer -->
    <div style="border-top:1px solid #eaf3e8;padding:20px 40px;text-align:center;">
        <div style="font-size:12px;color:#b5c9b1;letter-spacing:0.1em;">Club Pilates San Juan &nbsp;·&nbsp; clubpilatesanjuan@gmail.com</div>
    </div>

</div>
</body>
</html>'''


def send_welcome_email(nombre, apellido, email_dest, plan):
    """Envía el email de bienvenida en un hilo separado para no bloquear la respuesta."""
    if not EMAIL_ENABLED or not email_dest:
        return

    def _send():
        try:
            msg = MIMEMultipart('alternative')
            msg['Subject'] = f'¡Bienvenida a Club Pilates San Juan, {nombre}! 🌿'
            msg['From']    = f'Club Pilates San Juan <{EMAIL_FROM}>'
            msg['To']      = email_dest

            html = _build_welcome_html(nombre, apellido, plan)
            msg.attach(MIMEText(html, 'html', 'utf-8'))

            with smtplib.SMTP('smtp.gmail.com', 587) as server:
                server.starttls()
                server.login(EMAIL_FROM, EMAIL_PASSWORD)
                server.sendmail(EMAIL_FROM, email_dest, msg.as_string())

            print(f'[email] Bienvenida enviada a {email_dest}')
        except Exception as e:
            print(f'[email] Error al enviar a {email_dest}: {e}')

    threading.Thread(target=_send, daemon=True).start()


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

        # Migración: quitar UNIQUE de slot_key para permitir hasta 5 reservas por turno
        schema = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='reservas'"
        ).fetchone()
        if schema and 'UNIQUE' in schema[0].upper():
            conn.execute('ALTER TABLE reservas RENAME TO reservas_old')
            conn.execute('''
                CREATE TABLE reservas (
                    id         INTEGER PRIMARY KEY AUTOINCREMENT,
                    slot_key   TEXT    NOT NULL,
                    nombre     TEXT    NOT NULL,
                    apellido   TEXT    NOT NULL,
                    tel        TEXT    NOT NULL,
                    alumna_id  INTEGER REFERENCES alumnas(id) ON DELETE SET NULL,
                    created_at DATETIME DEFAULT (datetime('now','-3 hours'))
                )
            ''')
            conn.execute('INSERT INTO reservas SELECT id, slot_key, nombre, apellido, tel, alumna_id, created_at FROM reservas_old')
            conn.execute('DROP TABLE reservas_old')

        # Tabla para el estado de conversaciones del bot
        conn.execute('''
            CREATE TABLE IF NOT EXISTS conversaciones (
                telefono   TEXT PRIMARY KEY,
                estado     TEXT DEFAULT 'MENU',
                datos      TEXT DEFAULT '{}',
                updated_at DATETIME DEFAULT (datetime('now','-3 hours'))
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
                    'SELECT * FROM reservas WHERE slot_key BETWEEN ? AND ? ORDER BY slot_key, id',
                    (desde, hasta + '_99')
                ).fetchall()
            else:
                rows = conn.execute('SELECT * FROM reservas ORDER BY slot_key, id').fetchall()

        # Cada slot_key → lista de reservas (máx 5)
        result = {}
        for row in rows:
            k = row['slot_key']
            if k not in result:
                result[k] = []
            result[k].append({
                'id':        row['id'],
                'nombre':    row['nombre'],
                'apellido':  row['apellido'],
                'tel':       row['tel'],
                'alumna_id': row['alumna_id'],
                'createdAt': row['created_at']
            })
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
            count = conn.execute(
                'SELECT COUNT(*) FROM reservas WHERE slot_key = ?', (slot_key,)
            ).fetchone()[0]
            if count >= 5:
                return jsonify({'error': 'Turno completo (máximo 5 alumnas)'}), 409
            conn.execute(
                'INSERT INTO reservas (slot_key, nombre, apellido, tel, alumna_id) VALUES (?, ?, ?, ?, ?)',
                (slot_key, nombre, apellido, tel, alumna_id if alumna_id else None)
            )
            conn.commit()
        return jsonify({'ok': True}), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/reservas/<int:reserva_id>', methods=['DELETE'])
@login_required
def delete_reserva(reserva_id):
    try:
        with get_db() as conn:
            conn.execute('DELETE FROM reservas WHERE id = ?', (reserva_id,))
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

        # Enviar email de bienvenida si tiene email (no bloquea la respuesta)
        if email:
            send_welcome_email(nombre, apellido, email, plan)

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


# ── Bot de WhatsApp ───────────────────────────────────
#
# Horario del estudio (Python weekday: Lun=0, Mar=1 … Sáb=5, Dom=6)
HORARIO_BOT = {
    0: (8, 21),   # Lunes
    1: (8, 21),   # Martes
    2: (8, 21),   # Miércoles
    3: (8, 21),   # Jueves
    4: (8, 21),   # Viernes
    5: (9, 12),   # Sábado
}
MAX_POR_TURNO = 5
DIAS_ES_BOT   = ['Lunes','Martes','Miércoles','Jueves','Viernes','Sábado','Domingo']
PLANES_BOT    = {
    '1': ('plan8',      'Plan 8 clases – 2 veces por semana'),
    '2': ('plan4',      'Plan 4 clases – 1 vez por semana'),
    '3': ('individual', 'Clase individual'),
    '4': (None,         'Sin plan por ahora'),
}

# ── Helpers de DB para el bot ─────────────────────────

def _slot_key_bot(d, h):
    return f"{d.strftime('%Y-%m-%d')}_{h:02d}"

def _get_conv(tel):
    try:
        with get_db() as conn:
            row = conn.execute(
                'SELECT estado, datos FROM conversaciones WHERE telefono=?', (tel,)
            ).fetchone()
        if row:
            return row['estado'], json.loads(row['datos'])
    except Exception:
        pass
    return 'MENU', {}

def _set_conv(tel, estado, datos=None):
    if datos is None:
        datos = {}
    with get_db() as conn:
        conn.execute('''
            INSERT INTO conversaciones (telefono, estado, datos)
            VALUES (?, ?, ?)
            ON CONFLICT(telefono) DO UPDATE SET
                estado     = excluded.estado,
                datos      = excluded.datos,
                updated_at = datetime('now','-3 hours')
        ''', (tel, estado, json.dumps(datos, ensure_ascii=False)))
        conn.commit()

def _normalizar_tel(raw):
    """'whatsapp:+5492645797486' → '2645797486' (últimos 10 dígitos)"""
    digits = ''.join(c for c in raw if c.isdigit())
    return digits[-10:] if len(digits) >= 10 else digits

def _buscar_alumna_por_tel(tel_normalizado):
    with get_db() as conn:
        rows = conn.execute(
            'SELECT * FROM alumnas WHERE activa=1 ORDER BY id'
        ).fetchall()
        for r in rows:
            if r['tel'] and _normalizar_tel(str(r['tel'])) == tel_normalizado:
                return dict(r)
    return None

def _get_dias_disponibles():
    """Próximos 6 días hábiles a partir de hoy."""
    dias, d = [], date.today()
    for _ in range(21):
        if d.weekday() in HORARIO_BOT:
            dias.append(d)
        if len(dias) >= 6:
            break
        d += timedelta(days=1)
    return dias

def _get_horas_disponibles(fecha):
    wd = fecha.weekday()
    if wd not in HORARIO_BOT:
        return []
    start, end = HORARIO_BOT[wd]
    disponibles = []
    with get_db() as conn:
        for h in range(start, end):
            key   = _slot_key_bot(fecha, h)
            count = conn.execute(
                'SELECT COUNT(*) FROM reservas WHERE slot_key=?', (key,)
            ).fetchone()[0]
            if count < MAX_POR_TURNO:
                disponibles.append(h)
    return disponibles

def _hacer_reserva_bot(slot_key, nombre, apellido, tel, alumna_id):
    with get_db() as conn:
        count = conn.execute(
            'SELECT COUNT(*) FROM reservas WHERE slot_key=?', (slot_key,)
        ).fetchone()[0]
        if count >= MAX_POR_TURNO:
            raise Exception('Turno completo')
        conn.execute(
            'INSERT INTO reservas (slot_key, nombre, apellido, tel, alumna_id) VALUES (?,?,?,?,?)',
            (slot_key, nombre, apellido, tel, alumna_id)
        )
        conn.commit()

def _responder_ia(pregunta):
    try:
        import anthropic as ant
        client = ant.Anthropic(api_key=ANTHROPIC_API_KEY)
        msg = client.messages.create(
            model='claude-haiku-4-5-20251001',
            max_tokens=250,
            system=(
                'Sos el asistente virtual de Club Pilates San Juan, Argentina. '
                'Respondé de forma amable, breve y en español rioplatense. Máximo 3 oraciones. '
                'Datos del estudio: San Roque Sur 1044, Rawson, San Juan. '
                'Horarios: Lunes a Viernes 8-21hs, Sábados 9-12hs. '
                'Planes: Plan 8 clases (2×semana), Plan 4 clases (1×semana), Clase individual. '
                'WhatsApp: +54 9 264 579-7486. Email: clubpilatesanjuan@gmail.com. '
                'Si preguntan algo que no sabés, deciles que se contacten directamente.'
            ),
            messages=[{'role': 'user', 'content': pregunta}]
        )
        return msg.content[0].text
    except Exception as e:
        print(f'[bot-ia] Error: {e}')
        return 'Lo siento, no puedo responder en este momento. Contactanos directamente al +54 9 264 579-7486. 🌿'

# ── Mensajes del bot ──────────────────────────────────

def _msg_menu(alumna=None):
    saludo = f'¡Hola, *{alumna["nombre"]}*!' if alumna else '¡Hola!'
    return (f'{saludo} 👋 Bienvenida a *Club Pilates San Juan* 🌿\n\n'
            '¿En qué puedo ayudarte?\n\n'
            '*1* · 📅 Reservar un turno\n'
            '*2* · ❌ Cancelar un turno\n'
            '*3* · 🗓 Ver mis turnos\n'
            '*4* · 🕐 Consultar horarios\n'
            '*5* · 💬 Otra consulta\n\n'
            'Respondé con el número de la opción.')

def _msg_dias(dias):
    txt = '📅 *¿Qué día querés reservar?*\n\n'
    for i, d in enumerate(dias, 1):
        horas   = _get_horas_disponibles(d)
        lugares = len(horas)
        emoji   = '🟢' if lugares > 2 else ('🟡' if lugares > 0 else '🔴')
        txt += f'*{i}* · {emoji} {DIAS_ES_BOT[d.weekday()]} {d.strftime("%-d/%m")} — {lugares} lugar{"es" if lugares != 1 else ""}\n'
    txt += '\nRespondé con el número del día.'
    return txt

# ── Lógica principal del bot ──────────────────────────

def procesar_mensaje_bot(tel_raw, msg_in):
    tel    = _normalizar_tel(tel_raw)
    msg    = msg_in.strip()
    estado, datos = _get_conv(tel)
    alumna = _buscar_alumna_por_tel(tel)

    # Palabras clave que siempre vuelven al menú
    if msg.lower() in ('menu', 'menú', 'inicio', 'start', 'hola', 'buenas',
                        'buenos días', 'buenas tardes', 'buenas noches', 'hi'):
        _set_conv(tel, 'MENU', {})
        return _msg_menu(alumna)

    # ── MENU ──────────────────────────────────────────
    if estado == 'MENU':
        if msg == '1':
            dias = _get_dias_disponibles()
            _set_conv(tel, 'RESERVAR_DIA', {'dias': [d.isoformat() for d in dias]})
            return _msg_dias(dias)

        elif msg == '2':
            if not alumna:
                return ('Tu número no está registrado. '
                        'Escribí *menú* para reservar tu primer turno. 🌿')
            return _flujo_ver_turnos_cancelar(tel, alumna, modo='cancelar')

        elif msg == '3':
            if not alumna:
                return 'Tu número no está registrado. Escribí *1* para reservar tu primer turno.'
            return _flujo_ver_turnos_cancelar(tel, alumna, modo='ver')

        elif msg == '4':
            _set_conv(tel, 'MENU', {})
            return ('🕐 *Horarios de Club Pilates San Juan*\n\n'
                    '📍 San Roque Sur 1044, Rawson\n\n'
                    '• Lunes a Viernes: 8:00 a 21:00 hs\n'
                    '• Sábados: 9:00 a 12:00 hs\n\n'
                    'Escribí *menú* para volver al inicio.')

        elif msg == '5':
            _set_conv(tel, 'CONSULTA_IA', {})
            return ('🤖 Contame tu consulta y te respondo enseguida.\n\n'
                    '_(Escribí *menú* para volver al inicio en cualquier momento)_')

        else:
            return _msg_menu(alumna)

    # ── RESERVAR: elegir día ──────────────────────────
    elif estado == 'RESERVAR_DIA':
        dias = [date.fromisoformat(s) for s in datos.get('dias', [])]
        try:
            idx = int(msg) - 1
            assert 0 <= idx < len(dias)
        except (ValueError, AssertionError):
            return f'Por favor respondé un número del 1 al {len(dias)}.'

        dia_elegido = dias[idx]
        horas = _get_horas_disponibles(dia_elegido)
        if not horas:
            return (f'😔 Ya no quedan lugares para el {DIAS_ES_BOT[dia_elegido.weekday()]}.\n'
                    'Escribí *menú* para elegir otro día.')

        txt = (f'🕐 *Horarios disponibles — '
               f'{DIAS_ES_BOT[dia_elegido.weekday()]} {dia_elegido.strftime("%-d/%m")}*\n\n')
        for i, h in enumerate(horas, 1):
            txt += f'*{i}* · {h:02d}:00 — {h+1:02d}:00 hs\n'
        txt += '\nRespondé con el número del horario.'

        datos.update({'dia': dia_elegido.isoformat(), 'horas': horas})
        _set_conv(tel, 'RESERVAR_HORA', datos)
        return txt

    # ── RESERVAR: elegir hora ─────────────────────────
    elif estado == 'RESERVAR_HORA':
        horas = datos.get('horas', [])
        try:
            idx = int(msg) - 1
            assert 0 <= idx < len(horas)
        except (ValueError, AssertionError):
            return f'Por favor respondé un número del 1 al {len(horas)}.'

        hora  = horas[idx]
        dia   = date.fromisoformat(datos['dia'])
        datos.update({'hora': hora})
        _set_conv(tel, 'RESERVAR_CONFIRMAR', datos)

        return (f'✅ *Confirmá tu reserva:*\n\n'
                f'📅 {DIAS_ES_BOT[dia.weekday()]} {dia.strftime("%-d/%m/%Y")}\n'
                f'🕐 {hora:02d}:00 — {hora+1:02d}:00 hs\n\n'
                f'Respondé *sí* para confirmar o *no* para elegir otro horario.')

    # ── RESERVAR: confirmar ───────────────────────────
    elif estado == 'RESERVAR_CONFIRMAR':
        if msg.lower() in ('si', 'sí', 's', 'yes', '1'):
            dia  = date.fromisoformat(datos['dia'])
            hora = datos['hora']
            key  = _slot_key_bot(dia, hora)

            if alumna:
                try:
                    _hacer_reserva_bot(key, alumna['nombre'], alumna['apellido'],
                                       alumna['tel'] or tel, alumna['id'])
                    _set_conv(tel, 'MENU', {})
                    return (f'🎉 *¡Turno confirmado, {alumna["nombre"]}!*\n\n'
                            f'📅 {DIAS_ES_BOT[dia.weekday()]} {dia.strftime("%-d/%m/%Y")}\n'
                            f'🕐 {hora:02d}:00 — {hora+1:02d}:00 hs\n\n'
                            '¡Nos vemos pronto! 🌿\n'
                            'Escribí *2* si necesitás cancelar.')
                except Exception as e:
                    _set_conv(tel, 'MENU', {})
                    return f'😔 No se pudo reservar: {e}\nEscribí *menú* para intentar de nuevo.'
            else:
                # Nueva alumna → pedir datos
                _set_conv(tel, 'REG_NOMBRE', datos)
                return ('¡Genial! Como es tu primera vez, necesito algunos datos 📝\n\n'
                        '¿Cuál es tu *nombre*?')

        elif msg.lower() in ('no', 'n'):
            dias = _get_dias_disponibles()
            _set_conv(tel, 'RESERVAR_DIA', {'dias': [d.isoformat() for d in dias]})
            return _msg_dias(dias)
        else:
            return 'Respondé *sí* para confirmar o *no* para elegir otro horario.'

    # ── REGISTRO: nombre ──────────────────────────────
    elif estado == 'REG_NOMBRE':
        datos['reg_nombre'] = msg.strip().title()
        _set_conv(tel, 'REG_APELLIDO', datos)
        return f'¡Hola, *{datos["reg_nombre"]}*! ¿Y tu *apellido*?'

    # ── REGISTRO: apellido ────────────────────────────
    elif estado == 'REG_APELLIDO':
        datos['reg_apellido'] = msg.strip().title()
        _set_conv(tel, 'REG_PLAN', datos)
        return ('Perfecto! ¿Qué *plan* te interesa?\n\n'
                '*1* · Plan 8 clases – 2 veces por semana\n'
                '*2* · Plan 4 clases – 1 vez por semana\n'
                '*3* · Clase individual\n'
                '*4* · Sin plan por ahora\n')

    # ── REGISTRO: plan → crear alumna + reservar ──────
    elif estado == 'REG_PLAN':
        if msg not in PLANES_BOT:
            return 'Respondé *1*, *2*, *3* o *4* para elegir tu plan.'

        plan_key, plan_label = PLANES_BOT[msg]
        dia  = date.fromisoformat(datos['dia'])
        hora = datos['hora']
        key  = _slot_key_bot(dia, hora)

        try:
            with get_db() as conn:
                cur = conn.execute(
                    'INSERT INTO alumnas (nombre, apellido, tel, plan) VALUES (?,?,?,?)',
                    (datos['reg_nombre'], datos['reg_apellido'], tel, plan_key)
                )
                conn.commit()
                alumna_id = cur.lastrowid

            _hacer_reserva_bot(key, datos['reg_nombre'], datos['reg_apellido'], tel, alumna_id)
            _set_conv(tel, 'MENU', {})
            return (f'🎉 *¡Todo listo, {datos["reg_nombre"]}!*\n\n'
                    f'✅ Quedaste registrada · *{plan_label}*\n\n'
                    f'📅 Tu primer turno:\n'
                    f'{DIAS_ES_BOT[dia.weekday()]} {dia.strftime("%-d/%m/%Y")} · '
                    f'{hora:02d}:00 — {hora+1:02d}:00 hs\n\n'
                    '¡Nos vemos pronto! 🌿\n'
                    'Escribí *menú* cuando necesites reservar o cancelar un turno.')
        except Exception as e:
            _set_conv(tel, 'MENU', {})
            return f'Hubo un error al registrarte. Contactanos directamente. ({e})'

    # ── CANCELAR: elegir turno ────────────────────────
    elif estado == 'CANCELAR_TURNO':
        turnos = datos.get('turnos', [])
        if msg.lower() in ('no', 'n', 'ninguno', 'salir'):
            _set_conv(tel, 'MENU', {})
            return 'De acuerdo. Escribí *menú* si necesitás otra cosa. 🌿'
        try:
            idx = int(msg) - 1
            assert 0 <= idx < len(turnos)
        except (ValueError, AssertionError):
            return f'Respondé un número del 1 al {len(turnos)}, o *no* para salir.'

        turno = turnos[idx]
        try:
            with get_db() as conn:
                conn.execute('DELETE FROM reservas WHERE id=?', (turno['id'],))
                conn.commit()
            dia  = date.fromisoformat(turno['slot_key'][:10])
            hora = turno['slot_key'][-2:]
            _set_conv(tel, 'MENU', {})
            return (f'✅ *Turno cancelado:*\n'
                    f'{DIAS_ES_BOT[dia.weekday()]} {dia.strftime("%-d/%m")} · {hora}:00 hs\n\n'
                    'Escribí *1* si querés reservar otro turno. 🌿')
        except Exception:
            _set_conv(tel, 'MENU', {})
            return '😔 No pude cancelar el turno. Contactanos directamente.'

    # ── CONSULTA IA ───────────────────────────────────
    elif estado == 'CONSULTA_IA':
        respuesta = _responder_ia(msg)
        return f'{respuesta}\n\n_(Escribí *menú* para volver al inicio)_'

    # ── Default ───────────────────────────────────────
    else:
        _set_conv(tel, 'MENU', {})
        return _msg_menu(alumna)


def _flujo_ver_turnos_cancelar(tel, alumna, modo='ver'):
    today = date.today().isoformat() + '_00'
    with get_db() as conn:
        rows = conn.execute(
            '''SELECT id, slot_key FROM reservas
               WHERE alumna_id=? AND slot_key >= ?
               ORDER BY slot_key LIMIT 5''',
            (alumna['id'], today)
        ).fetchall()

    if not rows:
        return (f'No tenés turnos próximos reservados, *{alumna["nombre"]}*. '
                'Escribí *1* para reservar uno. 🌿')

    if modo == 'ver':
        txt = f'📅 *Tus próximos turnos, {alumna["nombre"]}:*\n\n'
        for r in rows:
            dia  = date.fromisoformat(r['slot_key'][:10])
            hora = r['slot_key'][-2:]
            txt += f'• {DIAS_ES_BOT[dia.weekday()]} {dia.strftime("%-d/%m")} · {hora}:00 hs\n'
        txt += '\nEscribí *menú* para volver al inicio.'
        return txt
    else:  # cancelar
        txt = f'📅 *¿Cuál turno querés cancelar, {alumna["nombre"]}?*\n\n'
        turnos = []
        for i, r in enumerate(rows, 1):
            dia  = date.fromisoformat(r['slot_key'][:10])
            hora = r['slot_key'][-2:]
            txt += f'*{i}* · {DIAS_ES_BOT[dia.weekday()]} {dia.strftime("%-d/%m")} · {hora}:00 hs\n'
            turnos.append({'id': r['id'], 'slot_key': r['slot_key']})
        txt += '\nRespondé con el número, o *no* para salir.'
        _set_conv(tel, 'CANCELAR_TURNO', {'turnos': turnos})
        return txt


@app.route('/webhook/whatsapp', methods=['POST'])
def whatsapp_webhook():
    try:
        from twilio.twiml.messaging_response import MessagingResponse
    except ImportError:
        return 'twilio no instalado', 500

    tel_raw = request.form.get('From', '')
    msg_in  = request.form.get('Body', '').strip()

    print(f'[bot] {tel_raw}: {msg_in}')

    try:
        respuesta = procesar_mensaje_bot(tel_raw, msg_in)
    except Exception as e:
        print(f'[bot] Error procesando mensaje: {e}')
        respuesta = '😔 Ocurrió un error. Por favor intentá de nuevo o contactanos directamente.'

    resp = MessagingResponse()
    resp.message(respuesta)
    return str(resp), 200, {'Content-Type': 'text/xml'}


# ── Arranque ──────────────────────────────────────────
if __name__ == '__main__':
    app.run(debug=True)
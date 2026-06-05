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
EMAIL_PASSWORD = 'xxxx xxxx xxxx xxxx'   # ← pegá acá tu App Password de 16 caracteres
EMAIL_ENABLED  = True

# PIN exclusivo para la sección Finanzas (solo vos y tu socio)
FINANZAS_PIN = '1234'   # ← cambiá esto por el PIN que quieran usar

# ── Configuración del Bot de WhatsApp (Twilio) ────────
# Credenciales desde twilio.com/console
TWILIO_ACCOUNT_SID  = 'ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx'  # ← tu Account SID
TWILIO_AUTH_TOKEN   = 'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx'    # ← tu Auth Token
TWILIO_WA_NUMBER    = 'whatsapp:+14155238886'               # ← número sandbox de Twilio

# API Key de Anthropic para respuestas con IA
# Obtené una en: console.anthropic.com
ANTHROPIC_API_KEY   = 'sk-ant-xxxxxxxxxxxx'                 # ← tu API key

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
    'plan12':     ('Plan 12 clases',     '3 clases por semana', '$55.000'),
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

        # Tabla de horarios fijos (patrones de recurrencia)
        conn.execute('''
            CREATE TABLE IF NOT EXISTS horarios_fijos (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                alumna_id   INTEGER NOT NULL REFERENCES alumnas(id) ON DELETE CASCADE,
                dias_semana TEXT    NOT NULL,
                hora        INTEGER NOT NULL,
                tipo        TEXT    NOT NULL CHECK(tipo IN ('mensual','anual')),
                mes_inicio  TEXT    NOT NULL,
                mes_fin     TEXT    NOT NULL,
                activo      INTEGER DEFAULT 1,
                created_at  DATETIME DEFAULT (datetime('now','-3 hours'))
            )
        ''')

        # Migración: agregar horario_id a reservas para rastrear origen
        cols_res2 = [r[1] for r in conn.execute("PRAGMA table_info(reservas)").fetchall()]
        if 'horario_id' not in cols_res2:
            conn.execute("ALTER TABLE reservas ADD COLUMN horario_id INTEGER REFERENCES horarios_fijos(id) ON DELETE SET NULL")

        # Tabla de instructores
        conn.execute('''
            CREATE TABLE IF NOT EXISTS instructores (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre       TEXT    NOT NULL,
                apellido     TEXT    NOT NULL,
                tel          TEXT,
                email        TEXT,
                tarifa_hora  REAL    DEFAULT 0,
                notas        TEXT,
                activo       INTEGER DEFAULT 1,
                created_at   DATETIME DEFAULT (datetime('now','-3 hours'))
            )
        ''')

        # Tabla de horas trabajadas
        conn.execute('''
            CREATE TABLE IF NOT EXISTS horas_trabajadas (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                instructor_id  INTEGER NOT NULL REFERENCES instructores(id) ON DELETE CASCADE,
                fecha          TEXT    NOT NULL,
                hora_inicio    TEXT    NOT NULL,
                hora_fin       TEXT    NOT NULL,
                tipo           TEXT    NOT NULL DEFAULT 'clase',
                notas          TEXT,
                created_at     DATETIME DEFAULT (datetime('now','-3 hours'))
            )
        ''')

        # Migración: agregar pin a instructores si no existe
        cols_inst = [r[1] for r in conn.execute("PRAGMA table_info(instructores)").fetchall()]
        if 'pin' not in cols_inst:
            conn.execute("ALTER TABLE instructores ADD COLUMN pin TEXT DEFAULT '0000'")

        conn.commit()

def limpiar_datos_viejos():
    """
    Limpieza automática al arrancar:
      - Reservas con más de 2 meses → se eliminan
      - Conversaciones del bot sin actividad hace más de 7 días → se eliminan
    Nunca toca alumnas ni movimientos.
    """
    try:
        with get_db() as conn:
            res = conn.execute('''
                DELETE FROM reservas
                WHERE slot_key < strftime('%Y-%m-%d', datetime('now', '-2 months', '-3 hours'))
            ''')
            borradas_res = res.rowcount

            res2 = conn.execute('''
                DELETE FROM conversaciones
                WHERE updated_at < datetime('now', '-7 days', '-3 hours')
            ''')
            borradas_conv = res2.rowcount

            conn.commit()

        if borradas_res or borradas_conv:
            print(f'[limpieza] {borradas_res} reservas viejas y {borradas_conv} conversaciones eliminadas')
    except Exception as e:
        print(f'[limpieza] Error: {e}')

# Inicializar DB y limpiar al arrancar
init_db()
limpiar_datos_viejos()

# ── Rutas principales ─────────────────────────────────
@app.route('/favicon.ico')
def favicon():
    return redirect(url_for('static', filename='img/favicon.svg'))

@app.route('/api/finanzas/verificar', methods=['POST'])
@login_required
def verificar_finanzas():
    data = request.get_json()
    pin  = data.get('pin', '')
    if pin == FINANZAS_PIN:
        session['finanzas_ok'] = True
        return jsonify({'ok': True})
    return jsonify({'error': 'PIN incorrecto'}), 403

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

@app.route('/api/reservas/bulk', methods=['POST'])
@login_required
def create_reservas_bulk():
    """
    Crea reservas recurrentes para una alumna durante un mes completo.
    Body: { alumna_id, dias_semana: [0,2,4], hora: 17, mes: "2026-05" }
    dias_semana: 0=Lunes, 1=Martes, ... 5=Sábado
    """
    data        = request.get_json()
    alumna_id   = data.get('alumna_id')
    dias_semana = data.get('dias_semana', [])   # lista de ints 0-5
    hora        = int(data.get('hora', 0))
    mes         = data.get('mes', '')            # "YYYY-MM"

    if not alumna_id or not dias_semana or not mes:
        return jsonify({'error': 'Faltan campos obligatorios'}), 400

    try:
        year, month = int(mes[:4]), int(mes[5:7])
    except (ValueError, IndexError):
        return jsonify({'error': 'Formato de mes inválido'}), 400

    # Horario válido del estudio
    HORARIO = {0:(8,21), 1:(8,21), 2:(8,21), 3:(8,21), 4:(8,21), 5:(9,12)}
    for dia in dias_semana:
        sc = HORARIO.get(dia)
        if sc and not (sc[0] <= hora < sc[1]):
            return jsonify({'error': f'El horario {hora:02d}:00 no está disponible ese día'}), 400

    try:
        with get_db() as conn:
            alumna = conn.execute(
                'SELECT nombre, apellido, tel FROM alumnas WHERE id=?', (alumna_id,)
            ).fetchone()
            if not alumna:
                return jsonify({'error': 'Alumna no encontrada'}), 404

            nombre   = alumna['nombre']
            apellido = alumna['apellido']
            tel      = alumna['tel'] or ''

            creadas   = []
            saltadas  = []   # turno lleno
            existentes = []  # ya tenía reserva

            # Iterar todos los días del mes
            import calendar as cal
            _, dias_en_mes = cal.monthrange(year, month)

            for day in range(1, dias_en_mes + 1):
                fecha = date(year, month, day)
                # Python weekday: 0=Lunes … 5=Sábado, 6=Domingo
                if fecha.weekday() not in [int(d) for d in dias_semana]:
                    continue

                slot_key = f"{fecha.strftime('%Y-%m-%d')}_{hora:02d}"

                # ¿Ya tiene reserva en ese slot?
                ya_tiene = conn.execute(
                    'SELECT id FROM reservas WHERE slot_key=? AND alumna_id=?',
                    (slot_key, alumna_id)
                ).fetchone()
                if ya_tiene:
                    existentes.append(slot_key)
                    continue

                # ¿Hay lugar (máx 5)?
                count = conn.execute(
                    'SELECT COUNT(*) FROM reservas WHERE slot_key=?', (slot_key,)
                ).fetchone()[0]
                if count >= 5:
                    saltadas.append(slot_key)
                    continue

                conn.execute(
                    'INSERT INTO reservas (slot_key, nombre, apellido, tel, alumna_id) VALUES (?,?,?,?,?)',
                    (slot_key, nombre, apellido, tel, alumna_id)
                )
                creadas.append(slot_key)

            conn.commit()

        return jsonify({
            'ok':        True,
            'creadas':   len(creadas),
            'saltadas':  len(saltadas),
            'existentes': len(existentes),
            'detalle':   creadas
        }), 201

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


# ── API de Horarios Fijos ─────────────────────────────

def _generar_reservas_desde_patron(conn, horario_id, alumna_id, dias_semana,
                                    hora, mes_inicio, mes_fin, nombre, apellido, tel):
    """Genera reservas para todos los meses entre mes_inicio y mes_fin."""
    import calendar as cal
    from datetime import date

    HORARIO_EST = {0:(8,21),1:(8,21),2:(8,21),3:(8,21),4:(8,21),5:(9,12)}
    creadas = saltadas = existentes = 0

    y_ini, m_ini = int(mes_inicio[:4]), int(mes_inicio[5:7])
    y_fin, m_fin = int(mes_fin[:4]),    int(mes_fin[5:7])

    y, m = y_ini, m_ini
    while (y, m) <= (y_fin, m_fin):
        _, dias_en_mes = cal.monthrange(y, m)
        for day in range(1, dias_en_mes + 1):
            fecha = date(y, m, day)
            wd    = fecha.weekday()           # 0=Lun…5=Sáb
            if wd not in dias_semana:
                continue
            sc = HORARIO_EST.get(wd)
            if not sc or not (sc[0] <= hora < sc[1]):
                continue
            slot_key = f"{fecha.strftime('%Y-%m-%d')}_{hora:02d}"

            ya = conn.execute(
                'SELECT id FROM reservas WHERE slot_key=? AND alumna_id=?',
                (slot_key, alumna_id)
            ).fetchone()
            if ya:
                existentes += 1
                continue

            count = conn.execute(
                'SELECT COUNT(*) FROM reservas WHERE slot_key=?', (slot_key,)
            ).fetchone()[0]
            if count >= 5:
                saltadas += 1
                continue

            conn.execute(
                'INSERT INTO reservas (slot_key, nombre, apellido, tel, alumna_id, horario_id) VALUES (?,?,?,?,?,?)',
                (slot_key, nombre, apellido, tel, alumna_id, horario_id)
            )
            creadas += 1

        m += 1
        if m > 12:
            m = 1
            y += 1

    return creadas, saltadas, existentes


@app.route('/api/horarios-fijos', methods=['GET'])
@login_required
def get_horarios_fijos():
    try:
        with get_db() as conn:
            rows = conn.execute('''
                SELECT h.*, a.nombre || ' ' || a.apellido AS alumna_nombre, a.plan
                FROM horarios_fijos h
                JOIN alumnas a ON h.alumna_id = a.id
                WHERE h.activo = 1
                ORDER BY h.mes_inicio DESC, a.apellido
            ''').fetchall()
        return jsonify([dict(r) for r in rows])
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/horarios-fijos', methods=['POST'])
@login_required
def create_horario_fijo():
    data        = request.get_json()
    alumna_id   = data.get('alumna_id')
    dias_semana = [int(d) for d in data.get('dias_semana', [])]
    hora        = int(data.get('hora', 0))
    tipo        = data.get('tipo', 'mensual')
    mes_inicio  = data.get('mes_inicio', '')
    mes_fin     = data.get('mes_fin', '')

    if not all([alumna_id, dias_semana, mes_inicio, mes_fin]):
        return jsonify({'error': 'Faltan campos obligatorios'}), 400

    try:
        with get_db() as conn:
            alumna = conn.execute(
                'SELECT nombre, apellido, tel FROM alumnas WHERE id=?', (alumna_id,)
            ).fetchone()
            if not alumna:
                return jsonify({'error': 'Alumna no encontrada'}), 404

            cur = conn.execute('''
                INSERT INTO horarios_fijos (alumna_id, dias_semana, hora, tipo, mes_inicio, mes_fin)
                VALUES (?,?,?,?,?,?)
            ''', (alumna_id, json.dumps(dias_semana), hora, tipo, mes_inicio, mes_fin))
            horario_id = cur.lastrowid

            creadas, saltadas, existentes = _generar_reservas_desde_patron(
                conn, horario_id, alumna_id, dias_semana, hora,
                mes_inicio, mes_fin, alumna['nombre'], alumna['apellido'], alumna['tel'] or ''
            )
            conn.commit()

        return jsonify({
            'ok': True, 'horario_id': horario_id,
            'creadas': creadas, 'saltadas': saltadas, 'existentes': existentes
        }), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/horarios-fijos/<int:hid>', methods=['PUT'])
@login_required
def update_horario_fijo(hid):
    data        = request.get_json()
    dias_semana = [int(d) for d in data.get('dias_semana', [])]
    hora        = int(data.get('hora', 0))
    tipo        = data.get('tipo', 'mensual')
    mes_inicio  = data.get('mes_inicio', '')
    mes_fin     = data.get('mes_fin', '')

    try:
        from datetime import date
        today_str = date.today().strftime('%Y-%m')

        with get_db() as conn:
            horario = conn.execute(
                'SELECT * FROM horarios_fijos WHERE id=?', (hid,)
            ).fetchone()
            if not horario:
                return jsonify({'error': 'Horario no encontrado'}), 404

            alumna_id = horario['alumna_id']
            alumna    = conn.execute(
                'SELECT nombre, apellido, tel FROM alumnas WHERE id=?', (alumna_id,)
            ).fetchone()

            # Borrar reservas futuras generadas por este horario
            conn.execute('''
                DELETE FROM reservas
                WHERE horario_id=?
                  AND substr(slot_key,1,7) >= ?
            ''', (hid, today_str))

            # Actualizar patrón
            conn.execute('''
                UPDATE horarios_fijos
                SET dias_semana=?, hora=?, tipo=?, mes_inicio=?, mes_fin=?
                WHERE id=?
            ''', (json.dumps(dias_semana), hora, tipo, mes_inicio, mes_fin, hid))

            # Regenerar desde hoy en adelante
            mes_desde = max(mes_inicio, today_str)
            creadas, saltadas, existentes = _generar_reservas_desde_patron(
                conn, hid, alumna_id, dias_semana, hora,
                mes_desde, mes_fin, alumna['nombre'], alumna['apellido'], alumna['tel'] or ''
            )
            conn.commit()

        return jsonify({'ok': True, 'creadas': creadas, 'saltadas': saltadas})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/horarios-fijos/<int:hid>', methods=['DELETE'])
@login_required
def delete_horario_fijo(hid):
    borrar_reservas = request.args.get('borrar_reservas', '0') == '1'
    try:
        from datetime import date
        today_str = date.today().strftime('%Y-%m')
        with get_db() as conn:
            if borrar_reservas:
                conn.execute('''
                    DELETE FROM reservas
                    WHERE horario_id=? AND substr(slot_key,1,7) >= ?
                ''', (hid, today_str))
            conn.execute('UPDATE horarios_fijos SET activo=0 WHERE id=?', (hid,))
            conn.commit()
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ── API de Instructores ───────────────────────────────

@app.route('/api/instructores', methods=['GET'])
@login_required
def get_instructores():
    try:
        with get_db() as conn:
            rows = conn.execute(
                'SELECT * FROM instructores ORDER BY apellido, nombre'
            ).fetchall()
        return jsonify([dict(r) for r in rows])
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/instructores', methods=['POST'])
@login_required
def create_instructor():
    data = request.get_json()
    nombre   = data.get('nombre', '').strip()
    apellido = data.get('apellido', '').strip()
    if not nombre or not apellido:
        return jsonify({'error': 'Nombre y apellido son obligatorios'}), 400
    try:
        with get_db() as conn:
            cur = conn.execute(
                '''INSERT INTO instructores (nombre, apellido, tel, email, tarifa_hora, notas, pin)
                   VALUES (?,?,?,?,?,?,?)''',
                (nombre, apellido,
                 data.get('tel','').strip(),
                 data.get('email','').strip(),
                 float(data.get('tarifa_hora', 0)),
                 data.get('notas','').strip(),
                 data.get('pin', '0000').strip())
            )
            conn.commit()
            row = conn.execute('SELECT * FROM instructores WHERE id=?', (cur.lastrowid,)).fetchone()
        return jsonify(dict(row)), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/instructores/<int:iid>', methods=['PUT'])
@login_required
def update_instructor(iid):
    data = request.get_json()
    try:
        with get_db() as conn:
            conn.execute(
                '''UPDATE instructores SET nombre=?, apellido=?, tel=?, email=?,
                   tarifa_hora=?, notas=?, pin=?, activo=? WHERE id=?''',
                (data.get('nombre','').strip(),
                 data.get('apellido','').strip(),
                 data.get('tel','').strip(),
                 data.get('email','').strip(),
                 float(data.get('tarifa_hora', 0)),
                 data.get('notas','').strip(),
                 data.get('pin','0000').strip(),
                 int(data.get('activo', 1)),
                 iid)
            )
            conn.commit()
            row = conn.execute('SELECT * FROM instructores WHERE id=?', (iid,)).fetchone()
        return jsonify(dict(row))
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/instructores/<int:iid>', methods=['DELETE'])
@login_required
def delete_instructor(iid):
    try:
        with get_db() as conn:
            conn.execute('UPDATE instructores SET activo=0 WHERE id=?', (iid,))
            conn.commit()
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/horas', methods=['GET'])
@login_required
def get_horas():
    mes          = request.args.get('mes', '')
    instructor_id = request.args.get('instructor_id', '')
    try:
        with get_db() as conn:
            q = '''SELECT h.*, i.nombre||' '||i.apellido AS instructor_nombre, i.tarifa_hora
                   FROM horas_trabajadas h
                   JOIN instructores i ON h.instructor_id = i.id
                   WHERE 1=1'''
            params = []
            if mes:
                q += ' AND h.fecha LIKE ?'; params.append(f'{mes}%')
            if instructor_id:
                q += ' AND h.instructor_id = ?'; params.append(int(instructor_id))
            q += ' ORDER BY h.fecha DESC, h.hora_inicio DESC'
            rows = conn.execute(q, params).fetchall()
        return jsonify([dict(r) for r in rows])
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/horas', methods=['POST'])
def create_hora():
    """Pueden llamarlo el admin (login_required omitido) o el instructor con PIN."""
    data          = request.get_json()
    instructor_id = data.get('instructor_id')
    pin           = data.get('pin', '')
    fecha         = data.get('fecha', '').strip()
    hora_inicio   = data.get('hora_inicio', '').strip()
    hora_fin      = data.get('hora_fin', '').strip()
    tipo          = data.get('tipo', 'clase').strip()
    notas         = data.get('notas', '').strip()

    if not all([instructor_id, fecha, hora_inicio, hora_fin]):
        return jsonify({'error': 'Faltan campos obligatorios'}), 400

    try:
        with get_db() as conn:
            # Si no hay sesión admin, verificar que el instructor existe y está activo
            if not session.get('logged_in'):
                inst_check = conn.execute(
                    'SELECT id FROM instructores WHERE id=? AND activo=1', (instructor_id,)
                ).fetchone()
                if not inst_check:
                    return jsonify({'error': 'Instructor no encontrado'}), 403

            # Calcular horas
            from datetime import datetime as dt
            ini = dt.strptime(hora_inicio, '%H:%M')
            fin = dt.strptime(hora_fin,   '%H:%M')
            if fin <= ini:
                return jsonify({'error': 'La hora de fin debe ser mayor a la de inicio'}), 400
            horas = round((fin - ini).seconds / 3600, 2)

            cur = conn.execute(
                '''INSERT INTO horas_trabajadas
                   (instructor_id, fecha, hora_inicio, hora_fin, tipo, notas)
                   VALUES (?,?,?,?,?,?)''',
                (instructor_id, fecha, hora_inicio, hora_fin, tipo, notas)
            )
            conn.commit()
            row = conn.execute(
                '''SELECT h.*, i.nombre||' '||i.apellido AS instructor_nombre, i.tarifa_hora
                   FROM horas_trabajadas h JOIN instructores i ON h.instructor_id=i.id
                   WHERE h.id=?''', (cur.lastrowid,)
            ).fetchone()
        return jsonify(dict(row)), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/horas/<int:hid>', methods=['DELETE'])
@login_required
def delete_hora(hid):
    try:
        with get_db() as conn:
            conn.execute('DELETE FROM horas_trabajadas WHERE id=?', (hid,))
            conn.commit()
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/horas/resumen', methods=['GET'])
@login_required
def resumen_horas():
    mes = request.args.get('mes', '')
    try:
        with get_db() as conn:
            rows = conn.execute('''
                SELECT i.id, i.nombre||' '||i.apellido AS nombre,
                       i.tarifa_hora,
                       COUNT(h.id) AS registros,
                       SUM(
                           (strftime('%H', h.hora_fin)*60 + strftime('%M', h.hora_fin)) -
                           (strftime('%H', h.hora_inicio)*60 + strftime('%M', h.hora_inicio))
                       ) / 60.0 AS total_horas
                FROM instructores i
                LEFT JOIN horas_trabajadas h
                    ON h.instructor_id = i.id AND h.fecha LIKE ?
                WHERE i.activo = 1
                GROUP BY i.id
                ORDER BY i.apellido
            ''', (f'{mes}%',)).fetchall()
        resultado = []
        for r in rows:
            d = dict(r)
            d['total_horas'] = round(d['total_horas'] or 0, 2)
            d['total_pagar'] = round((d['total_horas'] or 0) * (d['tarifa_hora'] or 0), 2)
            resultado.append(d)
        return jsonify(resultado)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/horas/export')
@login_required
def export_horas_excel():
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter
    from io import BytesIO

    mes = request.args.get('mes', '')

    try:
        with get_db() as conn:
            instructores = conn.execute(
                'SELECT * FROM instructores WHERE activo=1 ORDER BY apellido'
            ).fetchall()
            horas = conn.execute('''
                SELECT h.*, i.nombre||' '||i.apellido AS instructor_nombre, i.tarifa_hora
                FROM horas_trabajadas h
                JOIN instructores i ON h.instructor_id = i.id
                WHERE h.fecha LIKE ?
                ORDER BY h.instructor_id, h.fecha, h.hora_inicio
            ''', (f'{mes}%',)).fetchall()

        wb = openpyxl.Workbook()

        # ── Colores ──
        verde      = '7D9979'
        verde_pale = 'EEF3ED'
        oscuro     = '041620'
        blanco     = 'FFFFFF'
        gris       = 'F5F5F5'

        def header_font(bold=True, color=blanco):
            return Font(name='Calibri', bold=bold, color=color, size=11)

        def cell_font(bold=False, color='000000'):
            return Font(name='Calibri', bold=bold, color=color, size=10)

        def fill(hex_color):
            return PatternFill('solid', fgColor=hex_color)

        def thin_border():
            s = Side(style='thin', color='CCCCCC')
            return Border(left=s, right=s, top=s, bottom=s)

        # ── Hoja 1: Resumen ──────────────────────────────
        ws = wb.active
        ws.title = 'Resumen'

        ws.merge_cells('A1:F1')
        ws['A1'] = f'Club Pilates San Juan — Resumen de Horas · {mes}'
        ws['A1'].font = Font(name='Calibri', bold=True, color=blanco, size=13)
        ws['A1'].fill = fill(verde)
        ws['A1'].alignment = Alignment(horizontal='center', vertical='center')
        ws.row_dimensions[1].height = 32

        headers = ['Instructor', 'Registros', 'Horas totales', 'Tarifa/hora', 'Total a pagar']
        for col, h in enumerate(headers, 1):
            c = ws.cell(row=2, column=col, value=h)
            c.font   = header_font(color=blanco)
            c.fill   = fill(oscuro)
            c.alignment = Alignment(horizontal='center', vertical='center')
            c.border = thin_border()
        ws.row_dimensions[2].height = 22

        total_pagar_global = 0
        row_n = 3
        for i, inst in enumerate(instructores):
            horas_inst = [h for h in horas if h['instructor_id'] == inst['id']]
            total_min  = sum(
                (int(h['hora_fin'][:2])*60 + int(h['hora_fin'][3:])) -
                (int(h['hora_inicio'][:2])*60 + int(h['hora_inicio'][3:]))
                for h in horas_inst
            )
            total_h   = round(total_min / 60, 2)
            total_pay = round(total_h * (inst['tarifa_hora'] or 0), 2)
            total_pagar_global += total_pay

            bg = gris if i % 2 == 0 else blanco
            vals = [f"{inst['nombre']} {inst['apellido']}", len(horas_inst),
                    total_h, inst['tarifa_hora'], total_pay]
            for col, val in enumerate(vals, 1):
                c = ws.cell(row=row_n, column=col, value=val)
                c.font   = cell_font()
                c.fill   = fill(bg)
                c.border = thin_border()
                if col >= 3:
                    c.alignment = Alignment(horizontal='right')
                    if col in (4, 5):
                        c.number_format = '"$"#,##0.00'
            row_n += 1

        # Fila total
        ws.cell(row=row_n, column=1, value='TOTAL').font = header_font(color=blanco)
        ws.cell(row=row_n, column=5, value=total_pagar_global).font = header_font(color=blanco)
        ws.cell(row=row_n, column=5).number_format = '"$"#,##0.00'
        for col in range(1, 6):
            ws.cell(row=row_n, column=col).fill   = fill(verde)
            ws.cell(row=row_n, column=col).border = thin_border()
        ws.row_dimensions[row_n].height = 22

        ws.column_dimensions['A'].width = 28
        ws.column_dimensions['B'].width = 12
        ws.column_dimensions['C'].width = 15
        ws.column_dimensions['D'].width = 15
        ws.column_dimensions['E'].width = 18

        # ── Hoja por instructor ──────────────────────────
        for inst in instructores:
            horas_inst = [h for h in horas if h['instructor_id'] == inst['id']]
            ws2 = wb.create_sheet(title=f"{inst['apellido']} {inst['nombre']}"[:31])

            ws2.merge_cells('A1:G1')
            ws2['A1'] = f"{inst['nombre']} {inst['apellido']} — {mes}"
            ws2['A1'].font = Font(name='Calibri', bold=True, color=blanco, size=12)
            ws2['A1'].fill = fill(verde)
            ws2['A1'].alignment = Alignment(horizontal='center', vertical='center')
            ws2.row_dimensions[1].height = 28

            # Info tarifa
            ws2.merge_cells('A2:G2')
            ws2['A2'] = f"Tarifa por hora: ${inst['tarifa_hora']:,.2f}"
            ws2['A2'].font = Font(name='Calibri', size=10, color=oscuro)
            ws2['A2'].fill = fill(verde_pale)
            ws2['A2'].alignment = Alignment(horizontal='left', vertical='center', indent=1)
            ws2.row_dimensions[2].height = 18

            hdrs = ['Fecha', 'Día', 'Inicio', 'Fin', 'Horas', 'Tipo', 'Notas']
            for col, h in enumerate(hdrs, 1):
                c = ws2.cell(row=3, column=col, value=h)
                c.font   = header_font(color=blanco)
                c.fill   = fill(oscuro)
                c.alignment = Alignment(horizontal='center')
                c.border = thin_border()
            ws2.row_dimensions[3].height = 22

            dias_es = ['Lunes','Martes','Miércoles','Jueves','Viernes','Sábado','Domingo']
            from datetime import date as ddate
            total_min2 = 0
            for i, h in enumerate(horas_inst):
                try:
                    d_obj = ddate.fromisoformat(h['fecha'])
                    dia   = dias_es[d_obj.weekday()]
                except Exception:
                    dia = ''
                mins = (int(h['hora_fin'][:2])*60 + int(h['hora_fin'][3:])) - \
                       (int(h['hora_inicio'][:2])*60 + int(h['hora_inicio'][3:]))
                total_min2 += mins
                bg = gris if i % 2 == 0 else blanco
                vals = [h['fecha'], dia, h['hora_inicio'], h['hora_fin'],
                        round(mins/60, 2), h['tipo'], h['notas'] or '']
                for col, val in enumerate(vals, 1):
                    c = ws2.cell(row=4+i, column=col, value=val)
                    c.font   = cell_font()
                    c.fill   = fill(bg)
                    c.border = thin_border()

            # Fila totales instructor
            tr = 4 + len(horas_inst)
            total_h2   = round(total_min2/60, 2)
            total_pay2 = round(total_h2 * (inst['tarifa_hora'] or 0), 2)
            ws2.cell(row=tr, column=1, value='TOTAL').font = header_font(color=blanco)
            ws2.cell(row=tr, column=5, value=total_h2).font = header_font(color=blanco)
            ws2.cell(row=tr, column=7, value=total_pay2).font = header_font(color=blanco)
            ws2.cell(row=tr, column=7).number_format = '"$"#,##0.00'
            for col in range(1, 8):
                ws2.cell(row=tr, column=col).fill   = fill(verde)
                ws2.cell(row=tr, column=col).border = thin_border()

            ws2.column_dimensions['A'].width = 12
            ws2.column_dimensions['B'].width = 12
            ws2.column_dimensions['C'].width = 8
            ws2.column_dimensions['D'].width = 8
            ws2.column_dimensions['E'].width = 8
            ws2.column_dimensions['F'].width = 16
            ws2.column_dimensions['G'].width = 30

        buf = BytesIO()
        wb.save(buf)
        buf.seek(0)

        from flask import send_file
        return send_file(
            buf,
            download_name=f'horas_instructores_{mes}.xlsx',
            as_attachment=True,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ── Página de auto-registro del instructor ────────────
@app.route('/instructor')
def instructor_portal():
    return render_template('instructor.html')


@app.route('/api/instructor/login', methods=['POST'])
def instructor_login():
    data = request.get_json()
    instructor_id = data.get('instructor_id')
    pin           = data.get('pin', '')
    try:
        with get_db() as conn:
            inst = conn.execute(
                'SELECT id, nombre, apellido FROM instructores WHERE id=? AND activo=1 AND pin=?',
                (instructor_id, pin)
            ).fetchone()
        if inst:
            return jsonify({'ok': True, 'instructor': dict(inst)})
        return jsonify({'error': 'PIN incorrecto'}), 403
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/instructor/horas/<int:instructor_id>', methods=['GET'])
def get_horas_instructor(instructor_id):
    """Historial del instructor — sin PIN, acceso libre para instructores."""
    mes = request.args.get('mes', '')
    try:
        with get_db() as conn:
            rows = conn.execute('''
                SELECT * FROM horas_trabajadas
                WHERE instructor_id=? AND fecha LIKE ?
                ORDER BY fecha DESC, hora_inicio DESC
            ''', (instructor_id, f'{mes}%')).fetchall()
        return jsonify([dict(r) for r in rows])
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
    '2': ('plan12',     'Plan 12 clases – 3 veces por semana'),
    '3': ('plan4',      'Plan 4 clases – 1 vez por semana'),
    '4': ('individual', 'Clase individual'),
    '5': (None,         'Sin plan por ahora'),
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
                'Planes: Plan 8 clases (2×semana), Plan 12 clases (3×semana), Plan 4 clases (1×semana), Clase individual. '
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
                '*2* · Plan 12 clases – 3 veces por semana\n'
                '*3* · Plan 4 clases – 1 vez por semana\n'
                '*4* · Clase individual\n'
                '*5* · Sin plan por ahora\n')

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
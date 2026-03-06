from flask import Flask, render_template, request, jsonify, redirect, url_for
import sqlite3
import os

# ── App ──────────────────────────────────────────────
app = Flask(__name__)

app.config.update(
    SESSION_COOKIE_SECURE=True,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
)

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


    contact_data = {
        "whatsapp_link": "https://wa.me/5492645551234",
        "email": "clubpilatesanjuan@gmail.com",
        "address": "San Roque Sur 1044, Rawson, San Juan",
        "google_maps_api_key": "TU_API_KEY_AQUI"
    }
    return render_template('index.html', data=contact_data)

@app.route('/agenda')
def agenda():
    return render_template('agenda.html')

# ── API de Reservas ───────────────────────────────────

# GET /api/reservas?desde=2025-01-01&hasta=2025-01-31
# Devuelve todas las reservas en un rango de fechas
@app.route('/api/reservas', methods=['GET'])
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

# POST /api/reservas  — crea una reserva
@app.route('/api/reservas', methods=['POST'])
def create_reserva():
    data = request.get_json()
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

# DELETE /api/reservas/<slot_key>  — cancela una reserva
@app.route('/api/reservas/<path:slot_key>', methods=['DELETE'])
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
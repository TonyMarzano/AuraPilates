# whatsapp_bot.py
# ─────────────────────────────────────────────────────────
#  Bot de WhatsApp para Club Pilates
#  Usa Meta Cloud API + Anthropic Claude
# ─────────────────────────────────────────────────────────

import re
import json
import os
import sqlite3
import requests
from datetime import datetime, timedelta

# ── Configuración ─────────────────────────────────────────

WHATSAPP_TOKEN   = os.environ.get('WHATSAPP_TOKEN', '')
PHONE_NUMBER_ID  = os.environ.get('PHONE_NUMBER_ID', '1041462272380277')
VERIFY_TOKEN     = os.environ.get('VERIFY_TOKEN', 'clubpilates12!')
ANTHROPIC_KEY    = os.environ.get('ANTHROPIC_KEY', '')

WHATSAPP_API_URL = f'https://graph.facebook.com/v19.0/{PHONE_NUMBER_ID}/messages'

# ── Info del estudio (para que Claude responda consultas) ──
STUDIO_INFO = """
Sos el asistente virtual de Club Pilates San Juan, un estudio de pilates en San Juan, Argentina.
Respondés consultas de alumnas de forma amable, cálida y profesional, en español argentino (tuteo).

INFORMACIÓN DEL ESTUDIO:
- Nombre: Club Pilates Studio & Wellness
- Dirección: San Roque Sur 1044, Rawson, San Juan
- Email: clubpilatesanjuan@gmail.com
- Horarios de atención: Lunes a Viernes 8:00 a 21:00 hs, Sábados 9:00 a 14:00 hs
- Clases de 1 hora cada una
- Servicios: Reformer Pilates, clases individuales y grupales

REGLAS IMPORTANTES:
- Si te preguntan por turnos disponibles o quieren reservar, respondé EXACTAMENTE con: "RESERVAR"
- Si no sabés algo, decí que pueden comunicarse al email o llamar al estudio
- Respuestas cortas y amigables, máximo 3 líneas
- No inventes información que no está en este contexto
"""

# ── Estado de conversaciones (en memoria) ─────────────────
# { phone: { 'step': '...', 'data': {...} } }
conversation_state = {}

STEPS = {
    'idle':      None,
    'nombre':    '¿Cuál es tu nombre?',
    'apellido':  '¿Y tu apellido?',
    'fecha':     '¿Qué día querés reservar? Escribí la fecha (ej: 15/03/2026)',
    'hora':      '¿A qué hora? (ej: 10:00)',
    'confirmar': None,
}


# ── Enviar mensaje ─────────────────────────────────────────
def send_message(to, text):
    """Envía un mensaje de texto por WhatsApp."""
    payload = {
        'messaging_product': 'whatsapp',
        'to': to,
        'type': 'text',
        'text': {'body': text}
    }
    headers = {
        'Authorization': f'Bearer {WHATSAPP_TOKEN}',
        'Content-Type': 'application/json'
    }
    try:
        r = requests.post(WHATSAPP_API_URL, json=payload, headers=headers, timeout=10)
        return r.status_code == 200
    except Exception as e:
        print(f'[WhatsApp] Error enviando mensaje: {e}')
        return False


# ── Claude: responder consulta libre ──────────────────────
def ask_claude(user_message):
    """Llama a la API de Anthropic para responder consultas."""
    try:
        headers = {
            'x-api-key': ANTHROPIC_KEY,
            'anthropic-version': '2023-06-01',
            'content-type': 'application/json'
        }
        payload = {
            'model': 'claude-haiku-4-5-20251001',
            'max_tokens': 300,
            'system': STUDIO_INFO,
            'messages': [{'role': 'user', 'content': user_message}]
        }
        r = requests.post(
            'https://api.anthropic.com/v1/messages',
            json=payload, headers=headers, timeout=15
        )
        if r.status_code == 200:
            return r.json()['content'][0]['text'].strip()
        return None
    except Exception as e:
        print(f'[Claude] Error: {e}')
        return None


# ── Verificar disponibilidad ───────────────────────────────
def is_slot_available(fecha_str, hora_str, db_path):
    """Verifica si un turno está libre en la base de datos."""
    try:
        # Parsear fecha dd/mm/yyyy
        day, month, year = fecha_str.strip().split('/')
        slot_key = f'{year}-{month.zfill(2)}-{day.zfill(2)}_{hora_str[:2].zfill(2)}'

        conn = sqlite3.connect(db_path)
        row  = conn.execute(
            'SELECT id FROM reservas WHERE slot_key = ?', (slot_key,)
        ).fetchone()
        conn.close()
        return row is None, slot_key
    except Exception as e:
        print(f'[DB] Error verificando slot: {e}')
        return False, None


def save_reservation(slot_key, nombre, apellido, tel, db_path):
    """Guarda una reserva en la base de datos."""
    try:
        conn = sqlite3.connect(db_path)
        conn.execute(
            'INSERT INTO reservas (slot_key, nombre, apellido, tel) VALUES (?, ?, ?, ?)',
            (slot_key, nombre, apellido, tel)
        )
        conn.commit()
        conn.close()
        return True
    except sqlite3.IntegrityError:
        return False
    except Exception as e:
        print(f'[DB] Error guardando reserva: {e}')
        return False


def validate_date(fecha_str):
    """Valida que la fecha sea válida y no sea en el pasado."""
    try:
        day, month, year = fecha_str.strip().split('/')
        date = datetime(int(year), int(month), int(day))
        if date.date() < datetime.now().date():
            return False, 'La fecha ya pasó. Ingresá una fecha futura.'
        weekday = date.weekday()  # 0=Lun, 6=Dom
        if weekday == 6:  # Domingo
            return False, 'Los domingos no tenemos clases. Elegí otro día.'
        return True, None
    except:
        return False, 'Fecha inválida. Usá el formato dd/mm/yyyy (ej: 15/03/2026)'


def validate_time(hora_str, fecha_str):
    """Valida que la hora esté en el horario de atención."""
    try:
        hour = int(hora_str.replace(':00', '').replace(':30', '').strip())
        day, month, year = fecha_str.strip().split('/')
        date = datetime(int(year), int(month), int(day))
        is_saturday = date.weekday() == 5

        if is_saturday:
            if hour < 9 or hour >= 14:
                return False, 'Los sábados atendemos de 9:00 a 14:00 hs.'
        else:
            if hour < 8 or hour >= 21:
                return False, 'De lunes a viernes atendemos de 8:00 a 21:00 hs.'
        return True, None
    except:
        return False, 'Hora inválida. Usá el formato HH:00 (ej: 10:00)'


# ── Lógica principal del bot ───────────────────────────────
def process_message(phone, message_text, db_path):
    """
    Procesa un mensaje entrante y retorna la respuesta.
    Maneja el flujo de reserva paso a paso.
    """
    text  = message_text.strip()
    state = conversation_state.get(phone, {'step': 'idle', 'data': {}})
    step  = state['step']
    data  = state['data']

    # ── Comandos globales ──
    if text.lower() in ['cancelar', 'salir', 'menu']:
        conversation_state.pop(phone, None)
        return (
            '❌ Reserva cancelada.\n\n'
            'Escribí lo que necesitás o "reservar" para hacer un turno 🌿'
        )

    # ── Flujo de reserva ──
    if step == 'nombre':
        if len(text) < 2:
            return 'Por favor ingresá un nombre válido.'
        data['nombre'] = text.title()
        conversation_state[phone] = {'step': 'apellido', 'data': data}
        return '¿Y tu apellido?'

    if step == 'apellido':
        if len(text) < 2:
            return 'Por favor ingresá un apellido válido.'
        data['apellido'] = text.title()
        conversation_state[phone] = {'step': 'fecha', 'data': data}
        return '¿Qué día querés reservar?\nEscribí la fecha así: *dd/mm/yyyy*\nEj: 15/03/2026'

    if step == 'fecha':
        ok, err = validate_date(text)
        if not ok:
            return f'⚠️ {err}'
        data['fecha'] = text.strip()
        conversation_state[phone] = {'step': 'hora', 'data': data}
        day, month, year = text.split('/')
        date = datetime(int(year), int(month), int(day))
        is_saturday = date.weekday() == 5
        horario = '9:00 a 14:00 hs' if is_saturday else '8:00 a 21:00 hs'
        return f'¿A qué hora? Horario disponible: *{horario}*\nEscribí solo la hora (ej: 10:00)'

    if step == 'hora':
        ok, err = validate_time(text, data['fecha'])
        if not ok:
            return f'⚠️ {err}'

        hora_clean = text.zfill(5) if ':' in text else f'{text}:00'
        data['hora'] = hora_clean

        # Verificar disponibilidad
        available, slot_key = is_slot_available(data['fecha'], hora_clean, db_path)
        if not available:
            return (
                f'⚠️ Lo sentimos, el turno de las *{hora_clean}* del *{data["fecha"]}* '
                f'ya está reservado.\n¿Querés intentar con otro horario? Escribí la hora:'
            )

        data['slot_key'] = slot_key
        conversation_state[phone] = {'step': 'confirmar', 'data': data}

        return (
            f'📋 *Resumen de tu reserva:*\n\n'
            f'👤 {data["nombre"]} {data["apellido"]}\n'
            f'📅 {data["fecha"]} a las {hora_clean} hs\n'
            f'📱 {phone}\n\n'
            f'¿Confirmás? Respondé *SÍ* para confirmar o *NO* para cancelar.'
        )

    if step == 'confirmar':
        if text.lower() in ['si', 'sí', 's', 'yes']:
            saved = save_reservation(
                data['slot_key'],
                data['nombre'],
                data['apellido'],
                phone,
                db_path
            )
            conversation_state.pop(phone, None)
            if saved:
                return (
                    f'✅ *¡Turno confirmado!*\n\n'
                    f'📅 {data["fecha"]} a las {data["hora"]} hs\n'
                    f'👤 {data["nombre"]} {data["apellido"]}\n\n'
                    f'Te esperamos en Club Pilates 🌿\n'
                    f'San Roque Sur 1044, Rawson, San Juan'
                )
            else:
                return '⚠️ Hubo un problema al guardar tu reserva. Por favor intentá de nuevo.'
        else:
            conversation_state.pop(phone, None)
            return 'Reserva cancelada. ¡Cuando quieras podés volver a intentarlo! 🌿'

    # ── Sin flujo activo: consulta libre a Claude ──
    response = ask_claude(text)

    if response == 'RESERVAR' or 'reservar' in text.lower() or 'turno' in text.lower():
        conversation_state[phone] = {'step': 'nombre', 'data': {'tel': phone}}
        return (
            '¡Perfecto! Te ayudo a reservar tu turno 🌿\n\n'
            '¿Cuál es tu nombre?\n\n'
            '_(En cualquier momento escribí *cancelar* para salir)_'
        )

    if response:
        return response

    # Fallback
    return (
        '¡Hola! Soy el asistente de *Club Pilates* 🌿\n\n'
        'Puedo ayudarte a:\n'
        '• Reservar un turno → escribí *reservar*\n'
        '• Consultar horarios → escribí *horarios*\n'
        '• Saber dónde estamos → escribí *ubicación*'
    )
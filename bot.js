// bot.js — Club Pilates WhatsApp Bot (Baileys)
const { default: makeWASocket, DisconnectReason, useMultiFileAuthState } = require('@whiskeysockets/baileys');
const qrcode  = require('qrcode-terminal');
const https   = require('https');
const http    = require('http');

// ── Configuración ─────────────────────────────────────
const AGENDA_URL = 'http://localhost:8000';  // Tu Flask
const BOT_NAME   = 'Club Pilates 🌿';

// ── Estado de conversaciones ───────────────────────────
// { phone: { step, data } }
const state = {};

// ── Horarios válidos ───────────────────────────────────
const SCHEDULE = {
    1: { start: 8,  end: 21 }, // Lun
    2: { start: 8,  end: 21 }, // Mar
    3: { start: 8,  end: 21 }, // Mie
    4: { start: 8,  end: 21 }, // Jue
    5: { start: 8,  end: 21 }, // Vie
    6: { start: 9,  end: 14 }, // Sab
};

// ── Helpers ────────────────────────────────────────────
function slotKey(day, month, year, hour) {
    return `${year}-${String(month).padStart(2,'0')}-${String(day).padStart(2,'0')}_${String(hour).padStart(2,'0')}`;
}

function parseDate(str) {
    const parts = str.trim().split('/');
    if (parts.length !== 3) return null;
    const [d, m, y] = parts.map(Number);
    if (!d || !m || !y) return null;
    const date = new Date(y, m - 1, d);
    if (date.getMonth() !== m - 1) return null;
    return date;
}

function validateDate(str) {
    const date = parseDate(str);
    if (!date) return { ok: false, msg: 'Fecha inválida. Usá el formato *dd/mm/yyyy* (ej: 20/03/2026)' };
    const today = new Date(); today.setHours(0,0,0,0);
    if (date < today) return { ok: false, msg: 'Esa fecha ya pasó. Ingresá una fecha futura.' };
    if (date.getDay() === 0) return { ok: false, msg: 'Los domingos no tenemos clases. Elegí otro día.' };
    return { ok: true, date };
}

function validateTime(hourStr, date) {
    const hour = parseInt(hourStr);
    if (isNaN(hour)) return { ok: false, msg: 'Hora inválida. Usá el formato *HH:00* (ej: 10:00)' };
    const dow = date.getDay();
    const sched = SCHEDULE[dow];
    if (!sched) return { ok: false, msg: 'Ese día no tenemos clases.' };
    if (hour < sched.start || hour >= sched.end) {
        const label = dow === 6 ? 'Los sábados atendemos de 9:00 a 14:00 hs.' : 'De lunes a viernes atendemos de 8:00 a 21:00 hs.';
        return { ok: false, msg: label };
    }
    return { ok: true, hour };
}

// ── API calls a Flask ──────────────────────────────────
function apiGet(path) {
    return new Promise((resolve) => {
        http.get(`${AGENDA_URL}${path}`, (res) => {
            let data = '';
            res.on('data', chunk => data += chunk);
            res.on('end', () => {
                try { resolve(JSON.parse(data)); }
                catch { resolve({}); }
            });
        }).on('error', () => resolve({}));
    });
}

function apiPost(path, body) {
    return new Promise((resolve) => {
        const payload = JSON.stringify(body);
        const options = {
            hostname: 'localhost',
            port: 8000,
            path,
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Content-Length': Buffer.byteLength(payload)
            }
        };
        const req = http.request(options, (res) => {
            let data = '';
            res.on('data', chunk => data += chunk);
            res.on('end', () => {
                try { resolve({ status: res.statusCode, body: JSON.parse(data) }); }
                catch { resolve({ status: res.statusCode, body: {} }); }
            });
        });
        req.on('error', () => resolve({ status: 500, body: {} }));
        req.write(payload);
        req.end();
    });
}

async function isSlotAvailable(day, month, year, hour) {
    const key   = slotKey(day, month, year, hour);
    const desde = `${year}-${String(month).padStart(2,'0')}-${String(day).padStart(2,'0')}`;
    const data  = await apiGet(`/api/reservas?desde=${desde}&hasta=${desde}`);
    return { available: !data[key], key };
}

async function saveReservation(key, nombre, apellido, tel) {
    const res = await apiPost('/api/reservas', { slot_key: key, nombre, apellido, tel });
    return res.status === 201;
}

// ── Lógica del bot ─────────────────────────────────────
async function handleMessage(phone, text) {
    const msg  = text.trim();
    const low  = msg.toLowerCase();
    const s    = state[phone] || { step: 'idle', data: {} };

    // Comandos globales
    if (['cancelar', 'salir', 'menu', 'inicio'].includes(low)) {
        delete state[phone];
        return menuMessage();
    }

    // ── Flujo de reserva ──
    if (s.step === 'nombre') {
        if (msg.length < 2) return '⚠️ Por favor ingresá un nombre válido.';
        s.data.nombre = capitalize(msg);
        s.step = 'apellido';
        state[phone] = s;
        return '¿Y tu apellido?';
    }

    if (s.step === 'apellido') {
        if (msg.length < 2) return '⚠️ Por favor ingresá un apellido válido.';
        s.data.apellido = capitalize(msg);
        s.step = 'fecha';
        state[phone] = s;
        return '¿Qué día querés reservar?\nEscribí la fecha así: *dd/mm/yyyy*\nEj: 20/03/2026';
    }

    if (s.step === 'fecha') {
        const val = validateDate(msg);
        if (!val.ok) return `⚠️ ${val.msg}`;
        s.data.fecha = msg.trim();
        s.data.dateObj = val.date;
        s.step = 'hora';
        state[phone] = s;
        const dow = val.date.getDay();
        const horario = dow === 6 ? '9:00 a 14:00 hs' : '8:00 a 21:00 hs';
        return `¿A qué hora? Horario: *${horario}*\nEscribí solo la hora (ej: 10:00)`;
    }

    if (s.step === 'hora') {
        const hourStr = msg.replace(':00','').replace(':30','');
        const val = validateTime(hourStr, s.data.dateObj);
        if (!val.ok) return `⚠️ ${val.msg}`;

        const [d, m, y] = s.data.fecha.split('/').map(Number);
        const { available, key } = await isSlotAvailable(d, m, y, val.hour);

        if (!available) {
            return `⚠️ El turno de las *${msg}* del *${s.data.fecha}* ya está reservado.\n¿Querés otro horario? Escribí la hora:`;
        }

        s.data.hora    = `${String(val.hour).padStart(2,'0')}:00`;
        s.data.slotKey = key;
        s.step = 'confirmar';
        state[phone] = s;

        return (
            `📋 *Resumen de tu reserva:*\n\n` +
            `👤 ${s.data.nombre} ${s.data.apellido}\n` +
            `📅 ${s.data.fecha} a las ${s.data.hora} hs\n\n` +
            `¿Confirmás? Respondé *SÍ* para confirmar o *NO* para cancelar.`
        );
    }

    if (s.step === 'confirmar') {
        if (['si', 'sí', 's', 'yes'].includes(low)) {
            const saved = await saveReservation(
                s.data.slotKey,
                s.data.nombre,
                s.data.apellido,
                phone.replace('@s.whatsapp.net', '')
            );
            delete state[phone];
            if (saved) {
                return (
                    `✅ *¡Turno confirmado!*\n\n` +
                    `📅 ${s.data.fecha} a las ${s.data.hora} hs\n` +
                    `👤 ${s.data.nombre} ${s.data.apellido}\n\n` +
                    `Te esperamos en Club Pilates 🌿\n` +
                    `San Roque Sur 1044, Rawson, San Juan`
                );
            } else {
                return '⚠️ Hubo un problema al guardar tu reserva. Por favor intentá de nuevo escribiendo *reservar*.';
            }
        } else {
            delete state[phone];
            return '❌ Reserva cancelada. ¡Cuando quieras podés volver a intentarlo! 🌿';
        }
    }

    // ── Sin flujo: respuestas a palabras clave ──
    if (low.includes('reservar') || low.includes('turno') || low.includes('clase')) {
        state[phone] = { step: 'nombre', data: { tel: phone } };
        return (
            '¡Perfecto! Te ayudo a reservar tu turno 🌿\n\n' +
            '¿Cuál es tu nombre?\n\n' +
            '_En cualquier momento escribí *cancelar* para salir_'
        );
    }

    if (low.includes('horario') || low.includes('hora')) {
        return (
            '🕐 *Nuestros horarios:*\n\n' +
            '📅 Lunes a Viernes: 8:00 a 21:00 hs\n' +
            '📅 Sábados: 9:00 a 14:00 hs\n' +
            '🚫 Domingos: cerrado\n\n' +
            '¿Querés reservar un turno? Escribí *reservar* 🌿'
        );
    }

    if (low.includes('ubicacion') || low.includes('ubicación') || low.includes('donde') || low.includes('dónde') || low.includes('direccion')) {
        return (
            '📍 *Nos encontramos en:*\n\n' +
            'San Roque Sur 1044, Rawson, San Juan\n\n' +
            '¿Querés reservar un turno? Escribí *reservar* 🌿'
        );
    }

    if (low.includes('precio') || low.includes('costo') || low.includes('cuanto') || low.includes('cuánto')) {
        return (
            'Para consultar precios y promociones actuales,\n' +
            'escribinos al 📧 clubpilatesanjuan@gmail.com\n\n' +
            '¿Querés reservar un turno? Escribí *reservar* 🌿'
        );
    }

    if (['hola', 'buenas', 'buen dia', 'buen día', 'buenos dias', 'buenos días', 'hi', 'hello'].includes(low)) {
        return menuMessage();
    }

    // Fallback
    return menuMessage();
}

function menuMessage() {
    return (
        `¡Hola! Bienvenida a *Club Pilates San Juan* 🌿\n\n` +
        `¿En qué te puedo ayudar?\n\n` +
        `📅 *reservar* — Reservar un turno\n` +
        `🕐 *horarios* — Ver horarios disponibles\n` +
        `📍 *ubicación* — Dónde estamos\n` +
        `💰 *precios* — Consultar precios\n\n` +
        `_Escribí cualquiera de esas palabras_`
    );
}

function capitalize(str) {
    return str.charAt(0).toUpperCase() + str.slice(1).toLowerCase();
}

// ── Conexión a WhatsApp ────────────────────────────────
async function startBot() {
    const { state: authState, saveCreds } = await useMultiFileAuthState('auth_session');

    const sock = makeWASocket({
        auth: authState,
        printQRInTerminal: false,
    });

    sock.ev.on('connection.update', ({ connection, lastDisconnect, qr }) => {
        if (qr) {
            console.log('\n📱 Escaneá este QR con tu WhatsApp:\n');
            qrcode.generate(qr, { small: true });
        }

        if (connection === 'close') {
            const shouldReconnect = lastDisconnect?.error?.output?.statusCode !== DisconnectReason.loggedOut;
            console.log('[Bot] Desconectado. Reconectando:', shouldReconnect);
            if (shouldReconnect) startBot();
        }

        if (connection === 'open') {
            console.log('[Bot] ✅ Conectado a WhatsApp correctamente!');
        }
    });

    sock.ev.on('creds.update', saveCreds);

    sock.ev.on('messages.upsert', async ({ messages, type }) => {
        if (type !== 'notify') return;

        for (const msg of messages) {
            if (msg.key.fromMe) continue;  // Ignorar mensajes propios
            if (!msg.message) continue;

            const phone = msg.key.remoteJid;
            const text  = (
                msg.message.conversation ||
                msg.message.extendedTextMessage?.text ||
                ''
            ).trim();

            if (!text) continue;

            console.log(`[Bot] Mensaje de ${phone}: ${text}`);

            try {
                const response = await handleMessage(phone, text);
                await sock.sendMessage(phone, { text: response });
                console.log(`[Bot] Respuesta enviada a ${phone}`);
            } catch (err) {
                console.error(`[Bot] Error procesando mensaje:`, err);
            }
        }
    });
}

startBot();
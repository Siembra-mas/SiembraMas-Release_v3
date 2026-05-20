/* ═══════════════════════════════════════════════════════
   SIEMBRABOT — Widget Flotante
   Misma lógica que siembra_bot.html:
   · FormData para texto y audio
   · Mantener presionado para hablar (mousedown / mouseup)
   · Ícono mic → square mientras graba
   · Misma voz EdgeTTS es-MX-JorgeNeural vía /api/widget-chat
   ═══════════════════════════════════════════════════════ */

// SVG inline para avatares — evita dependencia de lucide.createIcons() en elementos dinámicos
const SVG_LEAF = `<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M11 20A7 7 0 0 1 9.8 6.1C15.5 5 17 4.48 19 2c1 2 2 4.18 2 8 0 5.5-4.78 10-10 10Z"/><path d="M2 21c0-3 1.85-5.36 5.08-6C9.5 14.52 12 13 13 12"/></svg>`;
const SVG_USER = `<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="8" r="5"/><path d="M20 21a8 8 0 1 0-16 0"/></svg>`;

(function () {
    'use strict';

    // ── Referencias DOM ──────────────────────────────────
    const botTrigger   = document.getElementById('botTrigger');
    const chatWidget   = document.getElementById('chatWidget');
    const closeChat    = document.getElementById('closeChat');
    const chatMessages = document.getElementById('chatMessages');
    const chatInput    = document.getElementById('chatInput');
    const sendBtn      = document.getElementById('sendBtn');
    const recordBtn    = document.getElementById('recordBtn');
    const statusEl     = document.getElementById('statusIndicator');
    const audioPlayer  = document.getElementById('botAudioPlayer');

    if (!botTrigger || !chatWidget) return;

    // ── Estado ────────────────────────────────────────────
    let mediaRecorder     = null;
    let audioChunks       = [];
    let isRecording       = false;
    let bienvenidaLista   = false;
    let userLat           = null;
    let userLon           = null;

    // ── Abrir / Cerrar ───────────────────────────────────
    botTrigger.addEventListener('click', abrirChat);
    closeChat.addEventListener('click', cerrarChat);

    function abrirChat() {
        chatWidget.classList.add('active');
        botTrigger.classList.add('hidden');
        chatInput.focus();
        if (!bienvenidaLista) {
            bienvenidaLista = true;
            reproducirBienvenida();
        }
    }

    function cerrarChat() {
        chatWidget.classList.remove('active');
        botTrigger.classList.remove('hidden');
        if (!audioPlayer.paused) audioPlayer.pause();
    }

    // ── Bienvenida ────────────────────────────────────────
    async function reproducirBienvenida() {
        const texto = '¡Bienvenido! Soy SiembraBot, tu asistente agrícola inteligente. ' +
                      'Puedo analizar el clima, recomendarte cultivos y resolver tus dudas del campo. ' +
                      '¿En qué te ayudo hoy?';
        showStatus('Cargando bienvenida...');
        const fd = new FormData();
        fd.append('mensaje', texto);
        try {
            const r    = await fetch('/api/widget-chat', { method: 'POST', body: fd });
            const data = await r.json();
            showStatus('En línea');
            if (data.audio_url) reproducirAudio(data.audio_url);
        } catch {
            showStatus('En línea');
        }
    }

    // ── Enviar texto ──────────────────────────────────────
    sendBtn.addEventListener('click', enviarTexto);
    chatInput.addEventListener('keydown', e => {
        if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); enviarTexto(); }
    });

    async function enviarTexto() {
        const texto = chatInput.value.trim();
        if (!texto) return;
        addBubble(texto, 'user');
        chatInput.value = '';
        showTyping(true);
        showStatus('Escribiendo...');

        const fd = new FormData();
        fd.append('mensaje', texto);
        if (userLat) { fd.append('lat', userLat); fd.append('lon', userLon); }

        try {
            const r    = await fetch('/api/widget-chat', { method: 'POST', body: fd });
            const data = await r.json();
            procesarRespuesta(data);
        } catch {
            showTyping(false);
            addBubble('Error: no pude obtener respuesta.', 'bot');
            showStatus('Error');
        }
    }

    // ── Micrófono — igual que SiembraBot: mantener presionado ──
    recordBtn.addEventListener('mousedown',  iniciarGrabacion);
    recordBtn.addEventListener('mouseup',    detenerGrabacion);
    recordBtn.addEventListener('touchstart', iniciarGrabacion, { passive: false });
    recordBtn.addEventListener('touchend',   detenerGrabacion, { passive: false });

    async function iniciarGrabacion(e) {
        if (e) e.preventDefault();
        if (!navigator.mediaDevices) {
            addBubble('Tu navegador no soporta el micrófono.', 'bot'); return;
        }
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            audioChunks  = [];
            mediaRecorder = new MediaRecorder(stream);
            mediaRecorder.ondataavailable = ev => audioChunks.push(ev.data);
            mediaRecorder.onstop = () => {
                const blob = new Blob(audioChunks, { type: 'audio/wav' });
                enviarAudio(blob);
            };
            mediaRecorder.start();
            isRecording = true;
            recordBtn.classList.add('recording');
            setMicIcon('square');
            showStatus('Escuchando...');
        } catch {
            addBubble('No se pudo acceder al micrófono. Verifica los permisos.', 'bot');
        }
    }

    function detenerGrabacion(e) {
        if (e) e.preventDefault();
        if (!isRecording || !mediaRecorder) return;
        mediaRecorder.stop();
        mediaRecorder.stream?.getTracks().forEach(t => t.stop());
        isRecording = false;
        recordBtn.classList.remove('recording');
        setMicIcon('mic');
        showStatus('Procesando audio...');
    }

    // ── Enviar audio ──────────────────────────────────────
    async function enviarAudio(blob) {
        addBubble('🎤 Mensaje de voz enviado', 'user');
        showTyping(true);

        const fd = new FormData();
        fd.append('audio_blob', blob, 'audio.wav');
        if (userLat) { fd.append('lat', userLat); fd.append('lon', userLon); }

        try {
            const r    = await fetch('/api/widget-chat', { method: 'POST', body: fd });
            const data = await r.json();
            procesarRespuesta(data);
        } catch {
            showTyping(false);
            addBubble('Error al conectar con el servidor.', 'bot');
            showStatus('Error');
        }
    }

    // ── Procesar respuesta ────────────────────────────────
    function procesarRespuesta(data) {
        showTyping(false);
        showStatus('En línea');
        if (data.error) { addBubble('Error: ' + data.error, 'bot'); return; }
        addBubble(data.bot, 'bot');
        if (data.audio_url) reproducirAudio(data.audio_url);
    }

    // ── Reproducir audio ──────────────────────────────────
    function reproducirAudio(url) {
        // url puede ser relativa ("audio/resp_xxx.mp3") — prepend STATIC_URL
        const src = url.startsWith('http') || url.startsWith('/')
            ? url
            : (window.STATIC_URL || '/static/') + url;
        audioPlayer.src = src;
        audioPlayer.play().catch(() => {});
    }

    // ── Helpers UI ────────────────────────────────────────
    function addBubble(text, sender) {
        const isBot = sender === 'bot';
        const now   = new Date().toLocaleTimeString('es-MX', { hour: '2-digit', minute: '2-digit' });

        const row = document.createElement('div');
        row.className = `bubble-row ${sender}`;

        // Avatares con SVG inline para evitar problemas de inicialización dinámica de Lucide
        const avatarBot  = `<div class="bubble-avatar bot">${SVG_LEAF}</div>`;
        const avatarUser = `<div class="bubble-avatar user">${SVG_USER}</div>`;

        row.innerHTML = `
            ${isBot ? avatarBot : ''}
            <div>
                <div class="bubble ${sender}">${text}</div>
                <div class="bubble-meta">${now}</div>
            </div>
            ${!isBot ? avatarUser : ''}
        `;
        chatMessages.appendChild(row);
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }

    function showTyping(show) {
        if (!statusEl) return;
        const textEl = statusEl.querySelector('.status-text');
        if (textEl) textEl.textContent = show ? 'Escribiendo...' : '';
        statusEl.classList.toggle('hidden', !show);
        if (show) chatMessages.scrollTop = chatMessages.scrollHeight;
    }

    function showStatus(text) {
        const textEl = statusEl?.querySelector('.status-text');
        if (textEl) textEl.textContent = text;
    }

    const SVG_MIC    = `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="2" width="6" height="11" rx="3"/><path d="M19 10v2a7 7 0 0 1-14 0v-2"/><line x1="12" y1="19" x2="12" y2="22"/><line x1="8" y1="22" x2="16" y2="22"/></svg>`;
    const SVG_SQUARE = `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="currentColor" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="3"/></svg>`;

    function setMicIcon(nombre) {
        const svg = nombre === 'mic' ? SVG_MIC : SVG_SQUARE;
        recordBtn.innerHTML = svg;
    }

})();

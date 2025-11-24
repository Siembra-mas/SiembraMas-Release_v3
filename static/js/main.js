document.addEventListener('DOMContentLoaded', () => {
    
    // --- 1. MENÚ RESPONSIVO ---
    const menuToggle = document.querySelector('.menu-toggle');
    const navLinks = document.querySelector('.nav-links');
    
    if(menuToggle) {
        menuToggle.addEventListener('click', () => {
            navLinks.classList.toggle('active');
        });
    }

    // --- 2. SIEMBRA BOT (OVERLAY) ---
    const floatBot = document.querySelector('.floating-bot');
    const botOverlay = document.getElementById('bot-overlay');
    
    if(floatBot && botOverlay) {
        floatBot.addEventListener('click', () => {
            botOverlay.classList.add('active');
            
            // Simular espera de 3 segundos y cerrar
            setTimeout(() => {
                botOverlay.classList.remove('active');
                alert("Simulación: Comando recibido. Redirigiendo a resultados...");
            }, 3000);
        });
        
        // Cerrar al hacer click fuera (en el fondo)
        botOverlay.addEventListener('click', (e) => {
            if(e.target === botOverlay) botOverlay.classList.remove('active');
        });
    }

    // --- 3. SIEMBRA VISIÓN (TABS) ---
    const btnCam = document.getElementById('btn-camara');
    const btnUpload = document.getElementById('btn-upload');
    const panelCam = document.getElementById('panel-camara');
    const panelUpload = document.getElementById('panel-upload');

    if(btnCam && btnUpload) {
        btnCam.addEventListener('click', () => {
            panelCam.classList.add('active');
            panelUpload.classList.remove('active');
            btnCam.classList.remove('btn-outline');
            btnCam.classList.add('btn');
            btnUpload.classList.add('btn-outline');
            btnUpload.classList.remove('btn');
        });

        btnUpload.addEventListener('click', () => {
            panelUpload.classList.add('active');
            panelCam.classList.remove('active');
            btnUpload.classList.remove('btn-outline');
            btnUpload.classList.add('btn');
            btnCam.classList.add('btn-outline');
            btnCam.classList.remove('btn');
        });
    }

    // --- 4. SIEMBRA LINK (SIMULACIÓN DE PLANTA HEADER) ---
    const plantStem = document.querySelector('.plant-stem');
    if(plantStem) {
        setTimeout(() => {
            plantStem.style.height = "75%"; 
        }, 500);
    }
    
    // --- 5. TOGGLE DE RESULTADOS (INDEX) ---
    const resultsToggle = document.querySelector('.results-toggle');
    const resultsSection = document.getElementById('resultados-content');
    
    if(resultsToggle && resultsSection) {
        resultsToggle.addEventListener('click', () => {
            resultsSection.classList.toggle('hidden');
            const icon = resultsToggle.querySelector('i');
            if(resultsSection.classList.contains('hidden')) {
                icon.classList.remove('fa-chevron-up');
                icon.classList.add('fa-chevron-down');
            } else {
                icon.classList.remove('fa-chevron-down');
                icon.classList.add('fa-chevron-up');
            }
        });
    }
});

// --- LÓGICA DE TABLERO DE CULTIVOS (API + FETCH + SVG) ---
document.addEventListener('DOMContentLoaded', () => {
    
    const selectEtapa = document.getElementById('etapa-select');
    const selectCultivo = document.getElementById('cultivo-select');
    const btnActualizar = document.getElementById('btn-actualizar');
    
    // Si no existen estos elementos, no estamos en la página del tablero
    if(!selectEtapa || !selectCultivo) return;

    // Variables globales para datos
    let DATOS_CULTIVOS = null;
    let SENSORES = null;

    // Referencias a los elementos UI (SVG y Tooltips)
    const ui = {
        titulo: document.getElementById('titulo-resumen'),
        icono: document.getElementById('icono-etapa'),
        
        // TEMPERATURA
        valTemp: document.getElementById('val-temp'),      
        recTemp: document.getElementById('rec-temp'),      
        fillTemp: document.getElementById('fill-temp'),    
        
        // HUMEDAD
        valHum: document.getElementById('val-hum'),
        recHum: document.getElementById('rec-hum'),
        fillHum: document.getElementById('fill-hum'),
        
        // LLUVIA
        valLluvia: document.getElementById('val-lluvia'),
        recLluvia: document.getElementById('rec-lluvia'),
        fillLluvia: document.getElementById('fill-lluvia')
    };

    // --- FUNCIÓN FETCH API ---
    async function fetchDatosTablero() {
        try {
            if(btnActualizar) btnActualizar.innerHTML = '<span>Cargando...</span><i class="fa-solid fa-spinner fa-spin"></i>';

            const response = await fetch('/api/datos-tablero');
            
            if (!response.ok) throw new Error('Error en la red');
            
            const data = await response.json(); 
            
            DATOS_CULTIVOS = data.cultivos;
            SENSORES = data.sensores;

            console.log("Datos recibidos de Flask:", data);
            
            // Actualizar interfaz con los nuevos datos
            actualizarInterfaz();

        } catch (error) {
            console.error('Error fetching data:', error);
            if(ui.titulo) ui.titulo.innerText = "Error conexión";
        } finally {
            if(btnActualizar) btnActualizar.innerHTML = '<span>Actualizar Análisis</span><i class="fa-solid fa-rotate"></i>';
        }
    }

    // --- FUNCIÓN ACTUALIZAR UI ---
    function actualizarInterfaz() {
        const etapa = selectEtapa.value;
        const cultivo = selectCultivo.value;

        if (!DATOS_CULTIVOS || !SENSORES) return;
        if (!cultivo) {
            ui.titulo.innerText = "Seleccione un cultivo";
            return;
        }

        const datosCultivo = DATOS_CULTIVOS[etapa] ? DATOS_CULTIVOS[etapa][cultivo] : null;

        if (!datosCultivo) {
            console.warn("No hay datos para este cultivo/etapa");
            ui.titulo.innerText = "Sin datos disponibles";
            return; 
        }
        
        // Actualizar Título
        ui.titulo.innerText = `${cultivo}`;
        
        // Icono según etapa
        if(etapa == "1") ui.icono.className = "fa-solid fa-seedling";
        else if(etapa == "2") ui.icono.className = "fa-solid fa-tree";
        else ui.icono.className = "fa-solid fa-wheat-awn";

        // Escalas (Valores máximos visuales)
        const ESCALA_TEMP = 60;     // 60°C = planta llena
        const ESCALA_HUM = 100;     // 100% = planta llena
        const ESCALA_LLUVIA = 2500; // 2500mm = planta llena

        // Animar cada planta
        animatePlant(SENSORES.temp, datosCultivo.temp_min, datosCultivo.temp_max, ESCALA_TEMP, 
            { valText: ui.valTemp, recText: ui.recTemp, fillSvg: ui.fillTemp }, "°C");
        
        animatePlant(SENSORES.hum, datosCultivo.hum_suelo_min, datosCultivo.hum_suelo_max, ESCALA_HUM, 
            { valText: ui.valHum, recText: ui.recHum, fillSvg: ui.fillHum }, "%");
            
        animatePlant(SENSORES.lluvia, datosCultivo.lluvia_min, datosCultivo.lluvia_max, ESCALA_LLUVIA, 
            { valText: ui.valLluvia, recText: ui.recLluvia, fillSvg: ui.fillLluvia }, "mm");
    }

    // --- HELPER ANIMACIÓN ---
    function animatePlant(actual, min, max, escala, elems, unidad) {
        elems.valText.innerText = `${actual} ${unidad}`;
        elems.recText.innerText = `${min} - ${max} ${unidad}`;

        // % de llenado (0 a 100)
        let porcentaje = (actual / escala) * 100;
        if (porcentaje > 100) porcentaje = 100;
        if (porcentaje < 0) porcentaje = 0;

        // translateY: 100% = Vacío, 0% = Lleno
        const translateValue = 100 - porcentaje;

        // CSS Transform
        elems.fillSvg.style.transform = `translateY(${translateValue}%)`;

        // Alerta visual en texto
        if (actual < min || actual > max) {
            elems.valText.style.color = "#D9534F"; // Rojo
        } else {
            elems.valText.style.color = "var(--dark-green)";
        }
    }

    // --- EVENTOS ---
    fetchDatosTablero(); // Cargar al inicio

    selectEtapa.addEventListener('change', actualizarInterfaz);
    selectCultivo.addEventListener('change', actualizarInterfaz);
    if(btnActualizar) btnActualizar.addEventListener('click', fetchDatosTablero);
});
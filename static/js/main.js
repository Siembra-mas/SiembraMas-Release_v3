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

    // --- 4. SIEMBRA LINK (SIMULACIÓN DE PLANTA) ---
    // Simula crecimiento aleatorio al cargar la página
    const plantStem = document.querySelector('.plant-stem');
    if(plantStem) {
        setTimeout(() => {
            plantStem.style.height = "75%"; // Valor simulado
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
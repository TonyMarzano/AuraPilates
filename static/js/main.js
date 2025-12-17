// La función initMap es llamada automáticamente por el script de Google Maps API
function initMap() {
    // Coordenadas para la ubicación de ejemplo en San Juan (Rawson)
    const sanJuanCoords = { lat: -31.5858212, lng: -68.5372213 };
    
    const map = new google.maps.Map(document.getElementById('google-map-container'), {
        zoom: 14,
        center: sanJuanCoords,
        // Puedes agregar opciones de estilo para que el mapa sea más "aesthetic"
        styles: [
            // Estilos de mapa minimalistas
        ]
    });

    // Marcador para la ubicación
    new google.maps.Marker({
        position: sanJuanCoords,
        map: map,
        title: 'Aura Pilates'
    });
}

// Lógica de Transición (Ejemplo: Parallax Simple en el encabezado)
document.addEventListener('scroll', function() {
    const header = document.querySelector('.hero-section');
    const scrollPosition = window.pageYOffset;
    // Mueve la imagen de fondo lentamente para crear el efecto Parallax
    header.style.backgroundPositionY = -scrollPosition * 0.5 + 'px';
});

// Lógica para aplicar un "fade-in" sutil a las secciones al hacer scroll (aesthetic)
const sections = document.querySelectorAll('section');
const observerOptions = {
    root: null,
    rootMargin: '0px',
    threshold: 0.1 
};

const observer = new IntersectionObserver((entries, observer) => {
    entries.forEach(entry => {
        if (entry.isIntersecting) {
            entry.target.classList.add('visible');
            observer.unobserve(entry.target);
        }
    });
}, observerOptions);

sections.forEach(section => {
    observer.observe(section);
});

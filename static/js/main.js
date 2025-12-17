/**
 * Aura Pilates - Lógica de Interactividad
 */

// 1. Desplazamiento suave (Smooth Scroll) para los enlaces de navegación
document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', function (e) {
        e.preventDefault();
        const targetId = this.getAttribute('href');
        const targetElement = document.querySelector(targetId);

        if (targetElement) {
            targetElement.scrollIntoView({
                behavior: 'smooth'
            });
        }
    });
});

// 2. Lógica de Transición (Parallax sutil en el Hero)
document.addEventListener('scroll', function() {
    const header = document.querySelector('.hero-section');
    if (header) {
        const scrollPosition = window.pageYOffset;
        // Mueve el fondo un poco más lento que el scroll para el efecto parallax
        header.style.backgroundPositionY = (scrollPosition * 0.5) + 'px';
    }
});

// 3. Efecto de aparición (Fade-in) al hacer scroll
// Declaramos las constantes una sola vez para evitar errores de VS Code
const observerOptions = {
    root: null,
    rootMargin: '0px',
    threshold: 0.1 
};

const sectionObserver = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
        if (entry.isIntersecting) {
            entry.target.classList.add('visible');
            // Una vez que es visible, dejamos de observarla para mejorar el rendimiento
            sectionObserver.unobserve(entry.target);
        }
    });
}, observerOptions);

// Aplicar el observador a todas las secciones
document.querySelectorAll('section').forEach(section => {
    sectionObserver.observe(section);
});

/**
 * Nota: La función initMap se ha eliminado ya que el mapa 
 * ahora se carga vía iframe directamente en el HTML.
 */
/**
 * Aura Pilates - Lógica de Interactividad
 */

// 1. Desplazamiento suave (Smooth Scroll)
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
        header.style.backgroundPositionY = (scrollPosition * 0.5) + 'px';
    }
});

// 3. Efecto de aparición (Fade-in) al hacer scroll
const observerOptions = {
    root: null,
    rootMargin: '0px',
    threshold: 0.1 
};

const sectionObserver = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
        if (entry.isIntersecting) {
            entry.target.classList.add('visible');
            // Deja de observar para ahorrar recursos una vez que ya se ve
            sectionObserver.unobserve(entry.target);
        }
    });
}, observerOptions);

// Aplicar el observador a todas las secciones
document.querySelectorAll('section').forEach(section => {
    sectionObserver.observe(section);
});
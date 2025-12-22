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


// Lógica para el menú hamburguesa
const menuBtn = document.querySelector('.mobile-menu-btn');
const navLinks = document.querySelector('.nav-links');

menuBtn.addEventListener('click', () => {
    navLinks.classList.toggle('active');
    
    // Opcional: Cambia el icono de hamburguesa por una X
    const icon = menuBtn.querySelector('i');
    icon.classList.toggle('fa-bars');
    icon.classList.toggle('fa-times');
});

// Cerrar el menú automáticamente al hacer clic en un enlace
// Opción A: Desaparecer cuando el DOM esté listo y el Hero haya cargado
document.addEventListener('DOMContentLoaded', () => {
    const preloader = document.getElementById('preloader');
    const heroImg = new Image();
    heroImg.src = "static/img/hero_image.webp"; // Cambia a .webp si lo conviertes

    heroImg.onload = () => {
        setTimeout(() => {
            preloader.classList.add('hidden');
        }, 500); // 500ms de gracia para la animación
    };
});

// Opción B (Respaldo): Si tarda más de 4 segundos por mala conexión, quitarlo igual
setTimeout(() => {
    const preloader = document.getElementById('preloader');
    if (!preloader.classList.contains('hidden')) {
        preloader.classList.add('hidden');
    }
}, 4000);

// Asegurar que el clic en el logo haga scroll suave al inicio
document.querySelector('.logo-link').addEventListener('click', function(e) {
    e.preventDefault();
    window.scrollTo({
        top: 0,
        behavior: 'smooth'
    });
});

window.addEventListener('load', () => {
    const preloader = document.getElementById('preloader');
    
    // Agregamos un pequeño delay de 500ms para que la animación se aprecie
    setTimeout(() => {
        preloader.classList.add('hidden');
    }, 1000);
});

window.addEventListener('scroll', function() {
    const parallax = document.querySelector('.parallax-servicios');
    if (parallax) {
        // Obtenemos la posición de la sección respecto a la ventana
        const distance = window.pageYOffset - parallax.offsetTop;
        
        /* Multiplicamos por un factor pequeño (0.2 o 0.3). 
           Si el número es positivo, la imagen baja; si es negativo, sube.
        */
        const speed = 0.3;
        parallax.style.backgroundPositionY = (distance * speed) + 'px';
    }
});
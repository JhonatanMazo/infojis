document.addEventListener('DOMContentLoaded', function() {
    // Elementos principales
    const navbar = document.querySelector('.navbar');
    const scrollIndicator = document.querySelector('.scroll-indicator') || 
                            document.getElementById('scrollIndicator');
    const fadeElements = document.querySelectorAll('.fade-in');
    const navLinks = document.querySelectorAll('a[href^="#"]');
    const sections = document.querySelectorAll('section[id]');
    
    // Configuración de opciones
    const config = {
        scrollThreshold: 50,
        fadeOffset: 0.15, // Porcentaje de la pantalla
        scrollDelay: 20, // Tiempo para throttle (reducido para mayor suavidad)
        animationDuration: 0.8, // Duración aumentada para transiciones más suaves
        staggerDelay: 0.1 // Retraso entre elementos para efecto escalonado
    };
    
    // Configurar transiciones iniciales
    fadeElements.forEach((element, index) => {
        // Configurar opacidad inicial y transformación
        element.style.opacity = "0";
        element.style.transform = "translateY(30px)";
        
        // Configurar transición con duración y timing function mejorados
        element.style.transition = `
            opacity ${config.animationDuration}s cubic-bezier(0.25, 0.1, 0.25, 1), 
            transform ${config.animationDuration}s cubic-bezier(0.25, 0.1, 0.25, 1)
        `;
        
        // Preparar para efecto escalonado
        element.dataset.index = index;
    });
    
    // Usar Intersection Observer para mejor rendimiento en la detección de elementos visibles
    const observerOptions = {
        root: null, // viewport
        rootMargin: "0px",
        threshold: config.fadeOffset
    };
    
    const fadeObserver = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                const element = entry.target;
                const index = parseInt(element.dataset.index) || 0;
                
                // Aplicar retraso escalonado basado en el índice para un efecto en cascada
                const delay = index * config.staggerDelay;
                
                // Usar setTimeout para crear un efecto escalonado
                setTimeout(() => {
                    element.style.opacity = "1";
                    element.style.transform = "translateY(0)";
                }, delay * 1000);
                
                // Dejar de observar una vez que el elemento es visible
                fadeObserver.unobserve(element);
            }
        });
    }, observerOptions);
    
    // Observar todos los elementos con fade-in
    fadeElements.forEach(element => {
        fadeObserver.observe(element);
    });
    
    // Función optimizada para manejar scroll con requestAnimationFrame
    let ticking = false;
    let lastScrollY = window.scrollY;
    
    function updateScrollIndicator() {
        if (scrollIndicator) {
            const scrollPosition = window.scrollY;
            const totalHeight = document.body.scrollHeight - window.innerHeight;
            const scrollPercentage = totalHeight > 0 ? (scrollPosition / totalHeight) * 100 : 0;
            
            // Animación suave con requestAnimationFrame
            requestAnimationFrame(() => {
                scrollIndicator.style.width = `${scrollPercentage}%`;
            });
        }
    }
    
    function updateNavbarStyle() {
        if (navbar) {
            if (window.scrollY > config.scrollThreshold) {
                if (!navbar.classList.contains('shadow')) {
                    requestAnimationFrame(() => {
                        navbar.classList.add('shadow');
                    });
                }
            } else {
                if (navbar.classList.contains('shadow')) {
                    requestAnimationFrame(() => {
                        navbar.classList.remove('shadow');
                    });
                }
            }
        }
    }
    
    // Función para actualizar la navegación activa
    function updateActiveNavigation() {
        if (sections.length === 0 || navLinks.length === 0) return;
        
        const scrollPosition = window.scrollY + 100;
        let activeSection = null;
        
        // Encontrar la sección actualmente visible
        for (let i = 0; i < sections.length; i++) {
            const section = sections[i];
            const sectionTop = section.offsetTop;
            const sectionHeight = section.offsetHeight;
            
            if (scrollPosition >= sectionTop && scrollPosition < sectionTop + sectionHeight) {
                activeSection = section;
                break;
            }
        }
        
        if (activeSection) {
            const sectionId = activeSection.getAttribute('id');
            
            // Actualizar la clase active en los enlaces de navegación
            navLinks.forEach(navLink => {
                const isActive = navLink.getAttribute('href') === `#${sectionId}`;
                
                if (isActive && !navLink.classList.contains('active')) {
                    requestAnimationFrame(() => {
                        navLink.classList.add('active');
                        navLink.setAttribute('aria-current', 'page');
                    });
                } else if (!isActive && navLink.classList.contains('active')) {
                    requestAnimationFrame(() => {
                        navLink.classList.remove('active');
                        navLink.removeAttribute('aria-current');
                    });
                }
            });
        }
    }
    
    // Optimizar el manejo del scroll con throttling y requestAnimationFrame 
    function onScroll() {
        lastScrollY = window.scrollY;
        
        if (!ticking) {
            ticking = true;
            
            requestAnimationFrame(() => {
                updateScrollIndicator();
                updateNavbarStyle();
                updateActiveNavigation();
                ticking = false;
            });
        }
    }
    
    // Implementar smooth scrolling mejorado
    navLinks.forEach(anchor => {
        anchor.addEventListener('click', function(e) {
            e.preventDefault();
            
            const targetId = this.getAttribute('href');
            if (targetId === '#') return;
            
            try {
                const targetElement = document.querySelector(targetId);
                if (targetElement) {
                    // Calcular la posición de desplazamiento
                    const elementTop = targetElement.getBoundingClientRect().top;
                    const offsetPosition = window.scrollY + elementTop;
                    
                    // Implementar scroll suave personalizado con easeInOutQuad
                    const startPosition = window.scrollY;
                    const distance = offsetPosition - startPosition;
                    const duration = 800; // ms
                    let start = null;
                    
                    function easeInOutQuad(t) {
                        return t < 0.5 ? 2 * t * t : -1 + (4 - 2 * t) * t;
                    }
                    
                    function step(timestamp) {
                        if (!start) start = timestamp;
                        const progress = timestamp - start;
                        const time = Math.min(1, progress / duration);
                        
                        window.scrollTo(0, startPosition + distance * easeInOutQuad(time));
                        
                        if (progress < duration) {
                            window.requestAnimationFrame(step);
                        } else {
                            // Activar la navegación una vez completado el desplazamiento
                            navLinks.forEach(navLink => {
                                if (navLink.getAttribute('href') === targetId) {
                                    navLink.classList.add('active');
                                    navLink.setAttribute('aria-current', 'page');
                                } else {
                                    navLink.classList.remove('active');
                                    navLink.removeAttribute('aria-current');
                                }
                            });
                        }
                    }
                    
                    window.requestAnimationFrame(step);
                }
            } catch (error) {
                console.error(`Error al desplazarse hacia ${targetId}:`, error);
            }
        });
    });
    
    // Usar passive: true para mejorar el rendimiento
    window.addEventListener('scroll', onScroll, { passive: true });
    
    // Configurar un evento resize optimizado
    let resizeTimeout;
    window.addEventListener('resize', function() {
        clearTimeout(resizeTimeout);
        resizeTimeout = setTimeout(() => {
            // Recalcular valores basados en ventana al cambiar tamaño
            onScroll();
        }, 100);
    }, { passive: true });
    
    // Ejecutar una vez para establecer el estado inicial
    onScroll();
    
    // Añadir efecto de animación inicial para la sección hero
    const heroSection = document.querySelector('.hero');
    if (heroSection) {
        requestAnimationFrame(() => {
            heroSection.style.opacity = "0";
            heroSection.style.transform = "translateY(20px)";
            heroSection.style.transition = "opacity 1s ease-out, transform 1s ease-out";
            
            // Retrasar ligeramente para asegurar que la transición sea visible
            setTimeout(() => {
                heroSection.style.opacity = "1";
                heroSection.style.transform = "translateY(0)";
            }, 100);
        });
    }
    
    // Añadir clase para habilitar todas las transiciones después de la carga
    document.body.classList.add('transitions-enabled');
});
// Año dinámico
document.getElementById('year').textContent = new Date().getFullYear();
document.getElementById('generation-date').textContent = new Date().toLocaleDateString('es-CO', {
  year: 'numeric',
  month: 'long',
  day: 'numeric',
  hour: '2-digit',
  minute: '2-digit'
});

// Indicador de scroll mejorado
window.addEventListener('scroll', function () {
  const scrollTop = document.documentElement.scrollTop || document.body.scrollTop;
  const scrollHeight = document.documentElement.scrollHeight - document.documentElement.clientHeight;
  const scrolled = (scrollTop / scrollHeight) * 100;
  document.getElementById('scrollIndicator').style.width = scrolled + '%';
});

// Overlay con barra de progreso moderna (IDÉNTICO a políticas)
function createProgressOverlay() {
  const overlay = document.createElement("div");
  overlay.id = "progressOverlay";
  overlay.className = "progress-overlay";
  overlay.style = `
    position: fixed; top: 0; left: 0; width: 100%; height: 100%;
    background: rgba(0,0,0,0.7); backdrop-filter: blur(12px);
    display: flex; justify-content: center; align-items: center; z-index: 11000;
    animation: fadeIn 0.3s ease-out;
  `;

  overlay.innerHTML = `
    <div class="progress-card p-4 text-center shadow-lg" style="max-width:350px;width:90%; background: rgba(255,255,255,0.98); border-radius: 20px; border: 2px solid rgba(253, 126, 20, 0.2);">
      <div class="mb-3">
        <i class="fas fa-file-pdf fa-3x mb-2 pulse-animation" style="color:#fd7e14;"></i>
      </div>
      <h5 class="fw-bold mb-2" style="color:#1e293b; font-family: 'Inter', sans-serif;">Generando PDF</h5>
      <p class="text-muted mb-3 small">Preparando tu documento de términos y condiciones...</p>
      <div class="progress mb-3" style="height: 24px; border-radius: 12px; background: rgba(253, 126, 20, 0.1);">
        <div id="progressBar" class="progress-bar progress-bar-striped progress-bar-animated" 
             role="progressbar" style="width: 0%; background: linear-gradient(90deg, #fd7e14, #f97316); border-radius: 12px; font-weight: 600; font-size: 12px;">
          0%
        </div>
      </div>
      <div class="d-flex align-items-center justify-content-center">
        <div class="spinner-border spinner-border-sm me-2" style="color: #fd7e14;" role="status"></div>
        <small class="text-muted">Esto puede tomar unos segundos...</small>
      </div>
    </div>
  `;

  document.body.appendChild(overlay);

  // Animación de entrada
  requestAnimationFrame(() => {
    overlay.style.opacity = '1';
  });
}

function updateProgress(value) {
  const bar = document.getElementById("progressBar");
  if (bar) {
    bar.style.width = value + "%";
    bar.textContent = value + "%";

    // Cambiar color según progreso (IDÉNTICO a políticas)
    if (value >= 90) {
      bar.style.background = "linear-gradient(90deg, #10b981, #059669)";
    } else if (value >= 70) {
      bar.style.background = "linear-gradient(90deg, #f59e0b, #d97706)";
    }
  }
}

function removeProgressOverlay() {
  const overlay = document.getElementById("progressOverlay");
  if (overlay) {
    overlay.style.animation = "fadeOut 0.3s ease-out";
    setTimeout(() => overlay.remove(), 300);
  }
}

// Toast de confirmación mejorado con sonido (IDÉNTICO a políticas)
function showSuccessToast() {
  // Remover toast anterior si existe
  const existingToast = document.getElementById('successToast');
  if (existingToast) {
    existingToast.remove();
  }

  const container = document.createElement('div');
  container.className = "toast-container position-fixed";
  container.style.cssText = "bottom: 30px; right: 30px; z-index: 12000;";

  container.innerHTML = `
    <div id="successToast" class="toast modern-toast align-items-center text-white border-0 shadow-lg fade-in-up" 
         role="alert" aria-live="assertive" aria-atomic="true"
         style="background: linear-gradient(135deg, #10b981, #059669) !important; min-width: 320px; border-radius: 15px; backdrop-filter: blur(10px);">
      <div class="d-flex align-items-center p-3">
        <div class="toast-icon me-3">
          <i class="fas fa-check-circle fa-lg" style="color: #fff;"></i>
        </div>
        <div class="flex-grow-1">
          <div class="d-flex align-items-center mb-1">
            <h6 class="mb-0 fw-bold me-2">¡Descarga exitosa!</h6>
            <i class="fas fa-sparkles" style="color: #fbbf24;"></i>
          </div>
          <small class="opacity-90">Tu archivo PDF se ha generado correctamente</small>
        </div>
        <button type="button" class="btn-close btn-close-white ms-3 opacity-75" data-bs-dismiss="toast" aria-label="Cerrar"></button>
      </div>
      <div class="progress" style="height: 3px; background: rgba(255,255,255,0.2);">
        <div class="progress-bar bg-white" role="progressbar" style="width: 100%; animation: progressShrink 4s linear;"></div>
      </div>
    </div>
  `;

  document.body.appendChild(container);
  const toastEl = document.getElementById('successToast');

  // Agregar animación personalizada para la barra de progreso
  const style = document.createElement('style');
  style.textContent = `
    @keyframes progressShrink {
      from { width: 100%; }
      to { width: 0%; }
    }
    @keyframes fadeIn {
      from { opacity: 0; }
      to { opacity: 1; }
    }
    @keyframes fadeOut {
      from { opacity: 1; }
      to { opacity: 0; }
    }
  `;
  document.head.appendChild(style);

  // Sonido de notificación mejorado
  playSuccessSound();

  // Mostrar el toast con Bootstrap
  const toast = new bootstrap.Toast(toastEl, {
    delay: 4500,
    animation: true
  });
  toast.show();

  // Limpiar después de mostrar
  setTimeout(() => {
    container.remove();
    style.remove();
  }, 5000);
}

// Sonido de éxito más elegante (IDÉNTICO a políticas)
function playSuccessSound() {
  try {
    const audioContext = new (window.AudioContext || window.webkitAudioContext)();

    // Secuencia de tonos para sonido más elegante
    const notes = [
      { freq: 523.25, time: 0, duration: 0.15 }, // C5
      { freq: 659.25, time: 0.1, duration: 0.15 }, // E5
      { freq: 783.99, time: 0.2, duration: 0.25 }  // G5
    ];

    notes.forEach(note => {
      setTimeout(() => {
        const oscillator = audioContext.createOscillator();
        const gainNode = audioContext.createGain();

        oscillator.type = 'sine';
        oscillator.frequency.setValueAtTime(note.freq, audioContext.currentTime);

        gainNode.gain.setValueAtTime(0, audioContext.currentTime);
        gainNode.gain.linearRampToValueAtTime(0.1, audioContext.currentTime + 0.05);
        gainNode.gain.exponentialRampToValueAtTime(0.001, audioContext.currentTime + note.duration);

        oscillator.connect(gainNode);
        gainNode.connect(audioContext.destination);

        oscillator.start(audioContext.currentTime);
        oscillator.stop(audioContext.currentTime + note.duration);
      }, note.time * 1000);
    });
  } catch (err) {
    console.warn("No se pudo reproducir el sonido:", err);
  }
}

// Generar PDF PROFESIONAL - IDÉNTICO al de Políticas de Privacidad
document.getElementById('downloadPdf').addEventListener('click', function () {
  const { jsPDF } = window.jspdf;
  const element = document.getElementById('contentToPrint');

  // Ocultar botón y mostrar progreso
  const btnDownload = document.querySelector('.btn-download');
  btnDownload.style.display = 'none';
  createProgressOverlay();

  // Ocultar indicador de scroll durante la generación
  const scrollIndicator = document.getElementById('scrollIndicator');
  const originalScrollDisplay = scrollIndicator.style.display;
  scrollIndicator.style.display = 'none';

  // Configuración IDÉNTICA a la de políticas de privacidad
  html2canvas(element, {
    scale: 2,
    useCORS: true,
    logging: false,
    backgroundColor: '#ffffff',
    onclone: function (clonedDoc) {
      // Asegurar que el contenido se vea bien en el PDF
      clonedDoc.getElementById('contentToPrint').style.padding = '20px';
    }
  }).then(canvas => {
    updateProgress(90);

    const imgData = canvas.toDataURL('image/png', 1.0);
    const pdf = new jsPDF({
      orientation: 'portrait',
      unit: 'mm',
      format: 'a4',
      compress: true
    });

    const imgProps = pdf.getImageProperties(imgData);
    const pdfWidth = pdf.internal.pageSize.getWidth();
    const pdfHeight = pdf.internal.pageSize.getHeight();

    // Margenes de 15mm para mejor presentación (IGUAL que políticas)
    const margin = 15;
    const contentWidth = pdfWidth - (margin * 2);
    const contentHeight = (imgProps.height * contentWidth) / imgProps.width;

    // Calcular el número total de páginas
    let heightLeft = contentHeight;
    let position = margin;

    // Agregar primera página
    pdf.addImage(imgData, 'PNG', margin, position, contentWidth, contentHeight, undefined, 'FAST');
    heightLeft -= pdfHeight;

    // Agregar páginas adicionales si es necesario
    while (heightLeft >= 0) {
      position = heightLeft - contentHeight;
      pdf.addPage();
      pdf.addImage(imgData, 'PNG', margin, position, contentWidth, contentHeight, undefined, 'FAST');
      heightLeft -= pdfHeight;
    }

    updateProgress(95);

    // Nombre del archivo (mismo formato que políticas)
    const timestamp = new Date().toISOString().slice(0, 19).replace(/[:-]/g, '');
    const filename = `Terminos_Condiciones_Infojis.pdf`;

    // Guardar PDF
    pdf.save(filename);
    updateProgress(100);

    // Restaurar UI
    setTimeout(() => {
      removeProgressOverlay();
      btnDownload.style.display = 'block';
      scrollIndicator.style.display = originalScrollDisplay;
      showSuccessToast();
    }, 800);

  }).catch(error => {
    console.error("Error al generar PDF:", error);
    removeProgressOverlay();
    btnDownload.style.display = 'block';
    scrollIndicator.style.display = originalScrollDisplay;
    showErrorToast();
  });
});

// Toast de error (IDÉNTICO a políticas)
function showErrorToast() {
  const container = document.createElement('div');
  container.className = "toast-container position-fixed";
  container.style.cssText = "bottom: 30px; right: 30px; z-index: 12000;";

  container.innerHTML = `
    <div class="toast align-items-center text-white border-0 shadow-lg fade-in-up" 
         role="alert" aria-live="assertive" aria-atomic="true"
         style="background: linear-gradient(135deg, #ef4444, #dc2626); min-width: 320px; border-radius: 15px;">
      <div class="d-flex align-items-center p-3">
        <div class="toast-icon me-3">
          <i class="fas fa-exclamation-triangle fa-lg" style="color: #fff;"></i>
        </div>
        <div class="flex-grow-1">
          <h6 class="mb-0 fw-bold">Error al generar PDF</h6>
          <small class="opacity-90">Por favor, inténtalo nuevamente</small>
        </div>
        <button type="button" class="btn-close btn-close-white ms-3" data-bs-dismiss="toast"></button>
      </div>
    </div>
  `;

  document.body.appendChild(container);
  const toast = new bootstrap.Toast(container.querySelector('.toast'), { delay: 4000 });
  toast.show();

  setTimeout(() => container.remove(), 5000);
}

// Botón volver atrás con animación
document.querySelector('.btn-back').addEventListener('click', function (e) {
  e.preventDefault();
  this.style.transform = 'scale(0.95)';
  setTimeout(() => {
    this.style.transform = '';
    window.history.back();
  }, 150);
});

// Alerta inicial mejorada (IDÉNTICA a políticas)
window.addEventListener('DOMContentLoaded', () => {
  try {
    const alertBox = document.createElement('div');
    alertBox.className = 'alert alert-warning alert-dismissible fade show position-fixed top-0 start-50 translate-middle-x mt-3 shadow';
    alertBox.style.zIndex = '10000';
    alertBox.setAttribute('role', 'alert');
    alertBox.innerHTML = `
      <strong><i class="fas fa-exclamation-triangle me-2"></i>Importante:</strong> 
      Al usar este sistema, usted acepta nuestros Términos y Condiciones.
      <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
    `;
    document.body.appendChild(alertBox);
    setTimeout(() => {
      if (window.bootstrap && window.bootstrap.Alert) {
        const bsAlert = new bootstrap.Alert(alertBox);
        bsAlert.close();
      } else {
        alertBox.remove();
      }
    }, 5000);
  } catch (_) { }
});

// Efectos adicionales de interactividad (CON ANIMACIÓN DE TÍTULO CORREGIDA)
document.addEventListener('DOMContentLoaded', function () {
  // Efecto hover para botones
  document.querySelectorAll('button, .btn').forEach(btn => {
    btn.addEventListener('mouseenter', function () {
      this.style.transition = 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)';
    });
  });

  // Smooth scroll para enlaces internos
  document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', function (e) {
      e.preventDefault();
      const target = document.querySelector(this.getAttribute('href'));
      if (target) {
        target.scrollIntoView({
          behavior: 'smooth',
          block: 'start'
        });
      }
    });
  });

  // Efecto de typing para el título principal - CORREGIDO
  const titleElement = document.querySelector('.pdf-title');
  if (titleElement && titleElement.textContent) {
    const originalText = titleElement.textContent;
    titleElement.textContent = '';

    let i = 0;
    const typingSpeed = 50;

    function typeWriter() {
      if (i < originalText.length) {
        titleElement.textContent += originalText.charAt(i);
        i++;
        setTimeout(typeWriter, typingSpeed);
      }
    }

    // Iniciar efecto después de un breve delay
    setTimeout(typeWriter, 500);
  }

  // Contador de caracteres/palabras en tiempo real para desarrollo
  if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
    const contentElement = document.getElementById('contentToPrint');
    if (contentElement) {
      const wordCount = contentElement.textContent.trim().split(/\s+/).length;
      console.log(`📊 Estadísticas del documento:
        - Palabras: ${wordCount}
        - Caracteres: ${contentElement.textContent.length}
        - Secciones: ${contentElement.querySelectorAll('.pdf-section').length}`);
    }
  }
});

// Función para detectar modo oscuro del sistema
function detectDarkMode() {
  if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) {
    document.body.classList.add('dark-mode-preference');
  }
}

// Función para manejar errores globales de manera elegante
window.addEventListener('error', function (e) {
  console.error('Error capturado:', e.error);
  // No mostrar errores al usuario a menos que sea crítico
});

// Optimización de rendimiento: lazy loading para imágenes
document.addEventListener('DOMContentLoaded', function () {
  if ('IntersectionObserver' in window) {
    const imageObserver = new IntersectionObserver((entries, observer) => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          const img = entry.target;
          if (img.dataset.src) {
            img.src = img.dataset.src;
            img.removeAttribute('data-src');
            imageObserver.unobserve(img);
          }
        }
      });
    });

    document.querySelectorAll('img[data-src]').forEach(img => {
      imageObserver.observe(img);
    });
  }
});

// Preload de recursos críticos
function preloadCriticalResources() {
  const criticalResources = [
    'https://cdnjs.cloudflare.com/ajax/libs/jspdf/2.5.1/jspdf.umd.min.js',
    'https://cdnjs.cloudflare.com/ajax/libs/html2canvas/1.4.1/html2canvas.min.js'
  ];

  criticalResources.forEach(url => {
    const link = document.createElement('link');
    link.rel = 'preload';
    link.href = url;
    link.as = 'script';
    document.head.appendChild(link);
  });
}

// Inicializar preload al cargar la página
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', preloadCriticalResources);
} else {
  preloadCriticalResources();
}

// Detectar preferencias del usuario
detectDarkMode();

// Service Worker registration para mejor rendimiento (opcional)
if ('serviceWorker' in navigator && window.location.protocol === 'https:') {
  navigator.serviceWorker.register('/sw.js').catch(() => {
    // Silenciar error si no hay service worker
  });
}
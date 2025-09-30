document.addEventListener('DOMContentLoaded', () => {
    // Toggle sidebar móvil (mostrar u ocultar siddbar en teléfonos)
    const sidebar = document.getElementById('sidebar');
    const sidebarElements = [
        document.getElementById('sidebar-toggle'),
        document.getElementById('sidebar-overlay')
    ].filter(Boolean);

    const toggleSidebar = () => {
        ['active'].forEach(state => {
            sidebar.classList.toggle(state);
            sidebarElements[1]?.classList.toggle(state);
        });
    };

    sidebarElements.forEach(element => element.addEventListener('click', toggleSidebar));

    // Modal de cerrar sesión
    const modalHTML = `
    <div class="modal fade" id="logoutModal" tabindex="-1" aria-hidden="true">
        <div class="modal-dialog modal-dialog-centered">
            <div class="modal-content">
                <div class="modal-header bg-primary text-white">
                    <h5 class="modal-title">Cerrar sesión</h5>
                    <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal" aria-label="Close"></button>
                </div>
                <div class="modal-body text-center">
                    <i class="fas fa-sign-out-alt text-primary mb-3" style="font-size: 3rem;"></i>
                    <p>¿Estás seguro que deseas cerrar tu sesión?</p>
                </div>
                <div class="modal-footer">
                    <button type="button" class="btn btn-outline-secundary me-2" data-bs-dismiss="modal">Cancelar</button>
                    <!-- Botón en el navbar o sidebar -->
                    <a href="/auth/logout" class="btn btn-outline-primary" id="btn-confirm-logout">
                        <i class="fas fa-sign-out-alt me-2"></i> Cerrar sesión
                    </a>
                </div>
            </div>
        </div>
    </div>`;




    // Insertar modal si no existe
    if (!document.getElementById('logoutModal')) {
        document.body.insertAdjacentHTML('beforeend', modalHTML);
    }

    // Manejar clics en botones de logout
    document.querySelectorAll('.logout-button, #cerrar-sesion').forEach(btn => {
        btn.addEventListener('click', function (e) {
            e.preventDefault();
            new bootstrap.Modal(document.getElementById('logoutModal')).show();
        });
    });
});



// tiempo de espera para los mensajes de alerta flask
document.addEventListener('DOMContentLoaded', function () {
    const toastElList = [].slice.call(document.querySelectorAll('.toast'));
    toastElList.forEach(function (toastEl) {
        const toast = new bootstrap.Toast(toastEl, {
            delay: 4000
        });
        toast.show();
    });

    // Function to update notification badge
    function updateNotificationBadge() {
        fetch('/actividades/count_unread_notifications')
            .then(response => response.json())
            .then(data => {
                const notificationBadge = document.querySelector('.notification-badge');
                if (data.count > 0) {
                    if (notificationBadge) {
                        notificationBadge.textContent = data.count;
                    } else {
                        // Create badge if it doesn't exist
                        const notificationBtn = document.querySelector('.notification-btn');
                        if (notificationBtn) {
                            const newBadge = document.createElement('span');
                            newBadge.className = 'position-absolute top-0 start-100 translate-middle badge rounded-pill bg-danger notification-badge';
                            newBadge.textContent = data.count;
                            newBadge.innerHTML += '<span class="visually-hidden">nuevas notificaciones</span>';
                            notificationBtn.appendChild(newBadge);
                        }
                    }
                } else {
                    if (notificationBadge) {
                        notificationBadge.remove();
                    }
                }
            })
            .catch(error => console.error('Error fetching notification count:', error));
    }

    // tiempo de espera para actualizar notificaciones
    updateNotificationBadge();
    setInterval(updateNotificationBadge, 5000);
});

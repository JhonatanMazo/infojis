document.addEventListener('DOMContentLoaded', function () {
    // Botones de editar
    const editButtons = document.querySelectorAll('.btn-edit-usuario');
    const formEditar = document.getElementById('formEditarUsuario');

    editButtons.forEach(button => {
        button.addEventListener('click', async function () {
            const originalText = this.innerHTML;
            const loadingText = this.getAttribute('data-loading-text');

            // Mostrar spinner de carga
            this.innerHTML = loadingText;
            this.disabled = true;

            const userId = this.getAttribute('data-id');

            try {
                const response = await fetch(`/usuarios/obtener/${userId}`);
                if (!response.ok) {
                    throw new Error(`Error ${response.status}: ${response.statusText}`);
                }

                const usuario = await response.json();

                // Rellenar el formulario
                formEditar.action = `/usuarios/editar/${usuario.id}`;
                document.getElementById('edit-usuario-id').value = usuario.id;
                document.getElementById('edit-nombre').value = usuario.nombre;
                document.getElementById('edit-apellidos').value = usuario.apellidos || '';
                document.getElementById('edit-documento').value = usuario.documento;
                document.getElementById('edit-genero').value = usuario.genero;
                document.getElementById('edit-email').value = usuario.email;
                document.getElementById('edit-rol').value = usuario.rol;
                document.getElementById('edit-estado').value = usuario.estado;
                document.getElementById('edit-telefono').value = usuario.telefono || '';

                // Foto actual
                const fotoActual = document.getElementById('edit-foto-actual');
                if (usuario.foto) {
                    fotoActual.src = `/static/uploads/profiles/${usuario.foto}`;
                } else {
                    // Usar una imagen por defecto si no hay foto
                    fotoActual.src = 'data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iNDAiIGhlaWdodD0iNDAiIHZpZXdCb3g9IjAgMCA0MCA0MCIgZmlsbD0ibm9uZSIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj4KPGNpcmNsZSBjeD0iMjAiIGN5PSIyMCIgcj0iMjAiIGZpbGw9IiNmNmY2ZjYiLz4KPGcgdHJhbnNmb3JtPSJ0cmFuc2xhdGUoMTAsIDEwKSI+CjxjaXJjbGUgY3g9IjEwIiBjeT0iNyIgcj0iNCIgZmlsbD0iIzk5OTk5OSIvPgo8cGF0aCBkPSJNMiAxOGMwLTMuMzE0IDIuNjg2LTYgNi02aDRjMy4zMTQgMCA2IDIuNjg2IDYgNiIgZmlsbD0iIzk5OTk5OSIvPgo8L2c+Cjwvc3ZnPg==';
                }
                fotoActual.style.display = 'block';

            } catch (error) {
                console.error(error);
                Swal.fire({
                    icon: 'error',
                    title: 'Error',
                    text: 'No se pudo cargar la información del usuario'
                });
            } finally {
                // Restaurar botón
                this.innerHTML = originalText;
                this.disabled = false;
            }
        });
    });

    // Confirmación para eliminar
    const deleteButtons = document.querySelectorAll('.btn-eliminar-usuario');
    deleteButtons.forEach(button => {
        button.addEventListener('click', function (e) {
            e.preventDefault();
            const form = this.closest('form');
            const nombre = this.dataset.nombre; // <-- AQUÍ se obtiene correctamente el nombre

            Swal.fire({
                title: 'Eliminar usuario',
                html: `¿Estás seguro de eliminar al usuario <strong>${nombre}</strong>?`,
                icon: 'warning',
                showCancelButton: true,
                confirmButtonColor: '#d33',
                cancelButtonColor: '#6c757d',
                confirmButtonText: 'Sí, eliminar'
            }).then((result) => {
                if (result.isConfirmed) {
                    form.submit();
                }
            });
        });
    });


    // Filtros
    const btnFiltrar = document.getElementById('btn-filtrar');
    if (btnFiltrar) {
        btnFiltrar.addEventListener('click', () => {
            const estado = document.getElementById('filtro_estado').value;
            const rol = document.getElementById('filtro_rol').value;
            const url = new URL(window.location.href);

            if (estado) {
                url.searchParams.set('estado', estado);
            } else {
                url.searchParams.delete('estado');
            }
            if (rol) {
                url.searchParams.set('rol', rol);
            } else {
                url.searchParams.delete('rol');
            }
            url.searchParams.set('page', 1); // Ir a la primera página

            window.location.href = url.toString();
        });
    }

    // Validación de formulario en cliente
    const nuevoUsuarioForm = document.querySelector('#modalNuevoUsuario form');
    if (nuevoUsuarioForm) {
        nuevoUsuarioForm.addEventListener('submit', function (e) {
            const password = this.querySelector('[name="contraseña"]').value;
            const email = this.querySelector('[name="email"]').value;

            // Validar formato de email
            if (!/\S+@\S+\.\S+/.test(email)) {
                e.preventDefault();
                Swal.fire('Error', 'Por favor ingrese un email válido', 'error');
                return;
            }

            // Validar fortaleza de contraseña
            if (password && !/(?=.*[A-Za-z])(?=.*\d).{8,}/.test(password)) {
                e.preventDefault();
                Swal.fire('Error', 'La contraseña debe tener al menos 8 caracteres, una letra y un número', 'error');
            }
        });
    }
});
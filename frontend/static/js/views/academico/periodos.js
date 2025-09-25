document.addEventListener('DOMContentLoaded', function () {
    // Editar período
    const editButtons = document.querySelectorAll('.btn-edit-periodo');
    const formEditar = document.getElementById('formEditarPeriodo');

    editButtons.forEach(button => {
        button.addEventListener('click', () => {
            const id = button.getAttribute('data-id');
            const nombre = button.getAttribute('data-nombre');
            const fechaInicio = button.getAttribute('data-fecha-inicio');
            const fechaFin = button.getAttribute('data-fecha-fin');

            formEditar.action = `/periodos/editar/${id}`;
            formEditar.querySelector('#edit-nombre').value = nombre;
            formEditar.querySelector('#edit-fecha-inicio').value = fechaInicio;
            formEditar.querySelector('#edit-fecha-fin').value = fechaFin;
        });
    });

    // Eliminar período con confirmación y CSRF
    const deleteButtons = document.querySelectorAll('.btn-eliminar-periodo');
    const formEliminar = document.getElementById('formEliminarPeriodo'); // formulario oculto en HTML

    deleteButtons.forEach(button => {
        button.addEventListener('click', () => {
            const id = button.getAttribute('data-id');
            const nombre = button.getAttribute('data-nombre');

            Swal.fire({
                title: `Eliminar período`,
                html: `¿Está seguro que desea eliminar el período <strong>${nombre}</strong>?`,
                icon: 'warning',
                showCancelButton: true,
                confirmButtonColor: '#d33',
                cancelButtonColor: '#6c757d',
                confirmButtonText: 'Sí, eliminar'
            }).then((result) => {
                if (result.isConfirmed) {
                    formEliminar.action = `/periodos/eliminar/${id}`;
                    formEliminar.submit();
                }
            });
        });
    });

    // Function to validate MM-DD format and real date
    function isValidMonthDay(dateString) {
        const parts = dateString.split('-');
        if (parts.length !== 2) return false;

        const month = parseInt(parts[0], 10);
        const day = parseInt(parts[1], 10);

        if (isNaN(month) || isNaN(day)) return false;
        if (month < 1 || month > 12) return false;
        if (day < 1 || day > 31) return false;

        // Use a dummy year to create a Date object and check for validity
        // e.g., new Date(2000, 1, 30) for Feb 30th will become Mar 1st
        const testDate = new Date(2000, month - 1, day); // Month is 0-indexed
        return testDate.getMonth() === month - 1 && testDate.getDate() === day;
    }

    // Function to compare start and end dates
    function isEndDateAfterStartDate(startDateString, endDateString) {
        const startParts = startDateString.split('-');
        const endParts = endDateString.split('-');

        const startMonth = parseInt(startParts[0], 10);
        const startDay = parseInt(startParts[1], 10);
        const endMonth = parseInt(endParts[0], 10);
        const endDay = parseInt(endParts[1], 10);

        // Use a dummy year to create Date objects for comparison
        const startDate = new Date(2000, startMonth - 1, startDay);
        const endDate = new Date(2000, endMonth - 1, endDay);

        return endDate > startDate;
    }

    // Function to check for date overlaps with existing periods
    async function checkForDateOverlaps(fechaInicio, fechaFin, periodoId = null) {
        try {
            // Convert dates to full format for comparison
            const [startMonth, startDay] = fechaInicio.split('-').map(Number);
            const [endMonth, endDay] = fechaFin.split('-').map(Number);

            const startDate = new Date(2000, startMonth - 1, startDay);
            const endDate = new Date(2000, endMonth - 1, endDay);

            // Get all existing periods
            const response = await fetch('/periodos/json/all');
            if (!response.ok) throw new Error('Error al obtener períodos existentes');

            const periodos = await response.json();

            // Check for overlaps
            for (const periodo of periodos) {
                // Skip the current period if we're editing
                if (periodoId && periodo.id === parseInt(periodoId)) continue;

                const [existStartMonth, existStartDay] = periodo.fecha_inicio.split('-').map(Number);
                const [existEndMonth, existEndDay] = periodo.fecha_fin.split('-').map(Number);

                const existStartDate = new Date(2000, existStartMonth - 1, existStartDay);
                const existEndDate = new Date(2000, existEndMonth - 1, existEndDay);

                // Check if dates overlap
                if ((startDate <= existEndDate && endDate >= existStartDate)) {
                    return {
                        overlap: true,
                        periodoNombre: periodo.nombre
                    };
                }
            }

            return { overlap: false };
        } catch (error) {
            console.error('Error checking date overlaps:', error);
            // If there's an error, we'll let the server handle the validation
            return { overlap: false };
        }
    }

    // Function to handle form validation
    async function validatePeriodoForm(form, isEdit = false) {
        const nombre = form.querySelector('[name="nombre"]').value;
        const fechaInicio = form.querySelector('[name="fecha_inicio"]').value;
        const fechaFin = form.querySelector('[name="fecha_fin"]').value;
        const periodoId = isEdit ? form.action.split('/').pop() : null;

        if (!nombre) {
            Swal.fire('Error', 'El nombre del período es obligatorio.', 'error');
            return false;
        }

        if (!isValidMonthDay(fechaInicio)) {
            Swal.fire('Error', 'Formato de fecha de inicio inválido o fecha no real (ej. 02-30). Use MM-DD.', 'error');
            return false;
        }

        if (!isValidMonthDay(fechaFin)) {
            Swal.fire('Error', 'Formato de fecha de fin inválido o fecha no real (ej. 02-30). Use MM-DD.', 'error');
            return false;
        }

        if (!isEndDateAfterStartDate(fechaInicio, fechaFin)) {
            Swal.fire('Error', 'La fecha de fin debe ser posterior a la fecha de inicio.', 'error');
            return false;
        }

        // Check for date overlaps
        const overlapCheck = await checkForDateOverlaps(fechaInicio, fechaFin, periodoId);
        if (overlapCheck.overlap) {
            Swal.fire('Error', `Las fechas se cruzan con el período <strong>${overlapCheck.periodoNombre}</strong>. Por favor, elija otras fechas.`, 'error');
            return false;
        }

        return true;
    }

    // Get the create form and edit form
    const formCrear = document.querySelector('#modalPeriodo form');
    const formEditarPeriodo = document.querySelector('#modalEditarPeriodo form');

    // Add submit event listener for create form
    if (formCrear) {
        formCrear.addEventListener('submit', async function (event) {
            event.preventDefault(); // Prevent default form submission

            const isValid = await validatePeriodoForm(this, false);
            if (isValid) {
                this.submit(); // Submit the form if validation passes
            }
        });
    }

    // Add submit event listener for edit form
    if (formEditarPeriodo) {
        formEditarPeriodo.addEventListener('submit', async function (event) {
            event.preventDefault(); // Prevent default form submission

            const isValid = await validatePeriodoForm(this, true);
            if (isValid) {
                this.submit(); // Submit the form if validation passes
            }
        });
    }

    // Add real-time validation for date inputs
    const fechaInputs = document.querySelectorAll('input[name="fecha_inicio"], input[name="fecha_fin"]');
    fechaInputs.forEach(input => {
        input.addEventListener('input', function () { // Changed from 'blur' to 'input' for real-time feedback
            const value = this.value;
            const parent = this.parentNode;
            let errorDiv = parent.querySelector('.invalid-feedback');

            if (value && !isValidMonthDay(value)) {
                this.classList.add('is-invalid');
                if (!errorDiv) {
                    errorDiv = document.createElement('div');
                    errorDiv.className = 'invalid-feedback';
                    parent.appendChild(errorDiv);
                }
                errorDiv.textContent = 'Formato inválido. Use MM-DD (ej: 01-15)';
            } else {
                this.classList.remove('is-invalid');
                if (errorDiv) {
                    errorDiv.remove();
                }
            }
        });
    });
});
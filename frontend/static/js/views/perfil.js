document.addEventListener('DOMContentLoaded', function() {
    // Validación de contraseña en tiempo real
    const newPasswordInput = document.getElementById('new-password');
    const confirmPasswordInput = document.getElementById('confirm-password');
    const passwordStrength = document.querySelector('.password-strength');
    
    if (newPasswordInput) {
        newPasswordInput.addEventListener('input', function() {
            const password = newPasswordInput.value;
            let strength = 'weak';
            let color = 'red';
            
            if (password.length >= 4) {
                strength = 'medium';
                color = 'orange';
            }
            
            if (password.length >= 8 && /[A-Z]/.test(password) && /[0-9]/.test(password) && /[^A-Za-z0-9]/.test(password)) {
                strength = 'strong';
                color = 'green';
            }
            
            passwordStrength.className = `password-strength ${strength}`;
            passwordStrength.style.backgroundColor = color;
            passwordStrength.style.height = '5px';
            passwordStrength.style.width = '100%';
            passwordStrength.style.borderRadius = '2px';
            passwordStrength.style.transition = 'all 0.3s ease';
        });
        
        // Validar coincidencia de contraseñas
        confirmPasswordInput.addEventListener('input', function() {
            if (newPasswordInput.value !== confirmPasswordInput.value) {
                confirmPasswordInput.setCustomValidity('Las contraseñas no coinciden');
            } else {
                confirmPasswordInput.setCustomValidity('');
            }
        });
    }
    
    // Manejo de formulario de perfil
    const profileForm = document.getElementById('profile-form');
    if (profileForm) {
        profileForm.addEventListener('submit', function(e) {
            const emailInput = document.getElementById('email');
            const email = emailInput.value.trim();
            
            // Validación básica de email
            if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
                e.preventDefault();
                Swal.fire({
                    icon: 'error',
                    title: 'Correo inválido',
                    text: 'Por favor ingresa un correo electrónico válido'
                });
            }
        });
    }
});
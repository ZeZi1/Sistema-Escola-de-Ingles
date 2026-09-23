// static/js/auth.js
function togglePassword() {
    const input = document.getElementById('pass');
    if (input) {
        input.type = input.type === 'password' ? 'text' : 'password';
    }
}
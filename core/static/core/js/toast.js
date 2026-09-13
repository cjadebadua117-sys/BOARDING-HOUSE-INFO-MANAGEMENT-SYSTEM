(function () {
    var ICONS = { success: '<i class="bi bi-check-circle-fill"></i>', error: '<i class="bi bi-x-circle-fill"></i>', warning: '<i class="bi bi-exclamation-triangle-fill"></i>', info: '<i class="bi bi-info-circle-fill"></i>' };
    var TITLES = { success: 'Success', error: 'Error', warning: 'Heads up', info: 'Notice' };
    var container = document.getElementById('toast-container');
    if (!container) return;
    function createToast(type, title, message, duration) {
        duration = duration || 5000;
        if (!ICONS[type]) type = 'info';
        var toast = document.createElement('div');
        toast.className = 'bhims-toast ' + type;
        toast.setAttribute('role', 'status');
        toast.setAttribute('aria-live', 'polite');
        toast.innerHTML = '<div class="toast-icon">' + ICONS[type] + '</div><div class="toast-content"><div class="toast-title"></div><div class="toast-message"></div></div><button type="button" class="toast-close" aria-label="Close">&times;</button><div class="progress-track"><div class="progress-bar"></div></div>';
        toast.querySelector('.toast-title').textContent = title;
        toast.querySelector('.toast-message').textContent = message;
        var bar = toast.querySelector('.progress-bar');
        bar.style.animation = 'bhimsTimer ' + duration + 'ms linear forwards';
        container.appendChild(toast);
        var timer = setTimeout(function () { removeToast(toast); }, duration);
        toast.addEventListener('mouseenter', function () { clearTimeout(timer); bar.style.animationPlayState = 'paused'; });
        toast.addEventListener('mouseleave', function () { bar.style.animationPlayState = 'running'; timer = setTimeout(function () { removeToast(toast); }, duration); });
        toast.querySelector('.toast-close').addEventListener('click', function () { removeToast(toast); });
    }
    function removeToast(toast) {
        toast.style.animation = 'bhimsFadeOut 0.4s ease forwards';
        toast.addEventListener('animationend', function () { toast.remove(); }, { once: true });
    }
    window.createToast = createToast;
    window.bhimsToast = createToast;
})();

(function () {
    var html = document.documentElement;
    var toggles = document.querySelectorAll('[data-theme-toggle]');
    var savedTheme = 'light';
    try { savedTheme = localStorage.getItem('bhims-theme') || 'light'; } catch (e) {}
    html.setAttribute('data-theme', savedTheme);
    toggles.forEach(function (toggle) {
        toggle.checked = savedTheme === 'dark';
        toggle.addEventListener('change', function () {
            var theme = this.checked ? 'dark' : 'light';
            html.setAttribute('data-theme', theme);
            try { localStorage.setItem('bhims-theme', theme); } catch (e) {}
            document.querySelectorAll('[data-theme-toggle]').forEach(function (el) { el.checked = theme === 'dark'; });
        });
    });
})();

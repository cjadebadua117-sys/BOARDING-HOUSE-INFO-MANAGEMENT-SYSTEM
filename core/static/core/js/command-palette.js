(function () {
    document.addEventListener('keydown', function (e) {
        if ((e.metaKey || e.ctrlKey) && e.key === 'k') { e.preventDefault(); toggle(); }
        if (e.key === 'Escape' && document.querySelector('.cp-modal.active')) close();
    });
    function toggle() { var m = document.querySelector('.cp-modal'); if (m && m.classList.contains('active')) close(); else open(); }
    function open() { if (!document.querySelector('.cp-modal')) build(); var m = document.querySelector('.cp-modal'); m.classList.add('active'); m.querySelector('input').value = ''; m.querySelector('input').focus(); }
    function close() { var m = document.querySelector('.cp-modal'); if (m) m.classList.remove('active'); }
    function build() {
        var modal = document.createElement('div'); modal.className = 'cp-overlay';
        modal.innerHTML = '<div class="cp-modal"><div class="cp-input-wrap"><i class="bi bi-search"></i><input type="text" placeholder="Search..." autocomplete="off"></div><div class="cp-results"></div><div class="cp-footer">Press ESC to close</div></div>';
        document.body.appendChild(modal);
        var input = modal.querySelector('input'); var results = modal.querySelector('.cp-results');
        var items = []; var links = document.querySelectorAll('a[href], button[data-action]');
        links.forEach(function (a) { var href = a.getAttribute('href'); var text = (a.textContent || '').trim(); if (href && text && text.length < 60) items.push({ text: text, href: href }); });
        input.addEventListener('input', function () { var q = input.value.toLowerCase(); results.innerHTML = ''; if (!q) { close(); return; } var matched = items.filter(function (i) { return i.text.toLowerCase().indexOf(q) !== -1; }).slice(0, 8); matched.forEach(function (m) { var d = document.createElement('div'); d.className = 'cp-item'; d.textContent = m.text; d.addEventListener('click', function () { window.location.href = m.href; }); results.appendChild(d); }); });
        modal.addEventListener('click', function (e) { if (e.target === modal) close(); });
    }
    window.toggleCommandPalette = toggle;
})();

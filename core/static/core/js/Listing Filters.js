(function () {
    var form = document.getElementById('filterForm'); var grid = document.getElementById('listingGrid'); if (!form || !grid) return;
    var skeleton = document.getElementById('listingSkeleton');
    form.addEventListener('submit', function (e) { e.preventDefault(); filter(); });
    function filter() { if (skeleton) skeleton.style.display = ''; var fd = new FormData(form); fd.set('X-Requested-With', 'XMLHttpRequest'); fetch(form.getAttribute('action') || window.location.href, { method: 'POST', body: fd, headers: { 'X-Requested-With': 'XMLHttpRequest', 'X-CSRFToken': getCookie('csrftoken') } }).then(function (r) { return r.text(); }).then(function (html) { if (skeleton) skeleton.style.display = 'none'; grid.innerHTML = html; updateURL(); }).catch(function () { if (skeleton) skeleton.style.display = 'none'; }); }
    function updateURL() { var fd = new FormData(form); var params = new URLSearchParams(); fd.forEach(function (v, k) { if (k !== 'csrfmiddlewaretoken' && k !== 'X-Requested-With') params.set(k, v); }); var url = window.location.pathname + '?' + params.toString(); window.history.replaceState({}, '', url); }
    function getCookie(name) { var v = document.cookie.match(new RegExp(name + '=([^;]+)')); return v ? decodeURIComponent(v[1]) : ''; }
    if (window.location.search) { var params = new URLSearchParams(window.location.search); params.forEach(function (v, k) { var el = document.querySelector('[name="' + k + '"]'); if (el) { if (el.type === 'checkbox') el.checked = true; else el.value = v; } }); filter(); }
})();

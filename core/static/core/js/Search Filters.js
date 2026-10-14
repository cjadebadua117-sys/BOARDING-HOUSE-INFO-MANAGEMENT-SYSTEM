(function () {
    var form = document.getElementById('searchForm'); var grid = document.getElementById('searchGrid'); if (!form || !grid) return;
    var skeleton = document.getElementById('searchSkeleton'); var debounce = null;
    form.addEventListener('input', function () { clearTimeout(debounce); debounce = setTimeout(filter, 300); });
    form.addEventListener('submit', function (e) { e.preventDefault(); filter(); });
    function filter() { if (!form.querySelector('input[name="q"]').value.trim() && !form.querySelector('select').value) return; if (skeleton) skeleton.style.display = ''; var fd = new FormData(form); fd.set('X-Requested-With', 'XMLHttpRequest'); fetch(form.getAttribute('action') || window.location.href, { method: 'GET', body: fd, headers: { 'X-Requested-With': 'XMLHttpRequest' } }).then(function (r) { return r.text(); }).then(function (html) { if (skeleton) skeleton.style.display = 'none'; grid.innerHTML = html; }).catch(function () { if (skeleton) skeleton.style.display = 'none'; }); }
})();

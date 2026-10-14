(function () {
    var acceptBtns = document.querySelectorAll('[data-action="accept"]'); var declineBtns = document.querySelectorAll('[data-action="decline"]');
    acceptBtns.forEach(function (btn) { btn.addEventListener('click', function () { fetch(btn.getAttribute('data-url'), { method: 'POST', headers: { 'X-Requested-With': 'XMLHttpRequest', 'X-CSRFToken': getCookie('csrftoken') } }).then(function (r) { return r.json(); }).then(function (d) { if (d.ok) { btn.closest('.inquiry-row').classList.add('is-accepted'); btn.textContent = 'Accepted'; btn.disabled = true; } }).catch(function () {}); }); });
    declineBtns.forEach(function (btn) { btn.addEventListener('click', function () { fetch(btn.getAttribute('data-url'), { method: 'POST', headers: { 'X-Requested-With': 'XMLHttpRequest', 'X-CSRFToken': getCookie('csrftoken') } }).then(function (r) { return r.json(); }).then(function (d) { if (d.ok) { btn.closest('.inquiry-row').classList.add('is-declined'); btn.textContent = 'Declined'; btn.disabled = true; } }).catch(function () {}); }); });
    function getCookie(name) { var v = document.cookie.match(new RegExp(name + '=([^;]+)')); return v ? decodeURIComponent(v[1]) : ''; }
})();

(function () {
    var forms = document.querySelectorAll('form[data-validate]');
    if (!forms.length) return;
    function messageFor(el) {
        var v = el.validity;
        if (v.valueMissing) return 'This field is required.';
        if (v.typeMismatch) return el.type === 'email' ? 'Enter a valid email address.' : 'Enter a valid value.';
        if (v.patternMismatch) return 'Please match the requested format.';
        if (v.tooShort) return 'Use at least ' + el.minLength + ' characters.';
        if (v.tooLong) return 'Use no more than ' + el.maxLength + ' characters.';
        if (v.rangeUnderflow || v.rangeOverflow) return 'This value is out of range.';
        return 'Please check this field.';
    }
    function labelFor(el) {
        if (el.labels && el.labels.length && el.labels[0].textContent.trim()) return el.labels[0].textContent.replace('*', '').trim();
        return (el.name || 'This field').replace(/_/g, ' ');
    }
    function showError(el, text) {
        el.setAttribute('aria-invalid', 'true');
        var err = el.nextElementSibling;
        if (!(err && err.classList && err.classList.contains('bhims-field-error'))) { err = document.createElement('div'); err.className = 'bhims-field-error'; el.insertAdjacentElement('afterend', err); }
        err.textContent = text;
    }
    function clearError(el) { el.removeAttribute('aria-invalid'); var err = el.nextElementSibling; if (err && err.classList && err.classList.contains('bhims-field-error')) err.remove(); }
    function buildSummary(form, bad) {
        var old = form.querySelector('.bhims-error-summary'); if (old) old.remove(); if (!bad.length) return;
        var box = document.createElement('div'); box.className = 'bhims-error-summary'; box.setAttribute('role', 'alert'); box.tabIndex = -1;
        var title = document.createElement('h2'); title.className = 'h5 mb-2'; title.textContent = bad.length === 1 ? 'There is 1 problem with this form' : 'There are ' + bad.length + ' problems with this form';
        box.appendChild(title); var ul = document.createElement('ul'); ul.className = 'mb-0';
        bad.forEach(function (el) { if (!el.id) el.id = 'fld-' + (el.name || Math.random().toString(36).slice(2, 8)); var li = document.createElement('li'); var a = document.createElement('a'); a.href = '#' + el.id; a.textContent = labelFor(el) + ': ' + messageFor(el); li.appendChild(a); ul.appendChild(li); });
        box.appendChild(ul); form.insertBefore(box, form.firstChild); box.focus();
    }
    Array.prototype.forEach.call(forms, function (form) {
        var fields = Array.prototype.filter.call(form.querySelectorAll('input, select, textarea'), function (el) { var t = el.type; return t !== 'hidden' && t !== 'submit' && t !== 'button' && t !== 'checkbox' && t !== 'radio'; });
        fields.forEach(function (el) {
            el.addEventListener('blur', function () { if (!el.checkValidity()) showError(el, messageFor(el)); });
            el.addEventListener('input', function () { if (el.getAttribute('aria-invalid') === 'true' && el.checkValidity()) clearError(el); });
        });
        form.addEventListener('submit', function (e) { var bad = fields.filter(function (el) { return !el.checkValidity(); }); bad.forEach(function (el) { showError(el, messageFor(el)); }); buildSummary(form, bad); if (bad.length) { e.preventDefault(); bad[0].focus(); } });
    });
})();

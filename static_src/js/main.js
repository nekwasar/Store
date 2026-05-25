import Alpine from 'alpinejs'
import 'bootstrap'
import checkboxList from './components/checkbox-list.js'
import clipboardCopy from './components/clipboard-copy.js'
import formSubmit from './components/form-submit.js'
import choices from './components/choices.js'
import datepicker from './components/datepicker.js'
import dropzone from './components/dropzone.js'
import searchSuggestions from './components/search-suggestions.js'
import authForm from './components/auth-form.js'
import cartOffcanvas from './components/cart-offcanvas.js'
import { validatePrice, validateQuantity, validateDiscount } from './components/form-validators.js'
import { notify } from './notify.js'

Alpine.data('checkboxList', checkboxList)
Alpine.data('clipboardCopy', clipboardCopy)
Alpine.data('formSubmit', formSubmit)
Alpine.data('choices', choices)
Alpine.data('datepicker', datepicker)
Alpine.data('dropzone', dropzone)
Alpine.data('searchSuggestions', searchSuggestions)
Alpine.data('authForm', authForm)
Alpine.data('cartOffcanvas', cartOffcanvas)

window.Alpine = Alpine
window.validatePrice = validatePrice
window.validateQuantity = validateQuantity
window.validateDiscount = validateDiscount
window.notify = notify

window.appendAlert = function (message, type) {
    if (window.notify) {
        window.notify(message, type || 'danger');
    }
};

document.addEventListener('click', function (e) {
    var child = e.target.closest('.table-link-child');
    if (child && child.parentElement) {
        var href = child.parentElement.dataset.href;
        if (href) window.document.location = href;
    }
    var row = e.target.closest('.table-link');
    if (row) {
        var href = row.dataset.href;
        if (href) window.document.location = href;
    }
});

document.addEventListener('DOMContentLoaded', function () {
    document.querySelectorAll('[data-bs-toggle="tooltip"]').forEach(function (el) {
        new bootstrap.Tooltip(el);
    });
});

Alpine.start()

// formutils.js - javascript utility for form processing

/**
 * Reusable Tom Select loader for Mako Templates
 */
function setupDynamicSelect(selector, apiUrl) {
    return new TomSelect(selector, {
        valueField: 'id',
        labelField: 'text',
        searchField: 'text',
        
        shouldLoad: function(query) {
            return query.length >= 3;
        },

        load: function(query, callback) {
            // Using concatenation instead of backticks to avoid Mako/JS conflicts
            var url = apiUrl + '?q=' + encodeURIComponent(query);
            
            fetch(url)
                .then(function(response) { return response.json(); })
                .then(function(json) {
                    callback(json); 
                })
                .catch(function() {
                    callback();
                });
        },
        loadThrottle: 300
    });
}

/**
 * @param {string} selector - CSS selector for the input.
 * @param {string} url - API endpoint.
 * @param {string} csrfHeaderName - Header name (e.g., 'X-CSRF-Token' or 'X-CSRFToken').
 */
function initRemoteAutocomplete(selector, url, csrfHeaderName) {
    // Default to 'X-CSRF-Token' if not provided
    var headerName = csrfHeaderName || 'X-CSRF-Token';
    
    // Retrieve token from meta tag
    var meta = document.querySelector('meta[name="csrf-token"]');
    var token = meta ? meta.getAttribute('content') : '';

    return new TomSelect(selector, {
        valueField: 'value',
        labelField: 'text',
        searchField: 'text',
        create: true,
        createOnBlur: true,
        maxItems: 1,
        loadThrottle: 300,
        render: {
            item: function(data, escape) {
                return '<div class="py-0">' + escape(data.text) + '</div>';
            }
        },
        load: function(query, callback) {
            var fetchUrl = url + '?q=' + encodeURIComponent(query);
            
            fetch(fetchUrl, {
                method: 'GET', // or 'POST' depending on your API
                headers: {
                    'Accept': 'application/json',
                    // Pass the CSRF token in the headers
                    [headerName]: token 
                }
            })
            .then(function(response) { return response.json(); })
            .then(function(json) {
                callback(json);
            })
            .catch(function() {
                callback();
            });
        }
    });
}

/**
 * Initialize selection-bar behavior for a form.
 *
 * @param {string} form_id - HTML id of the form containing the checkboxes.
 * @param {string} prefix - Prefix used by selection-bar controls.
 * @param {string} checkbox_name - Name attribute of checkbox inputs.
 */
function initSelectionBar(form_id, prefix, checkbox_name) {
    var form = document.getElementById(form_id);
    if (!form) return;

    var modal = document.getElementById(prefix + '-modal');
    var selector = 'input[name="' + checkbox_name + '"]';
    var getAllBoxes = function() {
        return Array.from(form.querySelectorAll(selector));
    };

    var bindClick = function(id, handler) {
        var el = document.getElementById(id);
        if (el) el.addEventListener('click', handler);
    };

    bindClick(prefix + '-select-all', function() {
        getAllBoxes().forEach(function(cb) { cb.checked = true; });
    });
    bindClick(prefix + '-select-none', function() {
        getAllBoxes().forEach(function(cb) { cb.checked = false; });
    });
    bindClick(prefix + '-select-inverse', function() {
        getAllBoxes().forEach(function(cb) { cb.checked = !cb.checked; });
    });

    var submitHandler = async function(e) {
        e.preventDefault();

        try {
            var formData = new FormData(form);
            if (e.currentTarget && e.currentTarget.name) {
                formData.set(e.currentTarget.name, e.currentTarget.value || '');
            }

            var params = new URLSearchParams();
            formData.forEach(function(value, key) {
                if (!(value instanceof File)) {
                    params.append(key, value);
                }
            });

            var response = await fetch(form.action, {
                method: form.method || 'POST',
                headers: {
                    'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8',
                    'X-Requested-With': 'XMLHttpRequest'
                },
                body: params
            });

            if (response.ok && modal) {
                var html = await response.text();
                modal.innerHTML = html;
                if (window.bootstrap && window.bootstrap.Modal) {
                    window.bootstrap.Modal.getOrCreateInstance(modal).show();
                } else {
                    modal.classList.add('show');
                    modal.style.display = 'block';
                }
                document.dispatchEvent(
                    new CustomEvent('selection-bar:loaded', { detail: { prefix: prefix, html: html } })
                );
            }
        } catch (error) {
            console.error('Selection bar request failed', error);
        }
    };

    form.querySelectorAll('[id^="' + prefix + '-submit-"]').forEach(function(btn) {
        btn.addEventListener('click', submitHandler);
    });
}

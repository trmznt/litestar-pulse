// genutils.js - generic javascript utility

// the following code will convert <time datetime="DATETIME">DATETIME</time>
// to current local time zone
(function() {
    document.querySelectorAll('time[datetime]').forEach(function(el) {
      var date = new Date(el.getAttribute('datetime'));
      if (isNaN(date.getTime())) return;

      // Manually define components to avoid "Invalid option" conflict
      var options = {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: 'numeric',
        minute: '2-digit',
        hour12: false,
        timeZoneName: 'short'
      };

      // Using en-CA for the date part (YYYY-MM-DD)
      var datePart = new Intl.DateTimeFormat('en-CA', {
        year: 'numeric', month: '2-digit', day: '2-digit'
      }).format(date);

      // Using en-US for the time part with timezone
      var timePart = new Intl.DateTimeFormat('en-US', {
        hour: 'numeric', minute: '2-digit', hour12: false, timeZoneName: 'short'
      }).format(date);

      el.textContent = datePart + " " + timePart;
    });
  })();

  
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

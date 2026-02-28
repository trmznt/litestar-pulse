<%inherit file="../base.mako" />

% if html:
    ${html}
% else:
    ${content | n}
% endif

##
<%def name="stylelinks()">
    <link href="https://cdn.jsdelivr.net/npm/tom-select@2.4.3/dist/css/tom-select.css" rel="stylesheet">
</%def>
##
<%def name="jslinks()">
    <script src="https://cdn.jsdelivr.net/npm/tom-select@2.4.3/dist/js/tom-select.complete.min.js"></script>
</%def>
##
<%def name="jscode()">

<%text>
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

</%text>


    ${code or '' | n}

</%def>
##
##
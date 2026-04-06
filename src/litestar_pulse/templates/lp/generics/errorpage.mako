<%inherit file="../plainbase.mako" />

<h1>Error</h1>

%for error in errors:
    <p>${error}</p>
%endfor
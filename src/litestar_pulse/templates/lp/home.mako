<%inherit file="base.mako" />

<h1>Litestar-Pulse</h1>
<p>Welcome to the Litestar-Pulse library home page.</p>

% if request.user:
    <p>You are logged in as ${request.user.login}.</p>
% else:
    <p>You are not logged in. Please <a href="/login">log in</a> to access more functionalities.</p>
% endif

## EOF

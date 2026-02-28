<%inherit file="plainbase.mako" />

<%doc>
This template requires the following named variables:
- title: The title of the login page
- msg: An optional message to display (e.g., error messages)
- login: The pre-filled login value (if any)

</%doc>

% if (user := request.user) is not None:

<section class="login-block py-5">
    <div class="container">
        <div class="row justify-content-center">
            <div class="col-12 col-md-8 text-center">
                <h3 class="heading mb-4">You are already logged in as ${user.login}</h3>
                <a href="/logout" class="btn btn-primary btn-md w-100">Log Out</a>
            </div>
        </div>
    </div>
</section>

% else:
<section class="login-block py-5">
    <div class="container">
        <div class="row justify-content-center">
            <div class="col-12 col-md-8 col-lg-6">
                <form class="form-material" action="#" method="POST">
                    <div class="auth-box card shadow-sm">
                        <div class="card-body p-4">
                            <div class="text-center mb-4">
                                <h3 class="heading mb-3">Log In: ${title}</h3>
                                % if msg:
                                    <div class="alert alert-danger" role="alert">${msg}</div>
                                % endif
                            </div>

                            <div class="mb-3"> <input type="text" class="form-control" name="username" value="${username}" placeholder="Login or Email" id="username"> </div>
                            <div class="mb-3"> <input type="password" class="form-control" name="password" placeholder="Password" value="" id="password"> </div>
                            <div class="d-grid gap-2">
                                <button type="submit" class="btn btn-primary btn-md" name="submit" value="Log In">Log In</button>
                            </div>

<%doc>
    % if 'rhombus.oauth2.google.client_id' in request.registry.settings:
                            <div class="or-container">
                                <div class="line-separator"></div>
                                <div class="or-label">or</div>
                                <div class="line-separator"></div>
                            </div>
                            <div class="row">
                                <div class="col-md-12"> <a class="btn btn-lg btn-google w-100 text-uppercase btn-outline" href="/g_login"><img width="20px" style="margin-bottom:3px; margin-right:5px" alt="Google sign-in" src="${request.static_url('rhombus:static/google-g-logo.svg')}"> Login Using Google</a> </div>
                            </div> <br>
    % endif
</%doc>
                            <p class="text-center text-muted mt-4">Forget password? <a href="" data-abc="true">Click here</a></p>
                        </div>
                    </div>
                </form>
            </div>
        </div>
    </div>
</section>

% endif

##
##
<%def name="stylelinks()">
    <link href="/static/css/login.css" rel="stylesheet" />
</%def>
##

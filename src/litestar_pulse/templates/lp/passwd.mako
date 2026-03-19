<%inherit file="plainbase.mako" />

<%doc>
This template requires the following named variables:
- msg: An optional message to display (e.g., error or success messages)

Expects request.user to be set (user must be logged in).
The user's login is read from request.user.login.
</%doc>

% if (user := request.user) is not None:

<section class="py-4">
    <div class="container">
        <div class="row justify-content-center">
            <div class="col-12 col-md-8 col-lg-6">
                <div class="card shadow-sm">
                    <div class="card-body p-4">
                        <h3 class="text-center mb-4">Change Password</h3>

                        ## Message / error placeholder
                        <div id="msg-box">
                            % if msg:
                            <div class="alert alert-danger alert-dismissible fade show" role="alert">
                                ${msg}
                                <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
                            </div>
                            % endif
                        </div>

                        <form id="passwd-form" method="POST" action="#" novalidate>

                            ## Read-only login field
                            <div class="row mb-3">
                                <label for="login" class="col-sm-4 col-form-label text-end">Login</label>
                                <div class="col-sm-8">
                                    <input type="text" class="form-control-plaintext" id="login"
                                           value="${user.login}" readonly>
                                </div>
                            </div>

                            ## Current password
                            <div class="row mb-3">
                                <label for="cur_password" class="col-sm-4 col-form-label text-end">Current Password</label>
                                <div class="col-sm-8">
                                    <input type="password" class="form-control" id="cur_password"
                                           name="cur_password" required autocomplete="current-password">
                                    <div class="invalid-feedback">Please enter your current password.</div>
                                </div>
                            </div>

                            ## New password
                            <div class="row mb-3">
                                <label for="new_password" class="col-sm-4 col-form-label text-end">New Password</label>
                                <div class="col-sm-8">
                                    <input type="password" class="form-control" id="new_password"
                                           name="new_password" required autocomplete="new-password">
                                    <div class="invalid-feedback" id="new-password-error">Please enter a new password.</div>
                                    ## Complexity checklist
                                    <ul class="list-unstyled small mt-2 mb-0" id="pw-rules">
                                        <li id="rule-length"><i class="bi bi-x-circle text-danger"></i> At least 8 characters</li>
                                        <li id="rule-upper"><i class="bi bi-x-circle text-danger"></i> At least one uppercase letter</li>
                                        <li id="rule-lower"><i class="bi bi-x-circle text-danger"></i> At least one lowercase letter</li>
                                        <li id="rule-digit"><i class="bi bi-x-circle text-danger"></i> At least one digit</li>
                                        <li id="rule-special"><i class="bi bi-x-circle text-danger"></i> At least one special character</li>
                                    </ul>
                                </div>
                            </div>

                            ## Confirm password
                            <div class="row mb-3">
                                <label for="confirm_password" class="col-sm-4 col-form-label text-end">Confirm Password</label>
                                <div class="col-sm-8">
                                    <input type="password" class="form-control" id="confirm_password"
                                           name="confirm_password" required autocomplete="new-password">
                                    <div class="invalid-feedback" id="confirm-password-error">Please confirm your new password.</div>
                                </div>
                            </div>

                            ## Submit
                            <div class="row">
                                <div class="col-sm-8 offset-sm-4 d-grid gap-2">
                                    <button type="submit" class="btn btn-primary" id="btn-submit">Change Password</button>
                                </div>
                            </div>

                        </form>
                    </div>
                </div>
            </div>
        </div>
    </div>
</section>

% endif

##
<%def name="jscode()">
(function () {
    "use strict";

    var newPw = document.getElementById("new_password");
    var confirmPw = document.getElementById("confirm_password");
    var form = document.getElementById("passwd-form");

    // Password complexity rules
    var rules = [
        { id: "rule-length",  test: function (v) { return v.length >= 8; } },
        { id: "rule-upper",   test: function (v) { return /[A-Z]/.test(v); } },
        { id: "rule-lower",   test: function (v) { return /[a-z]/.test(v); } },
        { id: "rule-digit",   test: function (v) { return /\d/.test(v); } },
        { id: "rule-special", test: function (v) { return /[^A-Za-z0-9]/.test(v); } },
    ];

    var PASS_ICON = '<i class="bi bi-check-circle text-success"></i>';
    var FAIL_ICON = '<i class="bi bi-x-circle text-danger"></i>';

    /**
     * Evaluate all complexity rules against the current new-password value
     * and update the checklist icons.  Returns true only when every rule passes.
     */
    function checkComplexity() {
        var val = newPw.value;
        var allPassed = true;

        rules.forEach(function (rule) {
            var el = document.getElementById(rule.id);
            var passed = rule.test(val);
            if (!passed) allPassed = false;
            // Replace only the icon, preserve the rule text
            el.innerHTML = (passed ? PASS_ICON : FAIL_ICON) + " " + el.textContent.trim();
        });

        if (allPassed) {
            newPw.classList.remove("is-invalid");
            newPw.classList.add("is-valid");
        } else if (val.length > 0) {
            newPw.classList.remove("is-valid");
            newPw.classList.add("is-invalid");
            document.getElementById("new-password-error").textContent =
                "Password does not meet complexity requirements.";
        } else {
            newPw.classList.remove("is-valid", "is-invalid");
        }

        // Re-check match whenever the new password changes
        checkMatch();
        return allPassed;
    }

    /**
     * Verify that the confirm-password field matches the new-password field.
     * Returns true when both are non-empty and identical.
     */
    function checkMatch() {
        var val = confirmPw.value;
        if (val.length === 0) {
            confirmPw.classList.remove("is-valid", "is-invalid");
            return false;
        }
        if (val === newPw.value) {
            confirmPw.classList.remove("is-invalid");
            confirmPw.classList.add("is-valid");
            return true;
        }
        confirmPw.classList.remove("is-valid");
        confirmPw.classList.add("is-invalid");
        document.getElementById("confirm-password-error").textContent =
            "Passwords do not match.";
        return false;
    }

    // Live feedback while typing
    newPw.addEventListener("input", checkComplexity);
    confirmPw.addEventListener("input", checkMatch);

    // Form submission guard - block submit if validation fails
    form.addEventListener("submit", function (e) {
        var valid = true;

        // Current password must not be empty
        var curPw = document.getElementById("cur_password");
        if (!curPw.value.trim()) {
            curPw.classList.add("is-invalid");
            valid = false;
        } else {
            curPw.classList.remove("is-invalid");
        }

        if (!checkComplexity()) valid = false;
        if (!checkMatch()) valid = false;

        if (!valid) {
            e.preventDefault();
            e.stopPropagation();
        }
    });
})();
</%def>
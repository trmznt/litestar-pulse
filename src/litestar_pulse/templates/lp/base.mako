## -*- coding: utf-8 -*-
<!DOCTYPE html>
<html lang="en">
  <!-- litestar-pulse lp/base.mako -->
  <head>
  <meta charset="utf-8" />
  <title>${ title or "Litestar-Pulse library" }</title>
  <meta name='viewport' content='width=device-width, initial-scale=1.0' />

  <!-- styles -->
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.8/dist/css/bootstrap.min.css" rel="stylesheet" integrity="sha384-sRIl4kxILFvY47J16cr9ZwB07vP4J8+LH7qKQnuqkuIAvNWLzeN8tE5YBujZqJLB" crossorigin="anonymous">
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.13.1/font/bootstrap-icons.min.css">
    <link href="/static/css/theme.css" rel="stylesheet">
    <link href="/static/css/custom.css" rel="stylesheet">

  ${self.stylelinks()}

  </head>
  <body>

    <!-- Static navbar -->
    <nav class="navbar navbar-expand-md navbar-dark bg-dark mb-4">
      <span class="navbar-brand">${title}</span>
      <button class="navbar-toggler" type="button" data-toggle="collapse" data-target="#navbarCollapse" aria-controls="navbarCollapse" aria-expanded="false" aria-label="Toggle navigation">
        <span class="navbar-toggler-icon"></span>
      </button>
      <div class="collapse navbar-collapse justify-content-stretch" id="navbarCollapse">
        <div class="navbar-nav mr-auto"></div>
        <div class="navbar-nav justify-content-stretch">
        ## ${user_menu(request)}
        </div>
      </div>
    </nav>


    <div class="container-fluid">

      <div class="row"><div class="col-md-12">
      ## ${flash_msg()}
      </div></div>

      <div class="row"><div class="col-md-12">
        ${next.body()}
      </div>

    </div>

  ${self.scriptlinks()}

  </body>

</html>

##
##
<%def name="stylelinks()">
</%def>
##
##
<%def name="scriptlinks()">
<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.8/dist/js/bootstrap.bundle.min.js" integrity="sha384-FKyoEForCGlyvwx9Hj09JcYn3nv7wiPVlz7YYwJrWVcXK/BmnVDxM+D2scQbITxI" crossorigin="anonymous"></script>
    ## <!-- <script src="${request.static_url('rhombus:static/js/jquery.ocupload-min.js')}"></script> -->
    ${self.jslinks()}
    <script type="text/javascript">
        //<![CDATA[
        ${self.jscode()}


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

        //]]>
    </script>
</%def>
##
##
<%def name='flash_msg()'>
% if request.session.peek_flash():

  % for msg_type, msg_text in request.session.pop_flash():
   <div class="alert alert-${msg_type} alert-dismissible fade show" role="alert">
     ${msg_text}
     <button type="button" class="close" data-dismiss="alert" aria-label="Close">
       <span aria-hidden="true">&times;</span>
     </button>
   </div>
  % endfor

% endif
</%def>

##
<%def name='jscode()'>
</%def>

##
<%def name="jslinks()">
</%def>

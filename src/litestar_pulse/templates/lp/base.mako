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

    <link href="/static/css/fixer.css" rel="stylesheet">

  </head>
  <body id="body-layout">

    <!-- Static navbar -->
    <nav class="navbar navbar-expand-md navbar-dark bg-dark mb-4">
      <span class="navbar-brand">${title}</span>
      <button class="navbar-toggler" type="button" data-toggle="collapse" data-target="#navbarCollapse" aria-controls="navbarCollapse" aria-expanded="false" aria-label="Toggle navigation">
        <span class="navbar-toggler-icon"></span>
      </button>
      <div class="collapse navbar-collapse" id="navbarCollapse">
        <div class="navbar-nav ms-auto">
        ${user_menu(request)}
        </div>
      </div>
    </nav>


    <div class="container-fluid">

      <div class="row"><div class="col-md-12">
      ${flash_msg()}
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
<script src="//unpkg.com/alpinejs" defer></script>
<script src="/static/js/genutils.js"><</script>

${self.anyscriptlinks()}

<script type="text/javascript">
//<![CDATA[

${self.jscode()}

//]]>
</script>

</%def>
##
##
<%def name='flash_msg()'>

## Use Litestar's get_flashes() to retrieve message objects
% for msg in get_flashes():
    <div class="alert alert-${msg['category']} alert-dismissible fade show" role="alert">
        ${msg['message']}
        <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
    </div>
% endfor

</%def>

##
<%def name='jscode()'>
</%def>

##
<%def name='pyscode()'>
</%def>

##
<%def name="anyscriptlinks()">
</%def>

## EOF

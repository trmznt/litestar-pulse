<%inherit file="../base.mako" />

<!-- content lp/generics/formpage.mako -->
% if html:
${ html }
% else:
${ content | n }
% endif
<!-- /content lp/generics/formpage.mako -->

##
##
<%def name="stylelinks()">
    <link href="https://cdn.jsdelivr.net/npm/tom-select@2.4.3/dist/css/tom-select.css" rel="stylesheet">
</%def>
##
##
<%def name="anyscriptlinks()">
    <script src="https://cdn.jsdelivr.net/npm/tom-select@2.4.3/dist/js/tom-select.complete.min.js"></script>
    <script src="/static/js/formutils.js"></script>
</%def>
##
##
<%def name="jscode()">

${code or '' | n}
${javascript_code or '' | n}

</%def>
##
##
<%def name="pyscode()">
<script type="mpy">

${pyscript_code or '' | n}

</script>
</%def>
##
## EOF

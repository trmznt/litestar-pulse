<%inherit file="../base.mako" />

<!-- content lp/generics/page.mako -->
% if html:
${ html }
% else:
${ content | n }
% endif
<!-- /content lp/generics/page.mako -->

##
<%def name="stylelinks()">

</%def>
##
##
<%def name="anyscriptlinks()">

${scriptlink_lines or '' | n}

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
##

<%inherit file="../base.mako" />

% if html:
${ html }
% else:
${ content | n }
% endif

##
<%def name="stylelinks()">

</%def>
##
##
<%def name="jscode()">
  ${code or '' | n}
</%def>
##
##

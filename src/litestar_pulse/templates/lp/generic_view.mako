<%inherit file="base.mako" />


% if html:
${ html }
% else:
${ content | n }
% endif

##
##
<%def name="jscode()">
  ${code or '' | n}
</%def>
##
##
## EOF

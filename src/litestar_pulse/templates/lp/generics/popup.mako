<div class="modal-dialog" role="document">
    <div class="modal-content">
        <div class="modal-header">
            <h5 class="modal-title" id="myModalLabel">${title}</h5>
            <button type="button" class="btn-close ms-auto" data-bs-dismiss="modal" aria-label="Close">
                <span aria-hidden="true">&times;</span>
            </button>
        </div>
        <div class="modal-body">

            ${content}

        </div>
        <div class="modal-footer">
            ${footer}
        </div>
    </div>
</div>

% if jscode:
<script type="text/javascript">
    //<![CDATA[
    ${jscode | n}
    //]]>
</script>
% endif

% if pyscode:
<py-script>
    ${pyscode | n}
</py-script>
% endif

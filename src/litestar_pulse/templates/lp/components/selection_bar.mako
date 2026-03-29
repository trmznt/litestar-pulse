
##
##
<%def name="selection_bar(prefix, tag_id, add=None, others='')">
<div id='${prefix + "-modal"}' class="modal fade" role="dialog" tabindex="-1"></div>
<div class='btn-toolbar' x-data="selectionBar('${prefix}', 'input[name=${tag_id}]')">
  <div class='btn-group'>
    <button type="button" class="btn btn-mini" @click="selectAll()">Select all</button>
    <button type="button" class="btn btn-mini" @click="selectNone()">Unselect all</button>
    <button type="button" class="btn btn-mini" @click="selectInverse()">Inverse</button>
  </div>
  <div class='btn-group'>
    <button class="btn btn-mini btn-danger" @click="submitDelete($event)" type="button" name="_method" value="delete"><i class='icon-trash icon-white'></i> Delete</button>
  </div>
% if add:
  <div class='btn-group'>
    <a href="${add[1]}">
      <button class='btn btn-mini btn-success' type='button'>
        <i class='icon-plus-sign icon-white'></i> ${add[0]}
      </button>
    </a>
  </div>
% endif
% if others:
  <div class='btn-group'>
  ${others | n}
  </div>
% endif
</div>
</%def>
##
##
<%def name="selection_bar_js(form_id, prefix, tag_id)">
  const sb = initSelectionBar('${form_id}', '${prefix}', '${tag_id}');
  
  document.addEventListener('DOMContentLoaded', function() {
    // Bind select buttons
    const selectAllBtn = document.getElementById('${prefix}-select-all');
    const selectNoneBtn = document.getElementById('${prefix}-select-none');
    const selectInverseBtn = document.getElementById('${prefix}-select-inverse');
    
    if (selectAllBtn) selectAllBtn.addEventListener('click', () => sb.selectAll());
    if (selectNoneBtn) selectNoneBtn.addEventListener('click', () => sb.selectNone());
    if (selectInverseBtn) selectInverseBtn.addEventListener('click', () => sb.selectInverse());
    
    // Bind action buttons
    document.querySelectorAll('[id^="${prefix}-submit-"]').forEach(btn => {
      btn.addEventListener('click', (e) => sb.submitAction(e));
    });
  });
</%def>

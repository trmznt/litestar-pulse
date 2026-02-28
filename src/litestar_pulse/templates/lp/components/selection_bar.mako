
##
##
<%def name="selection_bar(prefix, add=None, others='')">
<div id='${prefix + "-modal"}' class="modal fade" role="dialog" tabindex="-1"></div>
<div class='btn-toolbar'>
  <div class='btn-group'>
    <button type="button" class="btn btn-mini" id='${prefix + "-select-all"}'>Select all</button>
    <button type="button" class="btn btn-mini" id='${prefix + "-select-none"}'>Unselect all</button>
    <button type="button" class="btn btn-mini" id='${prefix + "-select-inverse"}'>Inverse</button>
  </div>
  <div class='btn-group'>
    <button class="btn btn-mini btn-danger" id='${prefix + "-submit-delete"}' type="button" name="_method" value="delete"><i class='icon-trash icon-white'></i> Delete</button>
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
<%def name="selection_bar_js(prefix, tag_id)">
  $('${"#%s-select-all" % prefix}').click( function() {
        $('${"input[name=%s]" % tag_id}').each( function() {
            this.checked = true;
        });
    });

  $('${"#%s-select-none" % prefix}').click( function() {
        $('${"input[name=%s]" % tag_id}').attr("checked", false);
    });

  $('${"#%s-select-inverse" % prefix}').click( function() {
        $('${"input[name=%s]" % tag_id}').each( function() {
            if (this.checked == true) {
                this.checked = false;
            } else {
                this.checked = true;
            }
        });
    });

  $('${"#%s-submit-delete" % prefix}').click( function(e) {
        var form = $(this.form);
        var data = form.serializeArray();
        data.push({ name: $(this).attr('name'), value: $(this).val() });
        $.ajax({
            type: form.attr('method'),
            url: form.attr('action'),
            data: data,
            success: function(data, status) {
                $('${"#%s-modal" % prefix}').html(data);
                $('${"#%s-modal" % prefix}').modal('show');
            }
        });
    });

</%def>

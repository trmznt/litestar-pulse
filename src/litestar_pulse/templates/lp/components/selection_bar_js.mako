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
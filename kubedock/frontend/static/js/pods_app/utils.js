define({
    modalDialog: function(options){
        var modal = $('.modal'),
            modalDialog = modal.find('.modal-dialog');
        if ($('.modal-backdrop').is(':visible')) {
            // previous modal dialog is still visible. Delay until it's fully closed
            return modal.one('hidden.bs.modal', _.bind(this.modalDialog, this, options));
        }
        modalDialog.css('margin-top', ( $(window).height() / 2 - 140 ));
        if(options.title) modal.find('.modal-title').html(options.title);
        if(options.body) modal.find('.modal-body').html(options.body);
        if(options.large) modal.addClass('bs-example-modal-lg');
        if(options.small) modal.addClass('bs-example-modal-sm');
        if(options.show) modal.modal('show');
        if(options.footer){
            modal.find('.modal-footer').empty();
            var buttonText = options.type === 'delete' ? 'Delete' : 'Ok';
            if(options.footer.buttonOk){
                modal.find('.modal-footer').append(
                    $('<button type="button" class="btn blue" ' +
                          'data-dismiss="modal">').unbind('click')
                        .bind('click', options.footer.buttonOk)
                        .text(buttonText)
                );
            }
            if(options.footer.buttonCancel === true){
                modal.find('.modal-footer').prepend(
                    $('<button type="button" class="btn"' +
                          'data-dismiss="modal">Cancel</button>')
                );
            }
        }
        return modal;
    },

    modalDialogDelete: function(options){
        options.type = 'delete';
        return this.modalDialog(options);
    },

    notifyWindow: function(b, type){
        var msg = typeof b == "string" ? b :
                  !(b.responseJSON && b.responseJSON.data) ? b.responseText :
                  typeof b.responseJSON.data == 'string' ? b.responseJSON.data :
                  JSON.stringify(b.responseJSON.data);
        if (b && b.status == 401){
            window.location = '/logout'
        } else {
            $.notify(msg,{
                autoHideDelay: 5000,
                clickToHide: true,
                globalPosition: 'bottom left',
                className: type || 'error',
            });
        }
    },

    preloader: {
        show: function(){ $('#page-preloader').show(); },
        hide: function(){ $('#page-preloader').hide(); }
    },

    hasScroll: function() {
        var hContent = $('body').height(),
            hWindow = $(window).height();

        return  hContent > hWindow ? true : false;
    }
});

define({
    modalDialog: function(options){
        var modal = $('.modal');
        if(options.title) modal.find('.modal-title').html(options.title);
        if(options.body) modal.find('.modal-body').html(options.body);
        if(options.large) modal.addClass('bs-example-modal-lg');
        if(options.small) modal.addClass('bs-example-modal-sm');
        if(options.show) modal.modal('show');
        return modal;
    },
    
    modelError: function(b, t){
        this.modalDialog({
            title: t ? t : 'Error',
            body: typeof b == "string" ? b : b.responseJSON ? JSON.stringify(b.responseJSON): b.responseText,
            show: true
        });
    }
});
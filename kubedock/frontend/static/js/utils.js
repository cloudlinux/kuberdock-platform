define(function () {

    // jQuery ajax setup
    var that = this;
    Backbone.ajax = function() {
        // Invoke $.ajaxSetup in the context of Backbone.$
        Backbone.$.ajaxSetup.call(Backbone.$, {
            statusCode: {
                400: function(xhr){
                    if(xhr.responseJSON.status) alert(xhr.responseJSON.status);
                },
                401: function (xhr) {
                    // Redirect to the login page.
//                    Backbone.history.navigate("login", true);
                },
                403: function (xhr) {
                    // 403 -- Access denied
//                    Backbone.history.navigate("login", true);
                },
                404: function(xhr){
                    $('body').html(
                        '404 Page not found'
                    );
                }
            }
        });
        return Backbone.$.ajax.apply(Backbone.$, arguments);
    };


    // here you can define any useful functions or objects to use their in the project

    this.unwrapper = function (response) {
        if (response.hasOwnProperty('data'))
            return response['data'];
        else if(response.hasOwnProperty('status') && typeof response.status === 'string'){
            alert(response.status);
        }
        return response;
    };

    this.BaseModel = Backbone.Model.extend({
        parse: this.unwrapper
    });

    this.modalDialog = function(options){
        var modal = $('.modal');
        if(options.title) modal.find('.modal-title').html(options.title);
        if(options.body) modal.find('.modal-body').html(options.body);
        if(options.large) modal.addClass('bs-example-modal-lg');
        if(options.small) modal.addClass('bs-example-modal-sm');
        if(options.show) modal.modal('show');
        if(options.footer){
            modal.find('.modal-footer').empty();
            if(options.footer.buttonOk){
                modal.find('.modal-footer').prepend(
                    $('<button type="button" class="btn btn-success" ' +
                          'data-dismiss="modal">').unbind('click')
                        .bind('click', options.footer.buttonOk)
                        .text('OK')
                )
            }
            if(options.footer.buttonCancel){
                if(options.footer.buttonCancel === true){
                    modal.find('.modal-footer').append(
                        $('<button type="button" class="btn btn-default" ' +
                              'data-dismiss="modal">Cancel</button>')
                    )
                }
            }
        }
        console.log(modal)
        return modal;
    };


    return this;
});
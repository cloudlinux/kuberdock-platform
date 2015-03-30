define(function () {

    // jQuery ajax setup
    var that = this;
    var _ajaxStatusCodes = {
        statusCode: {
            400: function(xhr){
                var err = xhr.statusText;
                if(xhr.responseJSON && xhr.responseJSON.status)
                    err = xhr.responseJSON.status;
                $.notify(err, {
                    autoHideDelay: 5000,
                    globalPosition: 'top center',
                    className: 'danger'
                });
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
            },
            500: function(xhr){
                $.notify(xhr.statusText, {
                    autoHideDelay: 5000,
                    globalPosition: 'top center',
                    className: 'danger'
                });
            }
        }
    };

    $.ajaxSetup.call($, _ajaxStatusCodes);

    Backbone.ajax = function() {
        // Invoke $.ajaxSetup in the context of Backbone.$
        Backbone.$.ajaxSetup.call(Backbone.$, _ajaxStatusCodes);
        return Backbone.$.ajax.apply(Backbone.$, arguments);
    };


    // here you can define any useful functions or objects to use their in the project

    this.unwrapper = function (response) {
        var data = response.hasOwnProperty('data') ? response['data'] : response
        if (response.hasOwnProperty('status')) {
            if(response.status == 'error' || response.status == 'warning') {
                var err = data;
                if(typeof data !== 'string') err = JSON.stringify(data);
                $.notify(err, {
                    autoHideDelay: 5000,
                    globalPosition: 'top center',
                    className: response.status == 'error' ? 'danger' : 'warning'
                });
            }
        }
        return data;
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

    this.dateYYYYMMDD = function(date, sep){
        if(!date) date = new Date();
        if(!sep) sep = '-';
        var y = date.getFullYear(),
            m = date.getMonth() + 1,
            d = date.getDate(),
            D = [y, m > 9 ? m : '0' + m, d > 9 ? d : '0' + d];
        return D.join(sep);
    };

    return this;
});
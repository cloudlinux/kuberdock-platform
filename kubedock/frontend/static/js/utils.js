define(function () {

    // jQuery ajax setup
    var that = this;
    var _ajaxStatusCodes = {
        statusCode: {
            400: function(xhr){
                var err = xhr.statusText;
                if(xhr.responseJSON && xhr.responseJSON.data)
                    err = xhr.responseJSON.data;
                if(typeof err === "object")
                    err = JSON.stringify(err);
                $.notify(err, {
                    autoHideDelay: 5000,
                    clickToHide: true,
                    globalPosition: 'bottom left',
                    className: 'error'
                });
            },
            401: function (xhr) {
                var err = xhr.statusText;
                if(xhr.responseJSON && xhr.responseJSON.data)
                    err = xhr.responseJSON.data;
                if(typeof err === "object")
                    err = JSON.stringify(err);
                $.notify(err, {
                    autoHideDelay: 5000,
                    globalPosition: 'bottom left',
                    className: 'error'
                });

                // Redirect to the login page.
                    window.location.href = "/login";
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
                var err = xhr.statusText;
                if(xhr.responseJSON && xhr.responseJSON.data)
                    err = xhr.responseJSON.data;
                if(typeof err === "object")
                    err = JSON.stringify(err);
                $.notify(err, {
                    autoHideDelay: 5000,
                    globalPosition: 'bottom left',
                    className: 'error'
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
        var data = response.hasOwnProperty('data') ? response['data'] : response;
        if (response.hasOwnProperty('status')) {
            if(response.status == 'error' || response.status == 'warning') {
                var err = data;
                if(typeof data !== 'string') err = JSON.stringify(data);
                $.notify(err, {
                    autoHideDelay: 10000,
                    globalPosition: 'bottom left',
                    className: response.status == 'error' ? 'danger' : 'warning'
                });
            }
        }
        return data;
    };

    this.toHHMMSS = function (seconds) {
        var sec_num = parseInt(seconds, 10); // don't forget the second param
        var hours = Math.floor(sec_num / 3600);
        var minutes = Math.floor((sec_num - (hours * 3600)) / 60);
        var secs = sec_num - (hours * 3600) - (minutes * 60);
        if (hours   < 10)
            hours = "0" + hours;
        if (minutes < 10)
            minutes = "0" + minutes;
        if (secs < 10)
            secs = "0" + secs;
        return hours + ':' + minutes + ':' + secs;
    };

    this.localizeDatetime = function(dt, tz){
        try {
            return moment(dt).tz(tz).format('YYYY-MM-DD hh:mm:ss');
        } catch (e){
            console.log(e);
        }
        return dt;
    };

    this.BaseModel = Backbone.Model.extend({
        parse: this.unwrapper
    });

    this.BaseCollection = Backbone.Collection.extend({
        parse: this.unwrapper
    });

    this.modalDialog = function(options){
        var modal = $('.modal'),
        modalDialog = modal.find('.modal-dialog');
        modalDialog.css('margin-top', ( $(window).height() / 2 - 140 ));
        if(options.title) modal.find('.modal-title').html(options.title);
        if(options.body) modal.find('.modal-body').html(options.body);
        if(options.large) modal.addClass('bs-example-modal-lg');
        if(options.small) modal.addClass('bs-example-modal-sm');
        if(options.show) modal.modal('show');
        if(options.footer){
            modal.find('.modal-footer').empty();
            if(options.footer.buttonOk){
                modal.find('.modal-footer').append(
                    $('<button type="button" class="btn blue" ' +
                          'data-dismiss="modal">').unbind('click')
                        .bind('click', options.footer.buttonOk)
                        .text('Ok')
                )
            }
            if(options.footer.buttonCancel){
                if(options.footer.buttonCancel === true){
                    modal.find('.modal-footer').prepend(
                        $('<button type="button" class="btn"' +
                              'data-dismiss="modal">Cancel</button>')
                    )
                }
            }
        }
        return modal;
    };

    this.modalDialogDelete = function(options){
        var modal = $('.modal'),
        modalDialog = modal.find('.modal-dialog');
        modalDialog.css('margin-top', ( $(window).height() / 2 - 140 ));
        if(options.title) modal.find('.modal-title').html(options.title);
        if(options.body) modal.find('.modal-body').html(options.body);
        if(options.large) modal.addClass('bs-example-modal-lg');
        if(options.small) modal.addClass('bs-example-modal-sm');
        if(options.show) modal.modal('show');
        if(options.footer){
            modal.find('.modal-footer').empty();
            if(options.footer.buttonOk){
                modal.find('.modal-footer').append(
                    $('<button type="button" class="btn blue" ' +
                          'data-dismiss="modal">').unbind('click')
                        .bind('click', options.footer.buttonOk)
                        .text('Delete')
                )
            }
            if(options.footer.buttonCancel){
                if(options.footer.buttonCancel === true){
                    modal.find('.modal-footer').prepend(
                        $('<button type="button" class="btn"' +
                              'data-dismiss="modal">Cancel</button>')
                    )
                }
            }
        }
        return modal;
    };

    this.modelError = function(b, t){
        this.modalDialog({
            title: t ? t : 'Error',
            body: typeof b == "string" ? b : b.responseJSON ? JSON.stringify(b.responseJSON): b.responseText,
            show: true,
            buttonCancel: false
        });
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
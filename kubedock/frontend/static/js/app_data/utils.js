define(['moment-timezone', 'numeral', 'notify'], function(moment, numeral){
    'use strict';
    var utils = {};

    utils.modalDialog = function(options){
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
            var buttonText;
            if (options.type === 'delete'){
                buttonText = 'Delete';
            } else if (options.type === 'saveAnyway'){
                buttonText = 'save anyway';
            } else if ( options.type === 'deleteAnyway'){
                buttonText = 'Delete Anyway';
            } else {
                buttonText = 'Ok';
            }
            if(options.footer.buttonOk){
                var btn = $('<button type="button" class="btn blue" ' +
                            'data-dismiss="modal">').unbind('click')
                        .bind('click', options.footer.buttonOk)
                        .addClass(options.footer.buttonOkClass || '')
                        .text(options.footer.buttonOkText || buttonText);
                modal.find('.modal-footer').append(btn);
            }
            if(options.footer.buttonCancel){
                var btn = $('<button type="button" class="btn"' +
                                'data-dismiss="modal">Cancel</button>')
                        .addClass(options.footer.buttonCancelClass || '')
                        .text(options.footer.buttonCancelText || 'Cancel');
                if (_.isFunction(options.footer.buttonCancel))
                    btn.bind('click', options.footer.buttonCancel);
                modal.find('.modal-footer').prepend(btn);
            }
        }
        return modal;
    };

    utils.modalDialogDelete = function(options){
        options.type = 'delete';
        return this.modalDialog(options);
    };

    utils.toHHMMSS = function (seconds) {
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

    utils.dateYYYYMMDD = function(date, sep){
        if(!date) date = new Date();
        if(!sep) sep = '-';
        var y = date.getFullYear(),
            m = date.getMonth() + 1,
            d = date.getDate(),
            D = [y, m > 9 ? m : '0' + m, d > 9 ? d : '0' + d];
        return D.join(sep);
    };

    /**
     * Notify. Can be safely used as $.ajax handler.
     * @param data - Message as a string, or jsXHR object.
     * @param type - Optional message type in case if data is a string, or
        if you want to change default behaviour for jsXHR object.
     */
    utils.notifyWindow = function(data, type){
        var msg;
        if (typeof data == "string") {
            msg = data;
        } else if (!data.responseJSON || !data.responseJSON.data) {
            msg = data.responseText;
            if (data.status >= 500 && data.getResponseHeader &&  // nginx error page
                    data.getResponseHeader('content-type') == 'text/html'){
                var error;
                if (data.status == 504) error = 'Timeout error';
                else if (data.status == 502) error = 'Server is unavailable';
                else if (data.status == 500) error = 'Internal server error';
                else error = data.statusText;
                msg = 'It seems like something goes wrong (' + error + '). '
                    + 'Reload page, try again later, or contact support if '
                    + 'problem appears again.';
            }
        } else {
            msg = typeof data.responseJSON.data == 'string' ? data.responseJSON.data :
                JSON.stringify(data.responseJSON.data);
            if (!type)
                type = data.responseJSON.status == 'ok' ? 'success' : 'error';
        }
        type = type || 'error';

        if (data && data.status == 401){
            window.location = '/login';
        } else if (type === 'error') {
            // do not hide error messages automatically
            // also, group identical messages
            var notifyElement = utils.notifyList[msg];
            if (!notifyElement){  // new message
                $.notify({message: msg, count: 1}, {autoHide: false,
                                                    clickToHide: false,
                                                    className: type});
                // $.notify lib doesn't return the element, but it's always
                // the first one (prepend).
                utils.notifyList[msg] = $('.notifyjs-bootstrap-error')[0];
                utils.notifyList[msg].count = 1;
                utils.notifyList[msg].msg = msg;
            } else {  // old message, again (show and increase counter)
                $(notifyElement).find('.notify-count').text(++notifyElement.count);
                $(notifyElement).addClass('notify-multi');
            }
        } else {
            $.notify({message: msg}, {className: type});
        }
    };
    utils.notifyList = {};  // Notify messages counter
    $.notify.defaults({
        autoHide: true,
        autoHideDelay: 5000,
        clickToHide: true,
        globalPosition: 'bottom left',
    });
    $.notify.addStyle('bootstrap', {  // notify template
        html: "<div>" +
                  "<span class='notify-msg' data-notify-text='message'/>" +
                  "<span class='notify-count' data-notify-text='count'/>" +
                  "<span class='notify-close'/>" +
              "</div>"
    });
    // close errors only if there is no selected text (let user copy error message)
    $(document).on('click', '.notifyjs-bootstrap-error', function(event) {
        event.stopPropagation();
        if (!document.getSelection().toString().length){
            utils.notifyList[this.msg] = undefined;
            $(this).trigger('notify-hide');
        }
    });

    utils.preloader = {
        show: function(){ $('#page-preloader').show(); },
        hide: function(){ $('#page-preloader').hide(); }
    };

    utils.hasScroll = function() {
        var hContent = $('body').height(),
            hWindow = $(window).height();
        return  hContent > hWindow ? true : false;
    };

    utils.scrollTo = function(a){
        var el = a.offset().top;
        $('html, body').animate({
            scrollTop: el-50
        }, 500);
    };

    /* Returns string representing date&time with timezone converted to
     * the given `tz`.
     * You can pass params as an object: localizeDatetime({dt: ,..})
     * or just one by one: localizeDatetime(dt, tz,...)
     *
     * @param dt - datetime, current time by default
     * @param tz - timezone in form 'Europe/London (+0000)' or 'Europe/London'
     *     UTC by default
     * @param formatString - optional, 'YYYY-MM-DD HH:mm:ss' by default
     * @returns {String} formatted localized datetime
     */
    utils.localizeDatetime = function(options) {
        if (arguments.length != 1 || !options ||
                (!options.dt && !options.tz && !options.formatString)){
            // called as localizeDatetime(dt, tz, formatString)
            options = _.object(['dt', 'tz', 'formatString'], arguments);
        }

        var dt = options.dt || new Date(),
            tz = typeof options.tz == 'string' ? options.tz.split(' (', 1)[0] : 'UTC',
            formatString = options.formatString || 'YYYY-MM-DD HH:mm:ss';
        try {
            return moment(dt).tz(tz).format(formatString);
        } catch (e) {
            console.log(e);  // eslint-disable-line no-console
        }
        return moment(dt).format(formatString);
    };

    utils.getBillingUrl = function(billingcollection){

        var billingEndpoints = {
            WHMCS: {
                billing: '/kdorder.php?a=orderPod'
            }
        };

        var billingType = billingcollection.findWhere({name: 'billing_type'}).get('value');
        if (billingType === 'No billing') return null;  // no billing

        if (!_.has(billingEndpoints, billingType)) { // unknown billing
            utils.notifyWindow('Unknown billing type');
            return;
        }
        var billingUrl = billingcollection.findWhere({name: 'billing_url'}).get('value');
        if (billingUrl === undefined) { // no configured URL
            utils.notifyWindow('Billing URL not configured!');
            return;
        }
        return billingUrl.replace(/\/$/, '') + billingEndpoints[billingType].billing;
    };

    return utils;
});

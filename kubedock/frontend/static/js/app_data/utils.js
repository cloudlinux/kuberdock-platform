import moment from 'moment-timezone';
import numeral from 'numeral';
import 'notifyjs-browser';

export const KEY_CODES = {
    enter: 13,
};

export const modalDialog = function(options){
    var modal = $('.modal'),
        modalDialog = modal.find('.modal-dialog');
    if ($('.modal-backdrop').is(':visible')) {
        // previous modal dialog is still visible. Delay until it's fully closed
        return modal.one('hidden.bs.modal', _.bind(this.modalDialog, this, options));
    }
    modalDialog.css('margin-top', ( $(window).height() / 2 - 140 ));
    if (options.title) modal.find('.modal-title').html(options.title);
    if (options.body) modal.find('.modal-body').html(options.body);
    if (options.show) modal.modal('show');
    if (options.footer){
        modal.find('.modal-footer').empty();
        var buttonText;
        if (options.type === 'delete'){
            buttonText = 'Delete';
        } else if (options.type === 'saveAnyway'){
            buttonText = 'Save Anyway';
        } else if ( options.type === 'deleteAnyway'){
            buttonText = 'Delete Anyway';
        } else {
            buttonText = 'Ok';
        }
        var btn;
        if (options.footer.buttonOk){
            btn = $('<button type="button" class="btn blue" ' +
                        'data-dismiss="modal">').unbind('click')
                    .bind('click', options.footer.buttonOk)
                    .addClass(options.footer.buttonOkClass || '')
                    .text(options.footer.buttonOkText || buttonText);
            modal.find('.modal-footer').append(btn);
        }
        if (options.footer.buttonCancel){
            btn = $('<button type="button" class="btn"' +
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

export const modalDialogDelete = function(options){
    options.type = 'delete';
    return this.modalDialog(options);
};

export const toHHMMSS = function(seconds){
    return numeral(seconds).format('00:00:00');
};

export const dateYYYYMMDD = function(date, sep){
    return moment(date).format(['YYYY', 'MM', 'DD'].join(sep || '-'));
};


let notifyList = {};  // Notify messages counter

/**
 * Notify. Can be safely used as $.ajax handler.
 *
 * @param {jqXHR|string} data - Message as a string, or jqXHR object.
 * @param {string} type - Optional message type in case if data is a string,
 * or if you want to change default behaviour for jqXHR object.
 */
export const notifyWindow = function(data, type){
    let msg,
        errorMessage = data.responseJSON && (data.responseJSON.data ||
                                             data.responseJSON.message);
    if (typeof data == "string") {
        msg = data;
    } else if (data.statusText === 'abort' || type === 'abort') {
        return;
    } else if (!errorMessage) {
        msg = data.responseText;
        if (data.status >= 500 && data.getResponseHeader &&  // nginx error page
                data.getResponseHeader('content-type') === 'text/html'){
            let error;
            if (data.status === 504) error = 'Timeout error';
            else if (data.status === 502) error = 'Server is unavailable';
            else if (data.status === 500) error = 'Internal server error';
            else error = data.statusText;
            msg = 'It seems like something goes wrong (' + error + '). ' +
                  'Reload page, try again later, or contact support if ' +
                  'problem appears again.';
        }
    } else {
        msg = typeof errorMessage == 'string' ? errorMessage : JSON.stringify(errorMessage);
        if (!type)
            type = data.responseJSON.status === 'ok' ? 'success' : 'error';
    }
    type = type || 'error';

    if (type === 'error') {
        // do not hide error messages automatically
        // also, group identical messages
        let notifyElement = notifyList[msg];
        if (!notifyElement){  // new message
            $.notify({message: msg, count: 1}, {autoHide: false,
                                                clickToHide: false,
                                                className: type});
            // $.notify lib doesn't return the element, but it's always
            // the first one (prepend).
            notifyList[msg] = $('.notifyjs-bootstrap-error')[0];
            notifyList[msg].count = 1;
            notifyList[msg].msg = msg;
        } else {  // old message, again (show and increase counter)
            $(notifyElement).find('.notify-count').text(++notifyElement.count);
            $(notifyElement).addClass('notify-multi');
        }
    } else {
        $.notify({message: msg}, {className: type});
    }
};

$.notify.defaults({
    autoHide: true,
    autoHideDelay: 5000,
    clickToHide: true,
    globalPosition: 'bottom left',
});
$.notify.addStyle('bootstrap', {  // notify template
    html: "<div>" +
              "<span class='notify-icon'/>" +
              "<span class='notify-msg' data-notify-text='message'/>" +
              "<span class='notify-count' data-notify-text='count'/>" +
              "<span class='notify-close'/>" +
          "</div>"
});
$.notify.addStyle("metro", {
    html: "<div>\n<div class='text-wrapper'>\n<span data-notify-text></span>\n</div>\n</div>",
});

export const notifyWindowClose = function(){
    $('.notifyjs-bootstrap-error').trigger('notify-hide');
    notifyList = {};
};

// close errors only if there is no selected text (let user copy error message)
$(document).on('click', '.notifyjs-bootstrap-error', function(event) {
    event.stopPropagation();
    if (!document.getSelection().toString().length){
        notifyList[this.msg] = undefined;
        $(this).trigger('notify-hide');
    }
});

export const preloader = {
    show: function(){ $('#page-preloader').addClass('show'); },
    hide: function(){ $('#page-preloader').removeClass('show'); }
};

export const hasScroll = function() {
    var hContent = $('body').height(),
        hWindow = $(window).height();
    return hContent > hWindow;
};

export const scrollTo = function(a){
    var el = a.offset().top;
    $('html, body').animate({
        scrollTop: el - 50
    }, 500);
};

/* inline eroror hint */
export const notifyInline = function (message, el){
    var item = $(el);
    item.notify(message, {
        arrow : false,
        style : 'metro',
        autoHide: false,
        clickToHide: true,
        showDuration: 100,
        hideDuration: 100,
        showAnimation: "fadeIn",
        hideAnimation: "fadeOut",
        elementPosition: 'bottom left',
    });
    var messageHeight = $(el).parent().find('.text-wrapper').height();
    item.css('margin-bottom', messageHeight + 10);
    item.addClass('error');
};
// Just a shortcut to remove error from input (or group of inputs)
export const removeError = function(el){
    if (el.hasClass('error'))
        el.parents('td, .form-group').find('.notifyjs-metro-error').trigger('notify-hide');
};

$(document).on('notify-hide', '.notifyjs-metro-error', function(event) {
    $(this).parents('td, .form-group').find('input')
        .css('margin', '').removeClass('error');
});
$(document).on('click', '.notifyjs-metro-error', function(event) {
    $(this).trigger('notify-hide')
        .parents('.notifyjs-wrapper').next('input').focus();
});

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
export const localizeDatetime = function(options) {
    if (arguments.length !== 1 || !options ||
            (!options.dt && !options.tz && !options.formatString)){
        // called as localizeDatetime(dt, tz, formatString)
        options = _.object(['dt', 'tz', 'formatString'], arguments);
    }

    var dt = options.dt || new Date(),
        tz = typeof options.tz == 'string' ? options.tz.split(' (', 1)[0] : 'UTC',
        formatString = options.formatString || 'YYYY-MM-DD HH:mm:ss (Z)';
    try {
        return moment(dt).tz(tz).format(formatString);
    } catch (e) {
        console.log(e);  // eslint-disable-line no-console
    }
    return moment(dt).format(formatString);
};

export const removeURLParameter = function (url, parameter) {
    var urlParts = url.split('?');
    if (urlParts.length < 2) { return url; }
    var prefix = encodeURIComponent(parameter) + '=',
        rightParts = urlParts[1].split('#'),
        pars = rightParts[0].split(/[&;]/g),
        anchor = rightParts[1];
    for (var i = pars.length; i-- > 0;) {
        if (pars[i].lastIndexOf(prefix, 0) !== -1) {
            pars.splice(i, 1);
        }
    }
    var result = urlParts[0] + (pars.length > 0 ? '?' + pars.join('&') : "");
    if (anchor){
        result += '#' + anchor;
    }
    return result;
};

export const deepClone = function(obj) {
    /* eslint-disable no-nested-ternary */
    return (!obj || (typeof obj !== 'object')) ? obj
        : _.isString(obj) ? String.prototype.slice.call(obj)
        : _.isDate(obj) ? new Date(obj.valueOf())
        : _.isFunction(obj.clone) ? obj.clone()
        : _.isArray(obj) ? _.map(obj, function(t){ return deepClone(t); })
        : _.mapObject(obj, function(val) { return deepClone(val); });
    /* eslint-enable no-nested-ternary */
};

export const copyLink = function(text, successMessage, messageState){
    var link = text,
        $txa = $('<textarea />', {val: link, css: {position: 'fixed'}})
            .appendTo("body").select();
    if (document.execCommand('copy')){ // CH, FF, Edge, IE
        notifyWindow(successMessage, messageState ? messageState : 'success');
    } else {
        prompt(  // eslint-disable-line no-alert
            'Copy to clipboard:\nSelect, Cmd+C, Enter', link);
    }
    $txa.remove();
};

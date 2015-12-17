define(['moment-timezone', 'notify'], function(moment){

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

    //utils.localizeDatetime = function(dt, tz){
    //    try {
    //        return moment(dt).tz(tz).format('YYYY-MM-DD hh:mm:ss');
    //    } catch (e){
    //        console.log(e);
    //    }
    //    return dt;
    //};

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
        } else {
            msg = typeof data.responseJSON.data == 'string' ? data.responseJSON.data :
                JSON.stringify(data.responseJSON.data);
            if (!type)
                type = data.responseJSON.status == 'ok' ? 'success' : 'error';
        }
        type = type || 'error';

        if (data && data.status == 401){
            window.location = '/login';
        } else {
            $.notify(msg,{
                autoHideDelay: 5000,
                clickToHide: true,
                globalPosition: 'bottom left',
                className: type,
            });
        }
    };

    utils.preloader = {
        show: function(){ $('#page-preloader').show(); },
        hide: function(){ $('#page-preloader').hide(); }
    };

    utils.hasScroll = function() {
        var hContent = $('body').height(),
            hWindow = $(window).height();
        return  hContent > hWindow ? true : false;
    };

    utils.scrollTo = function(a, b){
        el = a.offset().top;
        $('html, body').animate({
            scrollTop: el-50
        }, 500);
    };

    utils.localizeDatetimeForUser = function(dt, user, formatString) {
        /* Returns string representing date&time with timezone converted to
         * the given user. 'user' must contain 'timezone' field.
         * If there is defined global userProfile variable, then it will
         * be used for timezone extracting (in case when 'user' is undefined).
         * Accepts timezones in form 'Europe/London (+0000)', 'Europe/London'
         * When no user is specified and userProfile is undefined, then uses
         * 'UTC' timezone to convert date&time.
         */
        var tz;
        if (user === undefined && typeof userProfile != 'undefined') {
            user = userProfile;
        }
        if (user === undefined || typeof user.timezone !== 'string') {
            tz = 'UTC';
        } else {
            tz = user.timezone.split(' (', 1)[0];
        }
        return this.localizeDatetime(dt, tz, formatString);
    };

    utils.localizeDatetime = function(dt, tz, formatString){
        formatString = formatString || 'YYYY-MM-DD HH:mm:ss';
        try {
            return moment(dt).tz(tz).format(formatString);
        } catch (e) {
            console.log(e);
        }
        return moment(dt).format(formatString);
    };

    // TODO: crate models Package and Kube; use backbone-associations for relations
    utils.getUserPackage = function(full) {
        var pkg = _.findWhere(backendData.packages, {id: backendData.userPackage});
        if (full) {
            var kubes = _.indexBy(backendData.kubeTypes, 'id');
            pkg.kubes = _.chain(backendData.packageKubes).where({package_id: pkg.id})
                .each(function(packageKube){
                    _.extend(packageKube, kubes[packageKube.kube_id]);
                }).value();
        }
        return pkg;
    };

    // TODO: it should be a method of Package model
    utils.getFormattedPrice = function(pkg, price, format) {
        format = format !== undefined ? format : '0.00';

        return pkg.prefix + numeral(price).format(format) + pkg.suffix;
    };

    return utils;
});

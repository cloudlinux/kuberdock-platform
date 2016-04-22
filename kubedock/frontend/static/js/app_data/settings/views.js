define(['app_data/app', 'marionette',
        'tpl!app_data/settings/templates/settings_layout.tpl',
        'tpl!app_data/settings/templates/user_edit.tpl',
        'tpl!app_data/settings/templates/general_settings.tpl',
        'tpl!app_data/settings/templates/general_settings_item.tpl',
        'tpl!app_data/settings/templates/license.tpl',
        'app_data/utils', 'bootstrap', 'bootstrap-editable', 'selectpicker', 'tooltip'],
       function(App, Marionette,
                settingsLayoutTpl, userEditTpl, generalSettingsTpl,
                generalSettingsItemTpl, licenseTpl, utils){
    var views = {};

    views.GeneralItemView = Marionette.ItemView.extend({
        template: generalSettingsItemTpl,
        tagName: 'div',

        className: function(){
            var className = 'link-wrapper',
                billing = this.model.collection.findWhere({name: 'billing_type'}).get('value'),
                name = this.model.get('name');

            if (billing === 'No billing' && _.contains(
                    ['billing_url', 'billing_username', 'billing_password', 'sso_secret_key'], name))
                className += ' hidden';
            return className;
        },

        ui: {
            itemField: '.settings-item',
        },

        events: {
            'change @ui.itemField': 'fieldChange'
        },

        fieldChange: function(evt){
            evt.stopPropagation();
            var tgt = $(evt.target),
                value = tgt.val(),
                trimmedValue = value.trim();
            if (this.model.get('options')) {
                value = this.model.get('options')[+value];
            }
            // Strip dangling spaces for all fields except password
            if (trimmedValue !== value && !_.contains(['billing_type', 'billing_password'],
                                                     this.model.get('name'))) {
                tgt.val(trimmedValue);
                this.model.set({value: trimmedValue});
            }
            else {
                this.model.set({value: value});
            }

            // toggle billing settings, depending on selected billing type
            if (this.model.get('name') === 'billing_type'){
                $('#billing_url, #billing_username, #billing_password, #sso_secret_key').parent()
                    .toggleClass('hidden', this.model.get('value') === 'No billing');
            }
        },

        onRender: function() {
            var options = this.model.get('options');
            if (options) {
                this.ui.itemField.selectpicker();
                this.ui.itemField.selectpicker(
                    'val', options.indexOf(this.model.get('value')));
            }
        },
    });

    views.GeneralView = Marionette.CompositeView.extend({
        template: generalSettingsTpl,
        childView: views.GeneralItemView,
        childViewContainer: 'div#settings-list',

        events: {
            'click [type="submit"]': 'submitSettings'
        },

        submitSettings: function(){
            var changed = this.collection.filter(function(m){ return m.hasChanged('value'); });
            if (changed.length) {
                _.each(changed, function(m){
                    m.save(null, {wait: true})
                        .fail(utils.notifyWindow)
                        .done(function(){
                            var msg = (m.get('name') === 'billing_type' ?
                                       'Billing system changed successfully' :
                                       m.get('label') + ' changed successfully');
                            utils.notifyWindow(msg, 'success');
                        });
                });
            }
            else {
                utils.notifyWindow('Data has not been changed.', 'success');
            }
        }
    });

    views.LicenseView = Marionette.ItemView.extend({
        template: licenseTpl,
        templateHelpers: {
            formatDate: function(dt) {
                if (dt) {
                    return App.currentUser.localizeDatetime(dt);
                }
                return 'unknown';
            }
        },

        initialize: function(){
            this.checkLimits();
        },

        modelEvents: {
            'change': 'modelChanged'
        },

        modelChanged: function(evt){
            this.checkLimits();
            this.render();
        },

        checkLimits: function(){
            var results,
                that = this,
                data = this.model.get('data');

            _.each(data, function(item){
                !that.comparison(item[0],item[1])
                    ? item[3] = true
                    : item[3] = false;
            });

            results = _.any(data, function(item){ return !that.comparison(item[0],item[1]); });
            this.model.set({attention: results}, {silent: true});
        },

        updateStatistics: function(evt){
            evt.stopPropagation();
            var that = this;
            this.ui.updateStats.addClass('start-atimation');
            this.model.fetch({
                wait: true,
                data: {force: true},
                success: function(model, resp, opts){
                    that.ui.updateStats.removeClass('start-atimation');
                    utils.notifyWindow('Status has been updated', 'success');
                },
                error: function(){
                    that.ui.updateStats.removeClass('start-atimation');
                    console.log('Could not fetch statistics');  //eslint-disable-line no-console
                }
            });
        },

        comparison: function(a, b){
            if (a == 'unlimited' || a == 0) a = Infinity;
            return a > b ? true : false;
        },

        ui: {
            peditable   : '.peditable',
            updateStats : '.check-for-update',
            tooltip     : '[data-toggle="tooltip"]'
        },

        events: {
            'click @ui.updateStats': 'updateStatistics'
        },

        onRender: function(){
            var that = this;
            this.ui.tooltip.tooltip();
            this.ui.peditable.editable({
                type: 'text',
                mode: 'inline',
                pk: 1,
                name: 'installationID',
                url: '/api/pricing/license/installation_id',
                validate: function(newValue) {
                    if (!newValue.trim()) {
                        utils.notifyWindow('Empty installation ID is not allowed.');
                        return ' ';  // return string - means validation not passed
                    }
                    if (newValue.trim().length > 32){
                        utils.notifyWindow('Maximum length is 32 symbols');
                        return ' ';
                    }
                },
                success: function(response, newValue) {
                    that.model.set(_.has(response, 'data') ? response.data : response);
                    utils.notifyWindow('New instalattion ID "' + newValue + '" is saved',
                                       'success');
                },
                error: function(response, newValue) {
                    that.model.set({name: newValue});
                    utils.notifyWindow(response);
                },
            });
        }
    });

    /* Profile edit */
    views.ProfileEditView = Backbone.Marionette.ItemView.extend({
        template: userEditTpl,

        initialize: function(options){
            this.timezones = options.timezones;
        },

        ui: {
            'first_name'       : 'input#firstname',
            'last_name'        : 'input#lastname',
            'middle_initials'  : 'input#middle_initials',
            'password'         : 'input#password',
            'password_again'   : 'input#password-again',
            'email'            : 'input#email',
            'timezone'         : 'select#timezone',
            'save'             : 'button#template-save-btn',
            'back'             : 'button#template-back-btn',
            'editBtn'          : '#template-edit-btn',
            'input'            : 'input',
            /*'deleteBtn'        : '#template-remove-btn'*/
        },

        events: {
            'click @ui.back'       : 'back',
            'click @ui.save'       : 'onSave',
            'click @ui.editBtn'    : 'editTemplate',
            'change @ui.input'     : 'changeValue',
            'keyup @ui.input'     : 'changeValue',
            'change @ui.timezone'  : 'changeValue',
            'focus @ui.input'      : 'removeError',
            /*'click @ui.deleteBtn'  : 'deleteProfile',*/
        },

        templateHelpers: function(){
            return {
                edit: this.model.in_edit,
                first_name: this.model.get('first_name'),
                last_name: this.model.get('last_name'),
                middle_initials: this.model.get('middle_initials'),
                email: this.model.get('email'),
                timezone: this.model.get('timezone'),
                timezones: this.timezones,
            };
        },

        onRender: function(){
            this.ui.first_name.val(this.model.get('first_name'));
            this.ui.last_name.val(this.model.get('last_name'));
            this.ui.middle_initials.val(this.model.get('middle_initials'));
            this.ui.email.val(this.model.get('email'));
            this.ui.timezone.val(this.model.get('timezone'));
            this.ui.timezone.selectpicker({ size: 7 });
        },

        changeValue: function(){
            var equal,
            oldData = {
                'first_name'      : this.model.get('first_name'),
                'last_name'       : this.model.get('last_name'),
                'middle_initials' : this.model.get('middle_initials'),
                'email'           : this.model.get('email'),
                'password'        : '',
                'timezone'        : this.model.get('timezone').split(' (', 1)[0],
            },
            newData = {
                'first_name'      : this.ui.first_name.val(),
                'last_name'       : this.ui.last_name.val(),
                'middle_initials' : this.ui.middle_initials.val(),
                'email'           : this.ui.email.val(),
                'password'        : this.ui.password.val(),
                'timezone'        : this.ui.timezone.val().split(' (', 1)[0],
            };

            equal = _.isEqual(oldData, newData);
            equal === false ? this.ui.save.show() : this.ui.save.hide();
        },

        back: function(){
            this.model.in_edit = false;
            this.render();
        },

        editTemplate: function(){
            this.model.in_edit = true;
            this.render();
        },

        /*deleteProfile: function(){
            var that = this;
            utils.modalDialogDelete({
                title: "Terminate account?",
                body: "Are you sure you want to terminate your account ?",
                small: true,
                show: true,
                footer: {
                    buttonOk: function(){
                        that.model.destroy(undefined, {
                            wait: true,
                            success: function(){
                                that.model.in_edit = false;
                                that.render();
                            },
                        })
                    },
                    buttonCancel: true
                }
            });
        },*/

        removeError: function(evt){
            var target = $(evt.target);
            if (target.hasClass('error')) target.parent().find('.notifyjs-metro-error').click();
        },

        onSave: function(){
            var firtsName = this.ui.first_name.val(),
                lastName = this.ui.last_name.val(),
                middleInitials = this.ui.middle_initials.val(),
                spaces = /\s/g,
                numbers = /\d/g,
                symbols = /[!"#$%&'()*+,\-.\/\\:;<=>?@[\]^_`{\|}~]/g,
                pattern = /^("\S+"|[a-z0-9_\.+-]+)@(([a-z0-9-]+\.)+[a-z0-9-]+|\[[a-f0-9:\.]+\])$/i;

            this.ui.first_name.val(firtsName.replace(symbols,'').replace(spaces,'').replace(numbers,''));
            this.ui.last_name.val(lastName.replace(symbols,'').replace(spaces,'').replace(numbers,''));
            this.ui.middle_initials.val(middleInitials.replace(symbols,'').replace(spaces,'').replace(numbers,''));

            var data = {
                    'first_name': this.ui.first_name.val(),
                    'last_name': this.ui.last_name.val(),
                    'middle_initials': this.ui.middle_initials.val(),
                    'email': this.ui.email.val(),
                    'timezone': this.ui.timezone.val(),
                };

            if (data.email == '') {
                utils.scrollTo(this.ui.email);
                utils.notifyInline('Empty E-mail',this.ui.email);
                return;
            } else if (!pattern.test(data.email)) {
                utils.scrollTo(this.ui.email);
                utils.notifyInline('E-mail must be correct',this.ui.email);
                return;
            }
            if (this.ui.password.val() !== this.ui.password_again.val()) {
                utils.scrollTo(this.ui.password);
                this.ui.password.addClass('error');
                utils.notifyInline("Passwords don\'t match",this.ui.password_again);
                return;
            }
            if (this.ui.password.val())  // update only if specified
                data.password = this.ui.password.val();

            this.model.save(data, {wait: true, patch: true, context: this})
                .fail(utils.notifyWindow)
                .done(function(){
                    this.model.in_edit = false;
                    this.render();
                    utils.notifyWindow('Profile changed successfully', 'success');
                });
        }
    });

    views.SettingsLayout = Marionette.LayoutView.extend({
        template: settingsLayoutTpl,
        regions: {
            nav: 'div#nav',
            main: 'div#details_content'
        },

        ui: {
            tabButton : 'ul.nav-sidebar li',
            general   : 'li.general'
        },

        events: {
            'click @ui.tabButton' : 'changeTab'
        },

        templateHelpers: function(){ return {user: App.currentUser}; },

        onBeforeShow: function(){
            utils.preloader.show();
        },

        onShow: function(){
            utils.preloader.hide();
        },

        changeTab: function (evt) {
            evt.preventDefault();
            var tgt = $(evt.target);
            if (tgt.hasClass('general')) App.navigate('settings/general', {trigger: true});
            if (tgt.hasClass('license')) App.navigate('settings/license', {trigger: true});
            else if (tgt.hasClass('profile')) App.navigate('settings/profile', {trigger: true});
            else if (tgt.hasClass('permissions')) App.navigate('settings/permissions', {trigger: true});
            else if (tgt.hasClass('notifications')) App.navigate('settings/notifications', {trigger: true});
        },

        onRender: function(){
            var that = this,
                tabs = that.ui.tabButton,
                href = window.location.hash.split('/')[1];

            utils.preloader.hide();

            _.each(tabs, function(item){
                if (item.className == href) {
                    $(item).addClass('active');
                } else if (!href) {
                    that.ui.general.addClass('active');
                }
                else {
                    $(item).removeClass('active');
                }
            });
        }
    });

    return views;
});

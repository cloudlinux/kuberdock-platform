import App from 'app_data/app';
import Model from 'app_data/model';
import * as utils from 'app_data/utils';
import userItemTpl from 'app_data/users/templates/user_item.tpl';
import onlineUserItemTpl from 'app_data/users/templates/online_user_item.tpl';
import activityItemTpl from 'app_data/users/templates/activity_item.tpl';
import usersListTpl from 'app_data/users/templates/users_list.tpl';
import onlineUsersListTpl from 'app_data/users/templates/online_users_list.tpl';
import usersActivitiesTpl from 'app_data/users/templates/users_activities.tpl';
import allUsersActivitiesTpl from 'app_data/users/templates/all_users_activities.tpl';
import userCreateTpl from 'app_data/users/templates/user_create.tpl';
import userProfileLogHistoryTpl from 'app_data/users/templates/user_profile_log_history.tpl';
import userProfileTpl from 'app_data/users/templates/user_profile.tpl';
import usersLayoutTpl from 'app_data/users/templates/users_layout.tpl';
import 'jquery-ui/ui/widgets/datepicker';       // we don't need to import
import 'jquery-ui/themes/base/datepicker.css';  // whole jquery-ui
import 'bootstrap-select';
import 'bootstrap-3-typeahead';

export const UserItem = Marionette.ItemView.extend({
    template : userItemTpl,
    tagName  : 'tr',

    ui: {
        'remove_user'    : '.deleteUser',
        'block_user'     : '.blockUser',
        'activated_user' : '.activeteUser'
    },

    events: {
        'click @ui.block_user'     : 'blockUser',
        'click @ui.activated_user' : 'activatedUser',
        'click @ui.remove_user'    : 'removeUserConfirm',
    },

    templateHelpers: function(){
        var podsCount = this.model.get('pods_count'),
            containersCount = this.model.get('containers_count');
        return {
            podsCount: podsCount ? podsCount : 0,
            containersCount: containersCount ? containersCount : 0,
        };
    },

    removeUserConfirm: function(){
        this.model.deleteUserConfirmDialog();
    },

    blockUser: function(){
        var that = this;
        utils.modalDialog({
            title: "Block " + this.model.get('username'),
            body: "Are you sure you want to block user '" +
                this.model.get('username') + "'?",
            small: true,
            show: true,
            footer: {
                buttonOk: function(){
                    utils.preloader.show();
                    that.model.save({active: false}, {wait: true, patch: true})
                        .always(utils.preloader.hide)
                        .fail(utils.notifyWindow)
                        .done(that.render);
                },
                buttonCancel: true
            }
        });
    },

    activatedUser: function(){
        utils.preloader.show();
        this.model.save({active: true}, {wait: true, patch: true})
            .always(utils.preloader.hide)
            .fail(utils.notifyWindow)
            .done(this.render);
    }
});

export const OnlineUserItem = Marionette.ItemView.extend({
    template : onlineUserItemTpl,
    tagName  : 'tr',

    ui: {
        'userActivityHistory' : "button.userActivityHistory"
    },

    events: {
        'click @ui.userActivityHistory' : 'userActivityHistory_btn'
    },

    userActivityHistory_btn: function(){
        App.navigate('/online/' + this.model.id + '/', {trigger: true});
    }
});

export const ActivityItem = Marionette.ItemView.extend({
    template : activityItemTpl,
    tagName  : 'tr'
});

export const UsersListView = Marionette.CompositeView.extend({
    template           : usersListTpl,
    childView          : UserItem,
    childViewContainer : "tbody",

    ui: {
        'create_user'        : 'button#create_user',
        'edit_selected_user' : 'span#editUser',
        'activity_page'      : '.activityPage',
        'online_page'        : '.onlinePage',
        'user_search'        : 'input#nav-search-input',
        'navSearch'          : '.nav-search',
        'th'                 : 'table th'
    },

    events: {
        'click @ui.create_user'            : 'createUser',
        'click @ui.remove_selected_user'   : 'removeSelectedUser',
        'click @ui.edit_selected_user'     : 'editSelectedUser',
        'click @ui.block_selected_user'    : 'blockSelectedUser',
        'click @ui.activate_selected_user' : 'activateSelectedUser',
        'click @ui.activity_page'          : 'activity',
        'click @ui.online_page'            : 'online',
        'keyup @ui.user_search'            : 'filter',
        'click @ui.navSearch'              : 'showSearch',
        'blur @ui.user_search'             : 'closeSearch',
        'click @ui.th'                     : 'toggleSort'
    },


    initialize: function() {
        this.counter = 1;
        this.sortingType = {
            username : 1,
            pods_count : 1,
            containers_count : 1,
            email : 1,
            package : 1,
            rolename : 1,
            active : 1
        };
    },

    templateHelpers: function(){
        return {
            sortingType : this.sortingType
        };
    },

    toggleSort: function(e) {
        var that = this,
            targetClass = e.target.className;

        if (targetClass) {
            this.collection.setSorting(targetClass, this.counter);
            this.collection.fullCollection.sort();
            this.counter = this.counter * (-1);

            if (that.sortingType[targetClass] == 1){
                _.each(that.sortingType, function(item, index){
                    that.sortingType[index] = 1;
                });
                that.sortingType[targetClass] = -1;
            } else {
                that.sortingType[targetClass] = 1;
            }
            this.render();
        }
    },

    //showSearch: function(){
    //    this.ui.navSearch.addClass('active');
    //    this.ui.user_search.focus();
    //},
    //
    //closeSearch: function(){
    //    this.ui.navSearch.removeClass('active');
    //},

    createUser: function(){
        App.navigate('users/create', {trigger: true});
    },

    activity: function(){
        App.navigate('users/activity', {trigger: true});
    },

    online: function(){
        App.navigate('users/online', {trigger: true});
    }
});

export const OnlineUsersListView = Marionette.CompositeView.extend({
    template           : onlineUsersListTpl,
    childView          : OnlineUserItem,
    childViewContainer : "tbody",

    ui: {
        'users_page'    : '.usersPage',
        'activity_page' : '.activityPage'
    },

    events: {
        'click @ui.activity_page' : 'activity',
        'click @ui.users_page'    : 'back'
    },

    back: function(){
        App.navigate('users', {trigger: true});
    },

    activity: function(){
        App.navigate('users/activity/', {trigger: true});
    }
});

export const UsersActivityView = Marionette.CompositeView.extend({
    template           : usersActivitiesTpl,
    childView          : ActivityItem,
    childViewContainer : "tbody",
});

export const AllUsersActivitiesView = Marionette.ItemView.extend({
    template: allUsersActivitiesTpl,

    ui: {
        'dateFrom'    : 'input#dateFrom',
        'dateTo'      : 'input#dateTo',
        'usersList'   : 'ul#users-list',
        'tbody'       : '#users-activities-table',
        'users_page'  : '#users-page, .usersPage',
        'username'    : '#username',
        'calendarIco' : '.calendar',
        'searchIco'   : 'i.search'
    },

    events: {
        'change input.user-activity' : 'getUsersActivities',
        'change @ui.dateFrom'        : 'getUsersActivities',
        'change @ui.dateTo'          : 'getUsersActivities',
        'click @ui.users_page'       : 'back',
        'click @ui.calendarIco'      : 'focusInput',
        'click @ui.searchIco'        : 'focusInput',
        'focus @ui.dateTo'           : 'removeError',
        'focus @ui.dateFrom'         : 'removeError',
        'focus @ui.username'         : 'removeError',
        'keypress @ui.username'      : 'selectUserByEnterKey'
    },

    selectUserByEnterKey: function(e){
        var that = this;
        if (e.which === 13) {  // 'Enter' key
            e.stopPropagation();
            that.ui.username.blur();
            that.getUsersActivities();
        }
    },

    focusInput: function(e){ $(e.target).parent().find('input').focus(); },

    removeError: function(evt){ utils.removeError($(evt.target)); },

    _getActivities: function(username, dateFrom, dateTo){
        var that = this,
            usernameOk = true,
            dateOk = true,
            invalidUsernameFormat = Model.UserModel.checkUsernameFormat(username);
        if (username && invalidUsernameFormat){
            utils.scrollTo(this.ui.username);
            utils.notifyInline(invalidUsernameFormat, this.ui.username);
            usernameOk = false;
        }

        if (dateFrom > dateTo){
            utils.scrollTo(this.ui.dateFrom);
            utils.notifyInline('Start date may not exceed the end date',
                               this.ui.dateFrom);
            this.ui.dateTo.addClass('error');
            dateOk = false;
        }

        if (username && dateFrom && dateTo && dateOk && usernameOk){
            utils.preloader.show();
            $.ajax({  // TODO: use Backbone.Model
                authWrap: true,
                url: '/api/users/a/' + username,
                data: {date_from: dateFrom, date_to: dateTo},
                dataType: 'JSON',
            }).always(utils.preloader.hide).fail(utils.notifyWindow)
                .done(function(rs){
                    if (rs.data){
                        that.ui.tbody.empty();
                        if (rs.data.length === 0){
                            that.ui.tbody.append($('<tr>').append(
                                '<td colspan="3" align="center" ' +
                                'class="disabled-color-text">Nothing found</td>'
                            ));
                        } else {
                            _.each(rs.data, function(itm){
                                that.ui.tbody.append($('<tr>').append(
                                   // '<td>' + itm.username + '</td>' +
                                   // '<td>' + itm.rolename + '</td>' +
                                    '<td>' + itm.action + '</td>' +
                                    '<td>' + App.currentUser.localizeDatetime(itm.ts) + '</td>' +
                                    '<td>' + itm.remote_ip + '</td>'
                                   // '<td>' + itm.ts + '</td>'
                                ));
                            });
                        }
                    }
                });
        }
    },

    onRender: function(){
        // Init datepicker
        var now = utils.dateYYYYMMDD();
        this.ui.dateFrom.datepicker({
            dateFormat: "yy-mm-dd",
            maxDate: now
        });
        this.ui.dateTo.datepicker({
                dateFormat : "yy-mm-dd",
                maxDate: now
        });
        // Set default date
        this.ui.dateFrom.val(now);
        this.ui.dateTo.val(now);
        // init user autocomplete field
        this.ui.username.typeahead({
            autoSelect: false,
            source: (query, process) => {
                this.ui.username.data('ready', false);
                $.ajax({  // TODO: use Backbone.Model
                    authWrap: true,
                    url: '/api/users/q',
                    data: {'s': this.ui.username.val()},
                    cache: false,
                }).fail(utils.notifyWindow).done(function(rs){ process(rs.data); });
            },
            updater: (v) => {
                this.ui.username.data('ready', true);
                this._getActivities(
                    v,
                    this.ui.dateFrom.val(),
                    this.ui.dateTo.val()
                );
                return v;
            }
        });
    },

    getUsersActivities: function(){
        var username = this.ui.username.val().trim();
        this.ui.username.val(username);
        this.ui.tbody.empty();
        this._getActivities(
            username,
            this.ui.dateFrom.val(),
            this.ui.dateTo.val()
        );
    },

    back: function(){
       App.navigate('users', {trigger: true});
    }
});

export const UserFormBaseView = Marionette.ItemView.extend({
    template : userCreateTpl,
    tagName  : 'div',

    initialize: function(options){
        this.roles = options.roles;
        this.packages = options.packages;
        this.timezones = options.timezones;
        this.listenTo(this, 'render',
            function(){ this.ui.selectpicker.selectpicker({size: 7}); });
    },

    templateHelpers: function(){
        return {
            isNew: this.model.isNew(),
            roles: this.roles,
            packages: this.packages,
            timezones: this.timezones,
        };
    },

    ui: {
        'username'        : 'input#username',
        'first_name'      : 'input#firstname',
        'last_name'       : 'input#lastname',
        'middle_initials' : 'input#middle_initials',
        'password'        : 'input#password',
        'password_again'  : 'input#password-again',
        'email'           : 'input#email',
        'timezone'        : 'select#timezone',
        'user_status'     : 'select#status-select',
        'user_suspend'    : 'input#suspended',
        'role_select'     : 'select#role-select',
        'package_select'  : 'select#package-select',
        'users_page'      : 'div#users-page',
        'user_add_btn'    : 'button#user-add-btn',
        'user_cancel_btn' : 'button#user-cancel-btn',
        'selectpicker'    : '.selectpicker',
        'input'           : 'input'
    },

    events: {
        'click @ui.users_page'     : 'toUserList',
        'click @ui.user_cancel_btn': 'toUserList',
        'focus @ui.input'          : 'removeError',
    },

    getData: function(passwordAgain){
        let data = {
                'username'        : this.ui.username.val(),
                'first_name'      : this.ui.first_name.val(),
                'last_name'       : this.ui.last_name.val(),
                'middle_initials' : this.ui.middle_initials.val(),
                'password'        : this.ui.password.val(),
                'password_again'  : this.ui.password_again.val(),
                'email'           : this.ui.email.val(),
                'timezone'        : this.ui.timezone.val(),
                'active'          : this.ui.user_status.val() === '1',
                'suspended'       : this.ui.user_suspend.prop('checked'),
                'rolename'        : this.ui.role_select.val(),
                'package'         : this.ui.package_select.val(),
            };
        if (!passwordAgain) data = _.omit(data, 'password_again');
        return data;
    },

    validate: function(isNew){
        var that = this,
            deferred = new $.Deferred();
        App.getUserCollection().done(function(users){
            var firtsName = that.ui.first_name.val(),
                lastName = that.ui.last_name.val(),
                middleInitials = that.ui.middle_initials.val(),
                spaces = /\s/g,
                numbers = /\d/g,
                symbols = /[!#$%*+\/\\:;<=>?@^{\|}~]/g,
                pattern = /^("\S+"|[a-z0-9_\.+-]+)@(([a-z0-9-]+\.)+[a-z0-9-]+|\[[a-f0-9:\.]+\])$/i;

            that.ui.first_name.val(firtsName.trim());
            that.ui.last_name.val(lastName.trim());
            that.ui.middle_initials.val(middleInitials.trim());
            that.ui.email.val(that.ui.email.val().trim());

            if (isNew)
                that.ui.username.val(that.ui.username.val().trim());

            var existsUsername = isNew && _.invoke(users.pluck('username'), 'toLowerCase')
                    .indexOf(that.ui.username.val().toLowerCase()) !== -1,
                existsEmail = users.chain().without(that.model).pluck('attributes')
                    .pluck('email').filter().invoke('toLowerCase')
                    .indexOf(that.ui.email.val().toLowerCase()).value() !== -1,
                invalidUsernameFormat = isNew && Model.UserModel.checkUsernameFormat(
                    that.ui.username.val());

            that.ui.input.removeClass('error');

            switch (true) {
            /* username */
            case isNew && !that.ui.username.val():
                that.addError(that.ui.username, 'Username is required.');
                break;
            case isNew && !!invalidUsernameFormat:
                that.addError(that.ui.username, invalidUsernameFormat);
                break;
            case isNew && existsUsername:
                that.addError(that.ui.username, 'Username should be unique.');
                break;
            /* name */
            case that.ui.first_name.val().length > 25:
                that.addError(that.ui.first_name, 'Maximum length is 25 symbols.');
                break;
            case symbols.test(that.ui.first_name.val()) ||
                 spaces.test(that.ui.first_name.val()) ||
                 numbers.test(that.ui.first_name.val()) :
                    that.addError(that.ui.first_name, 'First name can\'t have special' +
                                                     ' symbols, numbers or spaces');
                break;
            case that.ui.last_name.val().length > 25:
                that.addError(that.ui.last_name, 'Maximum length is 25 symbols.');
                break;
            case symbols.test(that.ui.last_name.val()) ||
                 spaces.test(that.ui.last_name.val()) ||
                 numbers.test(that.ui.last_name.val()) :
                    that.addError(that.ui.last_name, 'Last name can\'t have special' +
                                                     ' symbols, numbers or spaces');
                break;
            case that.ui.middle_initials.val().length > 25:
                that.addError(that.ui.middle_initials, 'Maximum length is 25 symbols.');
                break;
            case symbols.test(that.ui.middle_initials.val()) ||
                 spaces.test(that.ui.middle_initials.val()) ||
                 numbers.test(that.ui.middle_initials.val()) :
                    that.addError(that.ui.middle_initials,
                        'Middle initials can\'t have special symbols, numbers or spaces');
                break;
            /* password */
            case that.ui.password.val() !== that.ui.password_again.val():
                that.addError(that.ui.password_again, "Passwords don't match.");
                that.ui.password.addClass('error');
                break;
            case isNew && !that.ui.password.val():
                that.addError(that.ui.password_again, 'Password is required.');
                that.ui.password.addClass('error');
                break;
            case that.ui.password.val().length > 25:
                that.addError(that.ui.password_again, 'Maximum length is 25 symbols.');
                that.ui.password.addClass('error');
                break;
            /* email */
            case !that.ui.email.val():
                that.addError(that.ui.email, 'E-mail is required.');
                break;
            case !pattern.test(that.ui.email.val()):
                that.addError(that.ui.email, 'The E-mail format is invalid.');
                break;
            case that.ui.email.val().length > 50:
                that.addError(that.ui.email, 'Maximum length is 50 symbols.');
                break;
            case existsEmail:
                that.addError(that.ui.email, 'E-mail should be unique.');
                break;
            default:
                deferred.resolve();
                return;
            }
            deferred.reject();
        });
        return deferred.promise();
    },

    addError: function(el, message){
        utils.scrollTo(el);
        utils.notifyInline(message, el);
    },

    removeError: function(evt){ utils.removeError($(evt.target)); },

    toUserList: function(){ App.navigate('users', {trigger: true}); },
});

export const UserCreateView = UserFormBaseView.extend({
    events: function(){
        return _.extend({}, this.constructor.__super__.events, {
            'click @ui.user_cancel_btn': 'toUserList',
            'click @ui.user_add_btn'   : 'onSave',
        });
    },

    restoreByEmail: function(email){
        App.getUserCollection().done(function(users){
            utils.modalDialog({
                title: 'User exists',
                body: 'The email you are trying to use is already present' +
                    ' in your billing system. Looks like there is a deleted' +
                    ' user with this email. Would you like to restore the user' +
                    ' and tie him to existing billing user instead?',
                small: true,
                show: true,
                footer: {
                    buttonOk: function(){
                        Model.UserModel.restoreByEmail(email)
                            .done(() => {
                                utils.notifyWindow(
                                    `User "${email}" successfully restored`,
                                    'success');
                                App.navigate('users').controller.showUsers();
                            })
                            .fail(() => {
                                utils.notifyWindow(`Could not restore user "${email}"`);
                            });
                    },
                    buttonCancel: function(){
                        App.navigate('users')
                            .controller.showUsers();
                    },
                    buttonOkText: 'Yes, restore',
                    buttonCancelText: 'No, thanks'
                }
            });
        });
    },

    onSave: function(){
        $.when(App.getUserCollection(), this.validate(true)).done((users) => {
            utils.preloader.show();
            this.model.save(this.getData(), {wait: true})
                .always(utils.preloader.hide)
                .fail((resp) => {
                    var msg = resp.responseJSON.data || '',
                        type = resp.responseJSON.type || '',
                        emailRx = /user[\s\S]*?exist[\s\S]*?email/i;
                    if (type === 'BillingError' && emailRx.test(msg)) {
                        this.restoreByEmail(this.getData().email);
                    } else {
                        utils.notifyWindow(resp);
                    }
                })
                .done(() => {
                    users.add(this.model);
                    App.navigate('users', {trigger: true});
                    utils.notifyWindow(
                        `User "${this.model.get('username')}" created successfully`,
                        'success');
                });
        });
    },
});

export const UserProfileLogHistory = Marionette.ItemView.extend({
    template : userProfileLogHistoryTpl,
    tagName  : 'div',

    ui: {
        'delete_user_btn'     : 'button#delete_user',
        'login_this_user_btn' : 'button#login_this_user',
        'tb'                  : '#user-profile-logs-table tbody'
    },

    events: {
        'click @ui.delete_user_btn'     : 'delete_user',
        'click @ui.login_this_user_btn' : 'login_this_user',
    },

    onRender: function(e){
        utils.preloader.show();
        $.ajax({  // TODO: use Backbone.Model
            authWrap: true,
            url: '/api/users/logHistory',
            data: {'uid': this.model.get('id')},
        }).always(utils.preloader.hide).fail(utils.notifyWindow)
            .done((rs) => {
                if (rs.data.length !== 0){
                    _.each(rs.data, (itm) => {
                        this.ui.tb.append($('<tr>').append(
                            '<td>' + App.currentUser.localizeDatetime(itm[0]) + '</td>' +
                            '<td>' + utils.toHHMMSS(itm[1]) + '</td>' +
                            '<td>' + App.currentUser.localizeDatetime(itm[2]) + '</td>' +
                            '<td>' + itm[3] + '</td>'
                        ));
                    });
                } else {
                    this.ui.tb.append($('<tr>').append(
                        '<td colspan="4" class="text-center">There is no ' +
                        'login history for this user</td>'));
                }
            });
    },

    login_this_user: function(){
        this.model.loginConfirmDialog();
    },

    delete_user: function(){
        this.model.deleteUserConfirmDialog({
            success: function(){
                App.navigate('users', {trigger: true});
            },
        });
    },
});

export const UserProfileView = Marionette.ItemView.extend({
    template : userProfileTpl,
    tagName  : 'div',

    initialize: function(options){
        this.kubeTypes = options.kubeTypes;
    },

    ui: {
        'delete_user_btn'     : 'button#delete_user',
        'login_this_user_btn' : 'button#login_this_user'
    },

    events: {
        'click @ui.delete_user_btn'     : 'delete_user',
        'click @ui.login_this_user_btn' : 'login_this_user'
    },

    templateHelpers: function(){
        var kubesCount = 0;

        _.each(this.model.get('pods'), function(pod) {
            var config = JSON.parse(pod.config);
            _.each(config.containers, function(c) {
                kubesCount += c.kubes;
            });
        });

        return {
            kubeTypes: this.kubeTypes,
            kubes: kubesCount,
            toHHMMSS: utils.toHHMMSS,
            currentUser: App.currentUser
        };
    },

    login_this_user: function(){
        this.model.loginConfirmDialog();
    },

    delete_user: function(){
        this.model.deleteUserConfirmDialog({
            success: function(){
                App.controller.showUsers();
            },
        });
    }
});

export const UsersEditView = UserFormBaseView.extend({
    events: function(){
        return _.extend({}, this.constructor.__super__.events, {
            'click @ui.user_cancel_btn'         : 'cancel',
            'click @ui.user_add_btn'            : 'onSave',
            'input @ui.input'                   : 'toggleShowAddBtn',
            'change @ui.selectpicker'           : 'toggleShowAddBtn',
            'change @ui.input[type="checkbox"]' : 'toggleShowAddBtn',
        });
    },

    isEqual: function(){
        var data = this.getData(true);
        if (data.password || data.password_again){
            data.password = data.password || data.password_again;
            delete data.password_again;
        }
        var orig = _.mapObject(this.model.attributes,
                               val => val == null ? '' : val);
        return _.isMatch(orig, data);
    },

    toggleShowAddBtn: function(){
        if (!this.isEqual())
            this.ui.user_add_btn.show();
        else
            this.ui.user_add_btn.hide();
    },

    cancel: function(){
        App.navigate('users/profile/' + this.model.id + '/general', {trigger: true});
    },

    getData: function(){
        var data = _.omit(this.constructor.__super__.getData.apply(this, arguments), 'username');
        if (!data.password && !data.password_again){   // ignore if not specified
            delete data.password;
            delete data.password_again;
        }
        return data;
    },

    onSave: function(){
        var that = this;

        $.when(App.getUserCollection(), this.validate(false)).done(function(users){
            utils.preloader.show();
            that.model.save(that.getData(), {wait: true, patch: true})
                .always(utils.preloader.hide)
                .fail(utils.notifyWindow)
                .done(function(){
                    App.navigate('users/profile/' + that.model.id + '/general',
                                 {trigger: true});
                    utils.notifyWindow(
                        'Changes to user "' + that.model.get('username') +
                            '" saved successfully',
                        'success');
                });
        });
    },
});

export const UsersLayout = Marionette.LayoutView.extend({
    template : usersLayoutTpl,
    regions  : {
        nav   : 'div#nav',
        main  : 'div#main',
        pager : 'div#pager'
    },

    onBeforeShow: function(){ utils.preloader.show(); },
    onShow: function(){ utils.preloader.hide(); }
});

define(['app_data/app', 'app_data/controller', 'marionette', 'app_data/utils',
        'tpl!app_data/users/templates/user_item.tpl',
        'tpl!app_data/users/templates/online_user_item.tpl',
        'tpl!app_data/users/templates/activity_item.tpl',
        'tpl!app_data/users/templates/users_list.tpl',
        'tpl!app_data/users/templates/online_users_list.tpl',
        'tpl!app_data/users/templates/users_activities.tpl',
        'tpl!app_data/users/templates/all_users_activities.tpl',
        'tpl!app_data/users/templates/user_create.tpl',
        'tpl!app_data/users/templates/user_profile_log_history.tpl',
        'tpl!app_data/users/templates/user_profile.tpl',
        'tpl!app_data/users/templates/users_layout.tpl',
        'bootstrap', 'jquery-ui', 'jqplot', 'jqplot-axis-renderer', 'selectpicker', 'bootstrap3-typeahead'],
       function(App, Controller, Marionette, utils,
                userItemTpl,
                onlineUserItemTpl,
                activityItemTpl,
                usersListTpl,
                onlineUsersListTpl,
                usersActivitiesTpl,
                allUsersActivitiesTpl,
                userCreateTpl,
                userProfileLogHistoryTpl,
                userProfileTpl,
                usersLayoutTpl){

    var views = {};

    views.UserItem = Backbone.Marionette.ItemView.extend({
        template : userItemTpl,
        tagName  : 'tr',

        ui: {
            'remove_user'    : '.deleteUser',
            'block_user'     : '.blockUser',
            'activated_user' : '.activeteUser',
            'profileUser'    : '.profileUser'
        },

        events: {
            'click @ui.profileUser'    : 'profileUser_btn',
            'click @ui.remove_user'    : 'removeUserConfirm',
            'click @ui.block_user'     : 'blockUser',
            'click @ui.activated_user' : 'activatedUser',
            'click'                    : 'checkUser'
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
        },

        profileUser_btn: function(){
            App.navigate('users/profile/' + this.model.id + '/general', {trigger: true});
        },

        checkUser: function(){
            this.$el.toggleClass('checked').siblings().removeClass('checked');
        }
    });

    views.OnlineUserItem = Marionette.ItemView.extend({
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

    views.ActivityItem = Marionette.ItemView.extend({
        template : activityItemTpl,
        tagName  : 'tr'
    });

    views.UsersListView = Backbone.Marionette.CompositeView.extend({
        template           : usersListTpl,
        childView          : views.UserItem,
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
            }
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
                    })
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

    views.OnlineUsersListView = Marionette.CompositeView.extend({
        template           : onlineUsersListTpl,
        childView          : views.OnlineUserItem,
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

    views.UsersActivityView = Marionette.CompositeView.extend({
        template           : usersActivitiesTpl,
        childView          : views.ActivityItem,
        childViewContainer : "tbody",
    });

    views.AllUsersActivitiesView = Backbone.Marionette.ItemView.extend({
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
            'click @ui.calendarIco'      : 'foncusInput',
            'click @ui.searchIco'        : 'foncusInput',
            'focus @ui.dateFrom'         : 'removeError',
            'keypress @ui.username'      : 'selectUserByEnterKey'
        },

        selectUserByEnterKey: function(e){
            var that = this;
            if (e.which === 13) {  // 'Enter' key
                e.stopPropagation();
                that.getUsersActivities();
                that.ui.username.blur();
            }
        },

        foncusInput: function(e){
            var target = $(e.target);
            target.prev('input').focus();
        },

        removeError: function(evt){
            var target = $(evt.target);
            if (target.hasClass('error')) target.removeClass('error');
        },

        _getActivities: function(username, dateFrom, dateTo){
            var that = this;

            if (dateFrom > dateTo){
                this.ui.dateFrom.addClass('error');
                utils.notifyWindow('Start date may not exceed the end date')
            } else {
                this.ui.dateTo.removeClass('error');
                this.ui.dateFrom.removeClass('error');
            }

            if (username && dateFrom && dateTo){
                utils.preloader.show();
                $.ajax({
                    url: '/api/users/a/' + username,
                    data: {date_from: dateFrom, date_to: dateTo},
                    dataType: 'JSON',
                    success: function(rs){
                        console.log(rs)
                        if(rs.data){
                            that.ui.tbody.empty();
                            if(rs.data.length == 0){
                                that.ui.tbody.append($('<tr>').append(
                                    '<td colspan="3" align="center" class="disabled-color-text">Nothing found</td>'
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
                                })
                            }
                        }
                    },
                    complete: utils.preloader.hide,
                    error: utils.notifyWindow,
                });
            }
        },

        onRender: function(){
            var that = this;
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
                source: function(query, process){
                    that.ui.username.data('ready', false);
                    $.ajax({
                        url: '/api/users/q',
                        data: {'s': that.ui.username.val()},
                        cache: false,
                        success: function(rs){ process(rs.data); },
                        error: utils.notifyWindow,
                    })
                },
                updater: function(v){
                    that.ui.username.data('ready', true);
                    that._getActivities(
                        v,
                        that.ui.dateFrom.val(),
                        that.ui.dateTo.val()
                    );
                    return v;
                }
            });
        },

        getUsersActivities: function(){
            var that = this;
            that.ui.tbody.empty();
            that._getActivities(
                that.ui.username.val(),
                that.ui.dateFrom.val(),
                that.ui.dateTo.val()
            );
        },

        back: function(){
           App.navigate('users', {trigger: true});
        }
    });

    views.UserFormBaseView = Backbone.Marionette.ItemView.extend({
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

        getData: function(){
            return {
                'username'        : this.ui.username.val(),
                'first_name'      : this.ui.first_name.val(),
                'last_name'       : this.ui.last_name.val(),
                'middle_initials' : this.ui.middle_initials.val(),
                'password'        : this.ui.password.val(),
                'email'           : this.ui.email.val(),
                'timezone'        : this.ui.timezone.val(),
                'active'          : this.ui.user_status.val() === 1,
                'suspended'       : this.ui.user_suspend.prop('checked'),
                'rolename'        : this.ui.role_select.val(),
                'package'         : this.ui.package_select.val(),
            };
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
                    symbols = /[!"#$%&'()*+,\-.\/\\:;<=>?@[\]^_`{\|}~]/g,
                    pattern = /^("\S+"|[a-z0-9_\.+-]+)@(([a-z0-9-]+\.)+[a-z0-9-]+|\[[a-f0-9:\.]+\])$/i;

                that.ui.first_name.val(firtsName.replace(symbols,'').replace(spaces,'').replace(numbers,''));
                that.ui.last_name.val(lastName.replace(symbols,'').replace(spaces,'').replace(numbers,''));
                that.ui.middle_initials.val(middleInitials.replace(symbols,'').replace(spaces,'').replace(numbers,''));
                that.ui.email.val(that.ui.email.val().trim());
                if (isNew)
                    that.ui.username.val(that.ui.username.val().trim());


                var existsUsername = isNew && _.invoke(users.pluck('username'), 'toLowerCase')
                        .indexOf(that.ui.username.val().toLowerCase()) !== -1,
                    existsEmail = users.chain().without(that.model).pluck('attributes')
                        .pluck('email').filter().invoke('toLowerCase')
                        .indexOf(that.ui.email.val().toLowerCase()).value() !== -1;

                that.ui.input.removeClass('error');

                switch (true) {
                /* username */
                case isNew && !that.ui.username.val():
                    that.addError(that.ui.username, 'Username is required.');
                    break;
                case isNew && that.ui.username.val().length > 25:
                    that.addError(that.ui.username, 'Maximum length is 25 symbols.');
                    break;
                case isNew && !/^[A-Z\d_-]+$/i.test(that.ui.username.val()):
                    that.addError(that.ui.username,
                                  'Only "-", "_" and alphanumeric symbols are allowed.');
                    break;
                case isNew && !/^[A-Z\d](?:.*[A-Z\d])?$/i.test(that.ui.username.val()):
                    that.addError(that.ui.username,
                                  'Username should start and end with a letter or digit.');
                    break;
                case isNew && !/\D/g.test(that.ui.username.val()):
                    that.addError(that.ui.username, 'Username cannot consist of digits only.');
                    break;
                case isNew && existsUsername:
                    that.addError(that.ui.username, 'Username should be unique.');
                    break;
                /* name */
                case that.ui.first_name.val().length > 25:
                    that.addError(that.ui.first_name, 'Maximum length is 25 symbols.');
                    break;
                case that.ui.last_name.val().length > 25:
                    that.addError(that.ui.last_name, 'Maximum length is 25 symbols.');
                    break;
                case that.ui.middle_initials.val().length > 25:
                    that.addError(that.ui.middle_initials, 'Maximum length is 25 symbols.');
                    break;
                /* password */
                case that.ui.password.val() !== that.ui.password_again.val():
                    that.addError(that.ui.password, "Passwords don't match.");
                    that.ui.password_again.addClass('error');
                    break;
                case isNew && !that.ui.password.val():
                    that.addError(that.ui.password, 'Password is required.');
                    that.ui.password_again.addClass('error');
                    break;
                case that.ui.password.val().length > 25:
                    that.addError(that.ui.password, 'Maximum length is 25 symbols.');
                    that.ui.password_again.addClass('error');
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
            el.addClass('error');
            utils.notifyWindow(message);
        },

        removeError: function(evt){
            var target = $(evt.target);
            if (target.hasClass('error')) target.removeClass('error');
        },

        toUserList: function(){ App.navigate('users', {trigger: true}); },
    });

    views.UserCreateView = views.UserFormBaseView.extend({
        events: function(){
            return _.extend({}, this.constructor.__super__.events, {
                'click @ui.user_cancel_btn': 'toUserList',
                'click @ui.user_add_btn'   : 'onSave',
            });
        },

        onSave: function(){
            var that = this;
            $.when(App.getUserCollection(), this.validate(true)).done(function(users){
                utils.preloader.show();
                that.model.save(that.getData(), {wait: true})
                    .always(utils.preloader.hide)
                    .fail(utils.notifyWindow)
                    .done(function(){
                        users.add(that.model);
                        App.navigate('users', {trigger: true});
                        utils.notifyWindow('User "' + that.model.get('username')
                                           + '" created successfully', 'success');
                    });
            });
        },
    });

    views.UserProfileViewLogHistory = Backbone.Marionette.ItemView.extend({
        template : userProfileLogHistoryTpl,
        tagName  : 'div',

        ui: {
            'generalTab'          : '.generalTab',
            'users_page'          : 'div#users-page',
            'delete_user_btn'     : 'button#delete_user',
            'login_this_user_btn' : 'button#login_this_user',
            'edit_user'           : 'button#edit_user',
            'tb'                  : '#user-profile-logs-table tbody'
        },

        events: {
            'click @ui.generalTab'          : 'generalTab',
            'click @ui.users_page'          : 'back',
            'click @ui.delete_user_btn'     : 'delete_user',
            'click @ui.login_this_user_btn' : 'login_this_user',
            'click @ui.edit_user'           : 'edit_user'
        },

        onRender: function(e){
            var that = this;

            utils.preloader.show();
            $.ajax({
                url: '/api/users/logHistory',
                data: {'uid': this.model.get('id')},
                success: function(rs){
                    if (rs.data.length != 0){
                        _.each(rs.data, function(itm){
                            that.ui.tb.append($('<tr>').append(
                                '<td>' + App.currentUser.localizeDatetime(itm[0]) + '</td>' +
                                '<td>' + utils.toHHMMSS(itm[1]) + '</td>' +
                                '<td>' + App.currentUser.localizeDatetime(itm[2]) + '</td>' +
                                '<td>' + itm[3] + '</td>'
                            ))
                        });
                    } else {
                        that.ui.tb.append($('<tr>').append('<td colspan="4" class="text-center">There is no login history for this user</td>'));
                    }
                },
                complete: utils.preloader.hide,
                error: utils.notifyWindow,
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

        edit_user: function(){
            App.navigate('users/edit/' + this.model.id, {trigger: true});
        },

        generalTab: function(){
            App.navigate('users/profile/' + this.model.id + '/general', {trigger: true});
        },

        back: function(){
            App.navigate('users', {trigger: true});
        }
    });

    views.UserProfileView = Backbone.Marionette.ItemView.extend({
        template : userProfileTpl,
        tagName  : 'div',

        initialize: function(options){
            this.kubeTypes = options.kubeTypes;
        },

        ui: {
            'users_page'          : 'div#users-page',
            'delete_user_btn'     : 'button#delete_user',
            'user_cancel_btn'     : 'button#user-cancel-btn',
            'login_this_user_btn' : 'button#login_this_user',
            'edit_user'           : 'button#edit_user',
            'logHistory'          : '.logHistory'
        },

        events: {
            'click @ui.users_page'          : 'back',
            'click @ui.delete_user_btn'     : 'delete_user',
            'click @ui.login_this_user_btn' : 'login_this_user',
            'click @ui.edit_user'           : 'edit_user',
            'click @ui.logHistory'          : 'logHistory'
        },

        templateHelpers: function(){
            var pods = this.model.get('pods'),
                kubesCount = 0,
                join_date = this.model.get('join_date'),
                last_login = this.model.get('last_login'),
                last_activity = this.model.get('last_activity'),
                first_name = this.model.get('first_name'),
                last_name = this.model.get('last_name');
            _.each(pods, function(pod){
                var config = JSON.parse(pod.config);
                _.each(config.containers, function(c){
                    kubesCount += c.kubes;
                });
            });
            return {
                first_name: first_name ? first_name : '',
                last_name: last_name ? last_name : '',
                join_date: join_date ? App.currentUser.localizeDatetime(join_date) : '',
                last_login: last_login ? App.currentUser.localizeDatetime(last_login) : '',
                last_activity: last_activity ? App.currentUser.localizeDatetime(last_activity) : '',
                pods: pods ? pods : [],
                kubeTypes: _.object(_.map(this.kubeTypes, function(t){return [t.id, t.name]})),
                'kubes': kubesCount,
                toHHMMSS: utils.toHHMMSS,
            };
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

        edit_user: function(){
            App.navigate('users/edit/' + this.model.id, {trigger: true});
        },

        back: function(){
           App.navigate('users', {trigger: true});
        },

        logHistory: function(){
           App.navigate('users/profile/' + this.model.id + '/logHistory', {trigger: true});
        }
    });

    views.UsersEditView = views.UserFormBaseView.extend({
        events: function(){
            return _.extend({}, this.constructor.__super__.events, {
                'click @ui.user_cancel_btn'        : 'cancel',
                'click @ui.user_add_btn'           : 'onSave',
                'input @ui.input'                  : 'changeValue',
                'change @ui.selectpicker'          : 'changeValue',
                'change @ui.input[type="checkbox"]': 'changeValue',
            });
        },

        changeValue: function(){
            var orig = _.mapObject(this.model.attributes,
                                   function(val){ return val === null ? '' : val; }),
                changed = !_.isMatch(orig, this.getData());
            changed ? this.ui.user_add_btn.show() : this.ui.user_add_btn.hide();
        },

        cancel: function(){
            App.navigate('users/profile/' + this.model.id + '/general', {trigger: true});
        },

        getData: function(){
            var data = _.omit(this.constructor.__super__.getData.call(this), 'username');
            if (!data.password)  // ignore if not specified
                delete data.password;
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

    views.UsersLayout = Marionette.LayoutView.extend({
        template : usersLayoutTpl,
        regions  : {
            nav   : 'div#nav',
            main  : 'div#main',
            pager : 'div#pager'
        },

        onBeforeShow: function(){
            utils.preloader.show();
        },

        onShow: function(){
            utils.preloader.hide();
        }
    });

    return views;
});

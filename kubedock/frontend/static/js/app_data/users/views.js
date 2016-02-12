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
                containersCount: containersCount ? containersCount : 0
            }
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
            'focus @ui.dateFrom'         : 'removeError'
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
            var that = this,
                now = utils.dateYYYYMMDD();

            if (dateFrom > dateTo){
                this.ui.dateFrom.addClass('error');
                utils.notifyWindow('Start date may not exceed the end date')
            }

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
            if(!this.ui.username.data('ready')) return;
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

    views.UserCreateView = Backbone.Marionette.ItemView.extend({
        template : userCreateTpl,
        tagName  : 'div',

        initialize: function(options){
            this.roles = options.roles;
            this.packages = options.packages;
            this.timezones = options.timezones;
        },

        templateHelpers: function(){
            var roles = _.filter(this.roles, function(r){return r !== 'HostingPanel'});
                packages = this.packages,
                timezones = this.timezones;
            return {
                roles: roles,
                packages: packages,
                defaultRole: 'User',
                timezones: timezones
            }
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
            'click @ui.users_page'                  : 'back',
            'click @ui.user_cancel_btn'             : 'back',
            'click @ui.user_add_btn'                : 'onSave',
            'focus @ui.input'                       : 'removeError',
            'input @ui.input'                       : 'changeValue',
            'change @ui.selectpicker'               : 'changeValue',
            'change @ui.input[type="checkbox"]'     : 'changeValue',
            'change @ui.timezone'                   : 'changeValue'
        },

        onRender: function(){
            var that = this;
            this.ui.timezone.val('UTC (+0000)');
            this.ui.selectpicker.selectpicker();
        },

        onSave: function(){
            var that = this;
            App.getUserCollection().done(function(userCollection){
                var users = userCollection.models,
                    existsUsername = false,
                    existsEmail = false,
                    username = that.ui.username.val(),
                    pattern = /^("\S+"|[a-z0-9_\.+-]+)@(([a-z0-9-]+\.)+[a-z0-9-]+|\[[a-f0-9:\.]+\])$/i,
                    patternLatin = /^[A-Z0-9](?:[A-Z0-9_-]*[A-Z0-9])?$/i;

                _.each(users, function(user){
                    if (user.get('username') == that.ui.username.val()) existsUsername = true;
                    if (user.get('email') == that.ui.email.val()) existsEmail = true;
                });
                switch (true) {
                /* username */
                case that.ui.username.val() == '':
                    utils.scrollTo(that.ui.username);
                    that.ui.username.notify("Empty username");
                    that.ui.username.addClass('error');
                    break;
                case that.ui.username.val().length >= 26:
                    utils.scrollTo(that.ui.username);
                    that.ui.username.notify("Maximum length should be 25 symbols");
                    that.ui.username.addClass('error');
                    break;
                case !patternLatin.test(that.ui.username.val()):
                    utils.scrollTo(that.ui.username);
                    that.ui.username.notify("Username should contain letters of Latin alphabet only");
                    that.ui.username.addClass('error');
                    break;
                case existsUsername:
                    utils.scrollTo(that.ui.username);
                    that.ui.username.notify('Username should be unique');
                    that.ui.username.addClass('error');
                    break;
                /* first name */
                case that.ui.first_name.val().length >= 26:
                    utils.scrollTo(that.ui.first_name);
                    that.ui.first_name.addClass('error');
                    that.ui.first_name.notify("Maximum length should be 25 symbols");
                    break;
                /* last name */
                case that.ui.last_name.val().length >= 26:
                    utils.scrollTo(that.ui.last_name);
                    that.ui.last_name.addClass('error');
                    that.ui.last_name.notify("Maximum length should be 25 symbols");
                    break;
                /* middle initials */
                case that.ui.middle_initials.val().length >= 26:
                    utils.scrollTo(that.ui.middle_initials);
                    that.ui.middle_initials.addClass('error');
                    that.ui.middle_initials.notify("Maximum length should be 25 symbols");
                    break;
                /* password */
                case !that.ui.password.val() || (that.ui.password.val() !== that.ui.password_again.val()):
                    utils.scrollTo(that.ui.password);
                    that.ui.password.addClass('error');
                    that.ui.password_again.addClass('error');
                    that.ui.password_again.notify("Empty password or don't match");
                    break;
                case that.ui.password.val().length >= 26:
                    utils.scrollTo(that.ui.password);
                    that.ui.password.addClass('error');
                    that.ui.password_again.addClass('error');
                    that.ui.password_again.notify("Maximum length should be 25 symbols");
                    break;
                /* email */
                case that.ui.email.val() == '':
                    utils.scrollTo(that.ui.email);
                    that.ui.email.addClass('error');
                    that.ui.email.notify("Empty E-mail");
                    break;
                case that.ui.email.val() !== '' && !pattern.test(that.ui.email.val()):
                    utils.scrollTo(that.ui.email);
                    that.ui.email.addClass('error');
                    that.ui.email.notify("E-mail must be correct");
                    break;
                case that.ui.email.val().length >= 51:
                    utils.scrollTo(that.ui.email);
                    that.ui.email.addClass('error');
                    that.ui.email.addClass('error');
                    that.ui.email.notify("Maximum length should be 50 symbols");
                    break;
                case existsEmail && that.ui.email.val() !== '':
                    utils.scrollTo(that.ui.email);
                    that.ui.email.notify('Email should be unique');
                    that.ui.email.addClass('error');
                    break;
                /* timezone */
                case that.ui.timezone.val() == '':
                    utils.scrollTo(that.ui.timezone);
                    that.ui.timezone.addClass('error');
                    that.ui.timezone.notify("Empty Timezone");
                    break;
                default:
                    utils.preloader.show();
                    userCollection.create({
                        'username'        : username,
                        'first_name'      : that.ui.first_name.val(),
                        'last_name'       : that.ui.last_name.val(),
                        'middle_initials' : that.ui.middle_initials.val(),
                        'password'        : that.ui.password.val(),
                        'email'           : that.ui.email.val(),
                        'timezone'        : that.ui.timezone.val(),
                        'active'          : (that.ui.user_status.val() == 1),
                        'suspended'       : that.ui.user_suspend.prop('checked'),
                        'rolename'        : that.ui.role_select.val(),
                        'package'         : that.ui.package_select.val(),
                    }, {
                        wait: true,
                        complete: utils.preloader.hide,
                        success: function(data, response){
                            App.navigate('users', {trigger: true});
                            utils.notifyWindow('User "' + username + '" created successfully',
                                               'success');
                        },
                        error: function(collection, response){
                            utils.notifyWindow(response);
                        },
                    });
                }
            });
        },

        removeError: function(evt){
            var target = $(evt.target);
            if (target.hasClass('error')) target.removeClass('error');
        },

        back: function(){
           App.navigate('users', {trigger: true});
        },
    });

    views.UserProfileViewLogHistory = views.UserCreateView.extend({
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
                toHHMMSS: utils.toHHMMSS
            }
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

    views.UsersEditView = views.UserCreateView.extend({     // inherit
        onRender: function(){
            var that = this;
            this.ui.first_name.val(this.model.get('first_name'));
            this.ui.last_name.val(this.model.get('last_name'));
            this.ui.middle_initials.val(this.model.get('middle_initials'));
            this.ui.email.val(this.model.get('email'));
            this.ui.timezone.val(this.model.get('timezone'))
            this.ui.user_status.val((this.model.get('active') == true ? 1 : 0));
            this.ui.user_suspend.prop('checked', (this.model.get('suspended') == true));
            this.ui.role_select.val(this.model.get('rolename'));
            this.ui.package_select.val(this.model.get('package'));
            this.ui.user_add_btn.html('Save');
            this.ui.selectpicker.selectpicker();
        },

        changeValue: function(){
            var equal,
            oldData = {
                'email'           : this.model.get('email'),
                'active'          : this.model.get('active'),
                'suspended'       : this.model.get('suspended'),
                'rolename'        : this.model.get('rolename'),
                'package'         : this.model.get('package'),
                'first_name'      : this.model.get('first_name'),
                'last_name'       : this.model.get('last_name'),
                'middle_initials' : this.model.get('middle_initials'),
                'password'        : '',
                'timezone'        : this.model.get('timezone').split(' (', 1)[0],
            },
            newData = {
                'email'           : this.ui.email.val(),
                'active'          : (this.ui.user_status.val() == 1),
                'suspended'       : this.ui.user_suspend.prop('checked'),
                'rolename'        : this.ui.role_select.val(),
                'package'         : this.ui.package_select.val(),
                'first_name'      : this.ui.first_name.val(),
                'last_name'       : this.ui.last_name.val(),
                'middle_initials' : this.ui.middle_initials.val(),
                'password'        : this.ui.password.val(),
                'timezone'        : this.ui.timezone.val().split(' (', 1)[0],
            };

            equal = _.isEqual(oldData, newData)
            equal === false ? this.ui.user_add_btn.show() : this.ui.user_add_btn.hide();
        },

        onSave: function(){
            var that = this;
            App.getUserCollection().done(function(userCollection){
                var data = {
                    'email'           : that.ui.email.val(),
                    'active'          : (that.ui.user_status.val() == 1),
                    'suspended'       : that.ui.user_suspend.prop('checked'),
                    'rolename'        : that.ui.role_select.val(),
                    'package'         : that.ui.package_select.val(),
                    'first_name'      : that.ui.first_name.val(),
                    'last_name'       : that.ui.last_name.val(),
                    'middle_initials' : that.ui.middle_initials.val(),
                    'timezone'        : that.ui.timezone.val(),
                };

                var existsEmail = false,
                    users = userCollection.models,
                    pattern = /^("\S+"|[a-z0-9_\.+-]+)@(([a-z0-9-]+\.)+[a-z0-9-]+|\[[a-f0-9:\.]+\])$/i,
                    patternLatin = /^[A-Z0-9](?:[A-Z0-9_-]*[A-Z0-9])?$/i;

                    if (that.model.get('email') !== that.ui.email.val()){
                        _.each(users, function(user){
                            if (user.get('email') == that.ui.email.val()) existsEmail = true;
                        });
                    }

                switch (true) {
                /* first name */
                case that.ui.first_name.val().length >= 26:
                    utils.scrollTo(that.ui.first_name);
                    that.ui.first_name.addClass('error');
                    that.ui.first_name.notify("Maximum length should be 25 symbols");
                    break;
                /* last name */
                case that.ui.last_name.val().length >= 26:
                    utils.scrollTo(that.ui.last_name);
                    that.ui.last_name.addClass('error');
                    that.ui.last_name.notify("Maximum length should be 25 symbols");
                    break;
                /* middle initials */
                case that.ui.middle_initials.val().length >= 26:
                    utils.scrollTo(that.ui.middle_initials);
                    that.ui.middle_initials.addClass('error');
                    that.ui.middle_initials.notify("Maximum length should be 25 symbols");
                    break;
                /* password */
                case that.ui.password.val() || (that.ui.password.val() !== that.ui.password_again.val()):
                    utils.scrollTo(that.ui.password);
                    that.ui.password.addClass('error');
                    that.ui.password_again.addClass('error');
                    that.ui.password_again.notify("Empty password or don't match");
                    break;
                case that.ui.password.val().length >= 26:
                    utils.scrollTo(that.ui.password);
                    that.ui.password.addClass('error');
                    that.ui.password_again.addClass('error');
                    that.ui.password_again.notify("Maximum length should be 25 symbols");
                    break;
                /* email */
                case that.ui.email.val() == '':
                    utils.scrollTo(that.ui.email);
                    that.ui.email.addClass('error');
                    that.ui.email.notify("Empty E-mail");
                    break;
                case that.ui.email.val() !== '' && !pattern.test(that.ui.email.val()):
                    utils.scrollTo(that.ui.email);
                    that.ui.email.addClass('error');
                    that.ui.email.notify("E-mail must be correct");
                    break;
                case that.ui.email.val().length >= 51:
                    utils.scrollTo(that.ui.email);
                    that.ui.email.addClass('error');
                    that.ui.email.addClass('error');
                    that.ui.email.notify("Maximum length should be 50 symbols");
                    break;
                case existsEmail && that.ui.email.val() !== '':
                    utils.scrollTo(that.ui.email);
                    that.ui.email.notify('Email should be unique');
                    that.ui.email.addClass('error');
                    break;
                /* timezone */
                case that.ui.timezone.val() == '':
                    utils.scrollTo(that.ui.timezone);
                    that.ui.timezone.addClass('error');
                    that.ui.timezone.notify("Empty Timezone");
                    break;
                default:
                    if (that.ui.password.val())  // update only if specified
                        data.password = that.ui.password.val();

                    that.model.save(data, {wait: true, patch: true})
                        .fail(utils.notifyWindow)
                        .done(function(){
                            App.navigate('users/profile/' + that.model.id + '/general',
                                         {trigger: true});
                            utils.notifyWindow(
                                'Changes to user "' + that.model.get('username') +
                                    '" saved successfully',
                                'success');
                        });
                }
            });
        },

        back: function(){
            App.navigate('users', {trigger: true});
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

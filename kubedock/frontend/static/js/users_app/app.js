define(['marionette', 'paginator', 'utils'],
       function (Marionette, PageableCollection, utils) {

    var UsersApp = new Marionette.Application({
        regions: {
            contents: '#contents'
        }
    });

    UsersApp.module('Data', function(Data, App, Backbone, Marionette, $, _){
        Data.UserModel = utils.BaseModel.extend({
            urlRoot: '/api/users/full'
        });
        Data.UsersCollection = Backbone.Collection.extend({
            url: '/api/users/full',
            model: Data.UserModel
        });

        Data.UserActivitiesModel = utils.BaseModel.extend({
            urlRoot: '/api/users/a/:id'
        });

        Data.UsersPageableCollection = PageableCollection.extend({
            url: '/api/users/full',
            model: Data.UserModel,
            parse: utils.unwrapper,
            mode: 'client',
            state: {
                pageSize: 100
            }
        });

        Data.ActivitiesCollection = PageableCollection.extend({
            url: '/api/users/a/:id',
            model: Data.UserActivitiesModel,
            parse: utils.unwrapper,
            mode: 'client',
            state: {
                pageSize: 100
            }
        });
    });

    UsersApp.module('Views', function(Views, App, Backbone, Marionette, $, _){

        //=================Copy from app.js ====================================
        Views.PaginatorView = Backbone.Marionette.ItemView.extend({
            template: '#paginator-template',
            initialize: function(options) {
                this.model = new Backbone.Model({
                    v: options.view,
                    c: options.view.collection
                });
                this.listenTo(options.view.collection, 'remove', this.render);
                this.listenTo(options.view.collection, 'reset', this.render);
            },
            events: {
                'click li.pseudo-link' : 'paginateIt'
            },
            paginateIt: function(evt){
                evt.stopPropagation();
                var tgt = $(evt.target);
                if (tgt.hasClass('paginatorFirst')) this.model.get('c').getFirstPage();
                else if (tgt.hasClass('paginatorPrev')) this.model.get('c').getPreviousPage();
                else if (tgt.hasClass('paginatorNext')) this.model.get('c').getNextPage();
                else if (tgt.hasClass('paginatorLast')) this.model.get('c').getLastPage();
                this.render();
            }
        });
        //======================================================================

        Views.UserItem = Backbone.Marionette.ItemView.extend({
            template : '#user-item-template',
            tagName  : 'tr',

            ui: {
                'remove_user'    : '.deleteUser',
                'block_user'     : '.blockUser',
                'activated_user' : '.activeteUser',
                'profileUser'    : '.profileUser'
            },

            events: {
                'click @ui.profileUser'    : 'profileUser_btn',
                'click @ui.remove_user'    : 'removeUser',
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

            removeUser: function(){
                var that = this,
                    preloader = $('#page-preloader');
                utils.modalDialogDelete({
                    title: "Delete " + this.model.get('username') + "?",
                    body: "Are you sure want to delete user '" +
                        this.model.get('username') + "'?",
                    small: true,
                    show: true,
                    footer: {
                        buttonOk: function(){
                            preloader.show();
                            that.model.destroy({
                                wait:true,
                                success: function(){
                                    preloader.hide();
                                },
                                error: function(){
                                    preloader.hide();
                                }
                            });
                        },
                        buttonCancel: true
                    }
                });
            },

            blockUser: function(){
                var that = this,
                    preloader = $('#page-preloader');
                utils.modalDialog({
                    title: "Block " + this.model.get('username'),
                    body: "Are you sure want to block user '" +
                        this.model.get('username') + "'?",
                    small: true,
                    show: true,
                    footer: {
                        buttonOk: function(){
                            preloader.show();
                            that.model.save({
                                active: false
                            },{
                                wait: true,
                                patch: true,
                                success: function(){
                                    preloader.hide();
                                    that.render();
                                },
                                error: function(model, response){
                                    preloader.hide();
                                    utils.notifyWindow(response.statusText);
                                }
                            });
                        },
                        buttonCancel: true
                    }
                });
            },

            activatedUser: function(){
                var that = this;
                this.model.save({
                        active: true
                    },{
                        wait: true,
                        patch: true,
                        success: function(){
                            that.render();
                        }
                    });
            },

            profileUser_btn: function(){
                App.router.navigate('/profile/' + this.model.id + '/general/', {trigger: true});
            },

            checkUser: function(){
                this.$el.toggleClass('checked').siblings().removeClass('checked');
            }
        });

        Views.OnlineUserItem = Marionette.ItemView.extend({
            template : '#online-user-item-template',
            tagName  : 'tr',

            ui: {
                'userActivityHistory' : "button.userActivityHistory"
            },

            events: {
                'click @ui.userActivityHistory' : 'userActivityHistory_btn'
            },

            userActivityHistory_btn: function(){
                App.router.navigate('/online/' + this.model.id + '/', {trigger: true});
            }
        });

        Views.ActivityItem = Marionette.ItemView.extend({
            template : '#activity-item-template',
            tagName  : 'tr'
        });

        Views.UsersListView = Backbone.Marionette.CompositeView.extend({
            template           : '#users-list-template',
            childView          : Views.UserItem,
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
                this.fakeCollection = this.collection.fullCollection.clone();

                this.listenTo(this.collection, 'reset', function (col, options) {
                    options = _.extend({ reindex: true }, options || {});
                    if(options.reindex && options.from == null && options.to == null) {
                        this.fakeCollection.reset(col.models);
                    }
                });
                this.counter = 1;
            },

            toggleSort: function(e) {
                var target = $(e.target),
                    targetClass = target.attr('class');

                this.collection.setSorting(targetClass, this.counter);
                this.collection.fullCollection.sort();
                this.counter = this.counter * (-1)
                target.find('.caret').toggleClass('rotate').parent()
                      .siblings().find('.caret').removeClass('rotate');
            },

            filter: function() {
                var value = this.ui.user_search[0].value,
                    valueLength = value.length;

                if (valueLength >= 2){
                    this.collection.fullCollection.reset(_.filter(this.fakeCollection.models, function(e) {
                        if(e.get('username').indexOf( value || '') >= 0) return e
                    }), { reindex: false });
                } else{
                    this.collection.fullCollection.reset(this.fakeCollection.models, { reindex: false});
                }
                this.collection.getFirstPage();
            },

            editSelectedUser: function(e){
                _.each(this.collection.models,function(entry){
                    if (entry.get('checked')){
                        App.router.navigate('/edit/' + entry.id + '/', {trigger: true});
                        return true;
                    }
                });
                e.stopPropagation();
            },

            showSearch: function(){
                this.ui.navSearch.addClass('active');
                this.ui.user_search.focus();
            },

            closeSearch: function(){
                this.ui.navSearch.removeClass('active');
            },

            createUser: function(){
                App.router.navigate('/create/', {trigger: true});
            },

            activity: function(){
                App.router.navigate('/activity/', {trigger: true});
            },

            online: function(){
                App.router.navigate('/online/', {trigger: true});
            }
        });

        Views.OnlineUsersListView = Marionette.CompositeView.extend({
            template           : '#online-users-list-template',
            childView          : Views.OnlineUserItem,
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
                App.router.navigate('/', {trigger: true});
            },

            activity: function(){
                App.router.navigate('/activity/', {trigger: true});
            }
        });

        Views.UsersActivityView = Marionette.CompositeView.extend({
            template           : '#users-activities-template',
            childView          : Views.ActivityItem,
            childViewContainer : "tbody",
        });

        Views.AllUsersActivitiesView = Backbone.Marionette.ItemView.extend({
            template: '#all-users-activities-template',

            ui: {
                'dateFrom'   : 'input#dateFrom',
                'dateTo'     : 'input#dateTo',
                'usersList'  : 'ul#users-list',
                'tbody'      : '#users-activities-table',
                'users_page' : '#users-page, .usersPage',
                'username'   : '#username',
            },

            events: {
                'change input.user-activity' : 'getUsersActivities',
                'change input#dateFrom'      : 'getUsersActivities',
                'change input#dateTo'        : 'getUsersActivities',
                'click @ui.users_page'       : 'back'
            },

            _getActivities: function(username, dateFrom, dateTo){
                var that = this,
                    preloader = $('#page-preloader');

                preloader.show();
                $.ajax({
                    url: '/api/users/a/' + username,
                    data: {date_from: dateFrom, date_to: dateTo},
                    dataType: 'JSON',
                    success: function(rs){
                        console.log(rs)
                        preloader.hide();
                        if(rs.data){
                            that.ui.tbody.empty();
                            if(rs.data.length == 0){
                                that.ui.tbody.append($('<tr>').append(
                                    '<td colspan="5" align="center" class="disabled-color-text">Nothing found</td>'
                                ));
                            } else {
                                $.each(rs.data, function (i, itm) {
                                    that.ui.tbody.append($('<tr>').append(
                                       // '<td>' + itm.username + '</td>' +
                                       // '<td>' + itm.email + '</td>' +
                                       // '<td>' + itm.rolename + '</td>' +
                                        '<td>' + itm.ts + '</td>' +
                                        '<td>' + itm.action + '</td>'
                                       // '<td>' + itm.ts + '</td>'
                                    ));
                                })
                            }
                        }
                    },
                    error: function(){
                        preloader.hide();
                    }
                });
            },

            onRender: function(){
                var that = this;
                // Init datepicker
                this.ui.dateFrom.datepicker({dateFormat: "yy-mm-dd"});
                this.ui.dateTo.datepicker({dateFormat: "yy-mm-dd"});
                // Set default date
                var now = utils.dateYYYYMMDD();
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
                            success: function(rs){
                                process(rs.data);
                            }
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
               App.router.navigate('/', {trigger: true});
            }
        });

        Views.UserCreateView = Backbone.Marionette.ItemView.extend({
            template : '#user-create-template',
            tagName  : 'div',

            ui: {
                'username'        : 'input#username',
                'first_name'      : 'input#firstname',
                'last_name'       : 'input#lastname',
                'middle_initials' : 'input#middle_initials',
                'password'        : 'input#password',
                'password_again'  : 'input#password-again',
                'email'           : 'input#email',
                'user_status'     : 'select#status-select',
                'role_select'     : 'select#role-select',
                'package_select'  : 'select#package-select',
                'users_page'      : 'div#users-page',
                'user_add_btn'    : 'button#user-add-btn',
                'user_cancel_btn' : 'button#user-cancel-btn',
                'selectpicker'    : '.selectpicker',
                'input'           : 'input'
            },

            events: {
                'click @ui.users_page'      : 'back',
                'click @ui.user_cancel_btn' : 'back',
                'click @ui.user_add_btn'    : 'onSave',
                'focus @ui.input'           : 'removeError',
                'keyup @ui.input'           : 'changeValue',
                'change @ui.selectpicker'   : 'changeValue'
            },

            onRender: function(){
                this.ui.selectpicker.selectpicker();
            },

            onSave: function(){
                var that = this,
                    users = App.Data.users.models,
                    existsUsername = false,
                    existsEmail = false,
                    preloader = $('#page-preloader'),
                    username = this.ui.username.val(),
                    pattern = /^("\S+"|[a-z0-9_\.+-]+)@(([a-z0-9-]+\.)+[a-z0-9-]+|\[[a-f0-9:\.]+\])$/i,
                    patternLatin = /^[A-Z0-9](?:[A-Z0-9_-]*[A-Z0-9])?$/i;

                _.each(users, function(user){
                    if (user.get('username') == that.ui.username.val()) existsUsername = true;
                    if (user.get('email') == that.ui.email.val()) existsEmail = true;
                });

                switch (true)
                {
                /* username */
                case this.ui.username.val() == '':
                    utils.scrollTo(this.ui.username);
                    this.ui.username.notify("Empty username");
                    this.ui.username.addClass('error');
                    break;
                case this.ui.username.val().length >= 26:
                    utils.scrollTo(this.ui.username);
                    this.ui.username.notify("Maximum length should be 25 symbols");
                    this.ui.username.addClass('error');
                    break;
                case !patternLatin.test(this.ui.username.val()):
                    utils.scrollTo(this.ui.username);
                    this.ui.username.notify("Username should contain letters of Latin alphabet only");
                    this.ui.username.addClass('error');
                    break;
                case existsUsername:
                    utils.scrollTo(this.ui.username);
                    this.ui.username.notify('Username should be unique');
                    this.ui.username.addClass('error');
                    break;
                /* first name */
                case this.ui.first_name.val().length >= 26:
                    utils.scrollTo(this.ui.first_name);
                    this.ui.first_name.addClass('error');
                    this.ui.first_name.notify("Maximum length should be 25 symbols");
                    break;
                case !patternLatin.test(this.ui.first_name.val()) && this.ui.first_name.val() !== '':
                    utils.scrollTo(this.ui.first_name);
                    this.ui.first_name.notify("Username should contain letters of Latin alphabet only");
                    this.ui.first_name.addClass('error');
                    break;
                /* last name */
                case this.ui.last_name.val().length >= 26:
                    utils.scrollTo(this.ui.last_name);
                    this.ui.last_name.addClass('error');
                    this.ui.last_name.notify("Maximum length should be 25 symbols");
                    break;
                case !patternLatin.test(this.ui.last_name.val()) && this.ui.last_name.val() !== '':
                    utils.scrollTo(this.ui.last_name);
                    this.ui.last_name.notify("Username should contain letters of Latin alphabet only");
                    this.ui.last_name.addClass('error');
                    break;
                /* middle initials */
                case this.ui.middle_initials.val().length >= 26:
                    utils.scrollTo(this.ui.middle_initials);
                    this.ui.middle_initials.addClass('error');
                    this.ui.middle_initials.notify("Maximum length should be 25 symbols");
                    break;
                case !patternLatin.test(this.ui.middle_initials.val()) && this.ui.middle_initials.val() !== '':
                    utils.scrollTo(this.ui.middle_initials);
                    this.ui.middle_initials.notify("Username should contain letters of Latin alphabet only");
                    this.ui.middle_initials.addClass('error');
                    break;
                /* password */
                case !this.ui.password.val() || (this.ui.password.val() !== this.ui.password_again.val()):
                    utils.scrollTo(this.ui.password);
                    this.ui.password.addClass('error');
                    this.ui.password_again.addClass('error');
                    this.ui.password_again.notify("Empty password or don't match");
                    break;
                case this.ui.password.val().length >= 26:
                    utils.scrollTo(this.ui.password);
                    this.ui.password.addClass('error');
                    this.ui.password_again.addClass('error');
                    this.ui.password_again.notify("Maximum length should be 25 symbols");
                    break;
                /* email */
                case this.ui.email.val() == '':
                    utils.scrollTo(this.ui.email);
                    this.ui.email.addClass('error');
                    this.ui.email.notify("Empty E-mail");
                    break;
                case this.ui.email.val() !== '' && !pattern.test(this.ui.email.val()):
                    utils.scrollTo(this.ui.email);
                    this.ui.email.addClass('error');
                    this.ui.email.notify("E-mail must be correct");
                    break;
                case this.ui.email.val().length >= 51:
                    utils.scrollTo(this.ui.email);
                    this.ui.email.addClass('error');
                    this.ui.email.addClass('error');
                    this.ui.email.notify("Maximum length should be 50 symbols");
                    break;
                case existsEmail && this.ui.email.val() !== '':
                    utils.scrollTo(this.ui.email);
                    this.ui.email.notify('Email should be unique');
                    this.ui.email.addClass('error');
                    break;
                default:
                    preloader.show();
                    App.Data.users.create({
                        'username'        : username,
                        'first_name'      : this.ui.first_name.val(),
                        'last_name'       : this.ui.last_name.val(),
                        'middle_initials' : this.ui.middle_initials.val(),
                        'password'        : this.ui.password.val(),
                        'email'           : this.ui.email.val(),
                        'active'          : (this.ui.user_status.val() == 1 ? true : false),
                        'rolename'        : this.ui.role_select.val(),
                        'package'         : this.ui.package_select.val(),
                    }, {
                        wait: true,
                        success: function(){
                            preloader.hide();
                            App.router.navigate('/', {trigger: true})
                            $.notify('User "' + username + '" created successfully', {
                                autoHideDelay: 4000,
                                globalPosition: 'bottom left',
                                className: 'success'
                            });
                        },
                        error: function(model, response){
                            preloader.hide();
                            utils.notifyWindow(response.statusText);
                        }
                    });
                }
            },

            removeError: function(evt){
                var target = $(evt.target);
                if (target.hasClass('error')) target.removeClass('error');
            },

            back: function(){
               App.router.navigate('/', {trigger: true});
            },
        });

        Views.UserProfileViewLogHistory = Views.UserCreateView.extend({
            template : '#user-profile-log-history-template',
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
                var that = this,
                    preloader = $('#page-preloader');

                preloader.show();
                $.ajax({
                    url: '/api/users/logHistory',
                    data: {'uid': this.model.get('id')},
                    success: function(rs){
                        if (rs.data.length != 0){
                            _.each(rs.data, function(itm){
                                that.ui.tb.append($('<tr>').append(
                                    '<td>' + itm[0] + '</td>' +
                                    '<td>' + utils.toHHMMSS(itm[1]) + '</td>' +
                                    '<td>' + itm[2] + '</td>' +
                                    '<td>' + itm[3] + '</td>'
                                ))
                            });
                            preloader.hide();
                        } else {
                            that.ui.tb.append($('<tr>').append('<td colspan="4" class="text-center">There is no login history for this user</td>'));
                            preloader.hide();
                        }
                    }
                });
            },

            login_this_user: function(){
                var that = this,
                    preloader = $('#page-preloader');
                utils.modalDialog({
                    title: "Authorize by " + this.model.get('username'),
                    body: "Are you sure want to authorize by user '" +
                        this.model.get('username') + "'?",
                    small: true,
                    show: true,
                    footer: {
                        buttonOk: function(){
                            preloader.show();
                            $.ajax({
                                url: '/api/users/loginA',
                                type: 'POST',
                                data: {user_id: that.model.id},
                                dataType: 'JSON',
                                success: function(rs){
                                    if(rs.status == 'OK')
                                        window.location.href = '/';
                                    preloader.hide();
                                },
                                error: function(){
                                    preloader.hide();
                                }
                            });
                        },
                        buttonCancel: true
                    }
                });
            },

            delete_user: function(){
                var that = this,
                    preloader = $('#page-preloader');
                utils.modalDialogDelete({
                    title: "Delete " + this.model.get('username') + "?",
                    body: "Are you sure want to delete user '" +
                        this.model.get('username') + "'?",
                    small: true,
                    show: true,
                    footer: {
                        buttonOk: function(){
                            preloader.show();
                            that.model.destroy({
                                wait:true,
                                success: function(){
                                    preloader.hide();
                                    App.router.navigate('/', {trigger: true});
                                },
                                error: function(){
                                    preloader.hide();
                                }
                            });
                        },
                        buttonCancel: true
                    }
                });
            },

            edit_user: function(){
                App.router.navigate('/edit/' + this.model.id + '/', {trigger: true});
            },

            generalTab: function(){
                App.router.navigate('/profile/' + this.model.id + '/general/', {trigger: true});
            },

            back: function(){
                App.router.navigate('/', {trigger: true});
            }
        });

        Views.UserProfileView = Backbone.Marionette.ItemView.extend({
            template : '#user-profile-template',
            tagName  : 'div',

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
                    join_date: join_date ? join_date : '',
                    last_login: last_login ? last_login : '',
                    last_activity: last_activity ? last_activity : '',
                    pods: pods ? pods : [],
                    'kubeTypes': kubeTypes,
                    'kubes': kubesCount,
                    toHHMMSS: utils.toHHMMSS
                }
            },

            login_this_user: function(){
                var that = this,
                    preloader = $('#page-preloader');
                utils.modalDialog({
                    title: "Authorize by " + this.model.get('username'),
                    body: "Are you sure want to authorize by user '" +
                        this.model.get('username') + "'?",
                    small: true,
                    show: true,
                    footer: {
                        buttonOk: function(){
                            preloader.show();
                            $.ajax({
                                url: '/api/users/loginA',
                                type: 'POST',
                                data: {user_id: that.model.id},
                                dataType: 'JSON',
                                success: function(rs){
                                    if(rs.status == 'OK')
                                        window.location.href = '/';
                                    preloader.hide();
                                },
                                error: function(){
                                    preloader.hide();
                                }
                            });
                        },
                        buttonCancel: true
                    }
                });
            },

            delete_user: function(){
                var that = this,
                    preloader = $('#page-preloader');
                utils.modalDialogDelete({
                    title: "Delete " + this.model.get('username') + "?",
                    body: "Are you sure want to delete user '" +
                        this.model.get('username') + "'?",
                    small: true,
                    show: true,
                    footer: {
                        buttonOk: function(){
                            preloader.show();
                            that.model.destroy({
                                wait:true,
                                success: function(){
                                    preloader.hide();
                                    App.router.navigate('/', {trigger: true});
                                },
                                error: function(){
                                    preloader.hide();
                                }
                            });
                        },
                        buttonCancel: true
                    }
                });
            },

            edit_user: function(){
                App.router.navigate('/edit/' + this.model.id + '/', {trigger: true});
            },

            back: function(){
               App.router.navigate('/', {trigger: true});
            },

            logHistory: function(){
               App.router.navigate('/profile/' + this.model.id + '/logHistory/', {trigger: true});
            }
        });

        Views.UsersEditView = Views.UserCreateView.extend({     // inherit
            onRender: function(){
                this.ui.first_name.val(this.model.get('first_name'));
                this.ui.last_name.val(this.model.get('last_name'));
                this.ui.middle_initials.val(this.model.get('middle_initials'))
                this.ui.email.val(this.model.get('email'));
                this.ui.user_status.val((this.model.get('active') == true ? 1 : 0));
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
                    'rolename'        : this.model.get('rolename'),
                    'package'         : this.model.get('package'),
                    'first_name'      : this.model.get('first_name'),
                    'last_name'       : this.model.get('last_name'),
                    'middle_initials' : this.model.get('middle_initials'),
                    'password'        : '',
                },
                newData = {
                    'email'           : this.ui.email.val(),
                    'active'          : (this.ui.user_status.val() == 1 ? true : false),
                    'rolename'        : this.ui.role_select.val(),
                    'package'         : this.ui.package_select.val(),
                    'first_name'      : this.ui.first_name.val(),
                    'last_name'       : this.ui.last_name.val(),
                    'middle_initials' : this.ui.middle_initials.val(),
                    'password'        : this.ui.password.val(),
                };

                equal = _.isEqual(oldData, newData)
                equal === false ? this.ui.user_add_btn.show() : this.ui.user_add_btn.hide();
            },

            onSave: function(){
                // temp validation
                var data = {
                    'email'           : this.ui.email.val(),
                    'active'          : (this.ui.user_status.val() == 1 ? true : false),
                    'rolename'        : this.ui.role_select.val(),
                    'package'         : this.ui.package_select.val(),
                    'first_name'      : this.ui.first_name.val(),
                    'last_name'       : this.ui.last_name.val(),
                    'middle_initials' : this.ui.middle_initials.val()
                };

                var that = this,
                    existsEmail = false,
                    users = App.Data.users.models,
                    pattern = /^("\S+"|[a-z0-9_\.+-]+)@(([a-z0-9-]+\.)+[a-z0-9-]+|\[[a-f0-9:\.]+\])$/i,
                    patternLatin = /^[A-Z0-9](?:[A-Z0-9_-]*[A-Z0-9])?$/i;

                    if (this.model.get('email') !== that.ui.email.val()){
                        _.each(users, function(user){
                            if (user.get('email') == that.ui.email.val()) existsEmail = true;
                        });
                    }

                switch (true)
                {
                /* first name */
                case this.ui.first_name.val().length >= 26:
                    utils.scrollTo(this.ui.first_name);
                    this.ui.first_name.addClass('error');
                    this.ui.first_name.notify("Maximum length should be 25 symbols");
                    break;
                case !patternLatin.test(this.ui.first_name.val()) && this.ui.first_name.val() !== '':
                    utils.scrollTo(this.ui.first_name);
                    this.ui.first_name.notify("Username should contain letters of Latin alphabet only");
                    this.ui.first_name.addClass('error');
                    break;
                /* last name */
                case this.ui.last_name.val().length >= 26:
                    utils.scrollTo(this.ui.last_name);
                    this.ui.last_name.addClass('error');
                    this.ui.last_name.notify("Maximum length should be 25 symbols");
                    break;
                case !patternLatin.test(this.ui.last_name.val()) && this.ui.last_name.val() !== '':
                    utils.scrollTo(this.ui.last_name);
                    this.ui.last_name.notify("Username should contain letters of Latin alphabet only");
                    this.ui.last_name.addClass('error');
                    break;
                /* middle initials */
                case this.ui.middle_initials.val().length >= 26:
                    utils.scrollTo(this.ui.middle_initials);
                    this.ui.middle_initials.addClass('error');
                    this.ui.middle_initials.notify("Maximum length should be 25 symbols");
                    break;
                case !patternLatin.test(this.ui.middle_initials.val()) && this.ui.middle_initials.val() !== '':
                    utils.scrollTo(this.ui.middle_initials);
                    this.ui.middle_initials.notify("Username should contain letters of Latin alphabet only");
                    this.ui.middle_initials.addClass('error');
                    break;
                /* password */
                case this.ui.password.val() || (this.ui.password.val() !== this.ui.password_again.val()):
                    utils.scrollTo(this.ui.password);
                    this.ui.password.addClass('error');
                    this.ui.password_again.addClass('error');
                    this.ui.password_again.notify("Empty password or don't match");
                    break;
                case this.ui.password.val().length >= 26:
                    utils.scrollTo(this.ui.password);
                    this.ui.password.addClass('error');
                    this.ui.password_again.addClass('error');
                    this.ui.password_again.notify("Maximum length should be 25 symbols");
                    break;
                /* email */
                case this.ui.email.val() == '':
                    utils.scrollTo(this.ui.email);
                    this.ui.email.addClass('error');
                    this.ui.email.notify("Empty E-mail");
                    break;
                case this.ui.email.val() !== '' && !pattern.test(this.ui.email.val()):
                    utils.scrollTo(this.ui.email);
                    this.ui.email.addClass('error');
                    this.ui.email.notify("E-mail must be correct");
                    break;
                case this.ui.email.val().length >= 51:
                    utils.scrollTo(this.ui.email);
                    this.ui.email.addClass('error');
                    this.ui.email.addClass('error');
                    this.ui.email.notify("Maximum length should be 50 symbols");
                    break;
                case existsEmail && this.ui.email.val() !== '':
                    utils.scrollTo(this.ui.email);
                    this.ui.email.notify('Email should be unique');
                    this.ui.email.addClass('error');
                    break;
                default:
                    if (this.ui.password.val())  // update only if specified
                        data.password = this.ui.password.val();
                    this.model.set(data);

                    this.model.save(this.model.changedAttributes(), {
                        wait: true,
                        patch: true,
                        success: function(model){
                            App.router.navigate('/profile/' + model.id + '/general/', {trigger: true});
                            $.notify( "Changes to user '" + model.get('username') + "' saved successfully", {
                                autoHideDelay: 4000,
                                globalPosition: 'bottom left',
                                className: 'success'
                            });
                        },
                        error: function(model){
                            model.set(model.previousAttributes());
                        }
                    });
                }
            },

            back: function(){
                App.router.navigate('/profile/' + this.model.id + '/general/', {trigger: true});
            },
        });

        Views.UsersLayout = Marionette.LayoutView.extend({
            template : '#users-layout-template',
            regions  : {
                main  : 'div#main',
                pager : 'div#pager'
            }
        });
    });


    UsersApp.module('UsersCRUD', function(UsersCRUD, App, Backbone, Marionette, $, _){

        UsersCRUD.Controller = Marionette.Controller.extend({
            showOnlineUsers: function(){
                var layout_view = new App.Views.UsersLayout(),
                    online_users_list_view = new App.Views.OnlineUsersListView({
                        collection: App.Data.onlineUsers
                    }),
                    user_list_pager = new App.Views.PaginatorView({
                        view: online_users_list_view
                    });

                this.listenTo(layout_view, 'show', function(){
                    layout_view.main.show(online_users_list_view);
                    layout_view.pager.show(user_list_pager);
                });
                App.contents.show(layout_view);
            },
            showUserActivity: function(user_id){
                var that = this,
                    layout_view = new App.Views.UsersLayout();

                $.ajax({
                    'url': '/api/users/a/' + user_id,
                    success: function(rs){
                        UsersApp.Data.activities = new UsersApp.Data.ActivitiesCollection(rs.data);
                        var activities_view = new App.Views.UsersActivityView({
                                collection: UsersApp.Data.activities
                            }),
                            activities_list_pager = new App.Views.PaginatorView({
                                view: activities_view
                            });

                        that.listenTo(layout_view, 'show', function(){
                            layout_view.main.show(activities_view);
                            layout_view.pager.show(activities_list_pager);
                        });
                        App.contents.show(layout_view);
                    }
                });
            },
            showUsers: function(){
                var layout_view = new App.Views.UsersLayout(),
                    users_list_view = new App.Views.UsersListView({
                        collection: UsersApp.Data.users
                    }),
                    user_list_pager = new App.Views.PaginatorView({
                        view: users_list_view
                    });

                this.listenTo(layout_view, 'show', function(){
                    layout_view.main.show(users_list_view);
                    layout_view.pager.show(user_list_pager);
                });
                App.contents.show(layout_view);
            },
            showAllUsersActivity: function(){
                var layout_view = new App.Views.UsersLayout(),
                    users_activities_view = new App.Views.AllUsersActivitiesView();

                this.listenTo(layout_view, 'show', function(){
                    layout_view.main.show(users_activities_view);
                });
                App.contents.show(layout_view);
            },
            showCreateUser: function(){
                var layout_view = new App.Views.UsersLayout(),
                    user_create_view = new App.Views.UserCreateView();

                this.listenTo(layout_view, 'show', function(){
                    layout_view.main.show(user_create_view);
                });

                App.contents.show(layout_view);
            },
            showEditUser: function(user_id){
                var layout_view = new App.Views.UsersLayout(),
                    user_edit_view = new App.Views.UsersEditView({
                        model: App.Data.users.get(parseInt(user_id))
                    });

                this.listenTo(layout_view, 'show', function () {
                    layout_view.main.show(user_edit_view);
                    $('#pager').hide();
                    $('#user-header h2').text('Edit');

                });
                App.contents.show(layout_view);
            },
            showProfileUser: function(user_id){
                var layout_view = new App.Views.UsersLayout(),
                    user_model = App.Data.users.fullCollection.get(parseInt(user_id)),
                    user_profile_view = new App.Views.UserProfileView({
                        model: user_model
                    });

                this.listenTo(layout_view, 'show', function () {
                    layout_view.main.show(user_profile_view);
                });
                App.contents.show(layout_view);
            },
            showProfileUserLogHistory: function(user_id){
                var layout_view = new App.Views.UsersLayout(),
                    user_model = App.Data.users.fullCollection.get(parseInt(user_id)),
                    user_profile_view_log_history = new App.Views.UserProfileViewLogHistory({
                        model: user_model
                    });

                this.listenTo(layout_view, 'show', function () {
                    layout_view.main.show(user_profile_view_log_history);
                });
                App.contents.show(layout_view);
            }
        });

        UsersCRUD.addInitializer(function(){
            var controller = new UsersCRUD.Controller();
            App.router = new Marionette.AppRouter({
                controller: controller,
                appRoutes: {
                    ''                        : 'showUsers',
                    'online/'                 : 'showOnlineUsers',
                    'create/'                 : 'showCreateUser',
                    'edit/:id/'               : 'showEditUser',
                    'activity/'               : 'showAllUsersActivity',
                    'online/:id/'             : 'showUserActivity',
                    'profile/:id/general/'    : 'showProfileUser',
                    'profile/:id/logHistory/' : 'showProfileUserLogHistory',
                }
            });
        });

    });

    UsersApp.on('start', function(){
        if (Backbone.history) {
            Backbone.history.start({root: '/users', pushState: true});
        }
    });
    return UsersApp;
});

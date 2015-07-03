define(['marionette', 'utils'],
       function (Marionette, utils) {

    var SettingsApp = new Marionette.Application({
        regions: {
            contents: '#contents'
        }
    });

    SettingsApp.module('Data', function(Data, App, Backbone, Marionette, $, _){

        Data.CurrentUserModel = utils.BaseModel.extend({
            url: function(){ return '/api/users/editself' }
        });

        Data.PermissionModel = utils.BaseModel.extend({
            urlRoot: '/api/settings/permissions'
        });

        Data.PermissionsCollection = utils.BaseCollection.extend({
            url: '/api/settings/permissions',
            model: Data.PermissionModel
        });

        Data.NotificationModel = utils.BaseModel.extend({
            urlRoot: '/api/settings/notifications'
        });

        Data.NotificationsCollection = utils.BaseCollection.extend({
            url: '/api/settings/notifications',
            model: Data.NotificationModel
        });

        Data.PersistentStorageModel = utils.BaseModel.extend({
            defaults: {
                name   : 'Nameless',
                size   : 0,
                in_use : false,
                pod    : ''
            },
        });

        Data.PersistentStorageCollection = utils.BaseCollection.extend({
            url: '/api/pstorage',
            model: Data.PersistentStorageModel,
        });

        Data.UserAddressModel = utils.BaseModel.extend({
            defaults: {
                pod    : ''
            },
        });

        Data.UserAddressCollection = utils.BaseCollection.extend({
            url: '/api/ippool/userstat',
            model: Data.UserAddressModel,
        });

    });


    SettingsApp.module('Views', function(Views, App, Backbone, Marionette, $, _){

        Views.GeneralView = Marionette.CompositeView.extend({
            template: '#general-settings-template',

            ui: {
                'timezone': '#timezone'
            },

            events: {
                'click [type="submit"]': 'submitSettings'
            },

            onRender: function(){
                var that = this;
                this.ui.timezone.typeahead({
                    autoSelect: false,
                    source: function(query, process){
                        $.ajax({
                            url: '/api/settings/timezone',
                            data: {'s': that.ui.timezone.val()},
                            cache: false,
                            success: function(responce){
                                process(responce.data);
                            }
                        })
                    }
                });
            },

            submitSettings: function(){
                var data = {
                    timezone: this.ui.timezone.val()
                };
                $.ajax({
                    url: '/api/settings/timezone',
                    dataType: 'JSON',
                    data: data,
                    type: 'PUT',
                    cache: false,
                    success: function(rs){
                        if(rs.status == 'OK')
                            $.notify('Settings changed successfully', {
                                autoHideDelay: 10000,
                                globalPosition: 'top center',
                                className: 'success'
                        });
                    }
                })

            }
        });

        Views.NotificationCreateView = Backbone.Marionette.ItemView.extend({
            template: '#notification-create-template',

            ui: {
                'label'      : 'label[for="id_event"]',
                'event'      : 'select#id_event',
                'text_plain' : 'textarea#id_text_plain',
                'text_html'  : 'textarea#id_text_html',
                'as_html'    : 'input#id_as_html',
                'event_keys' : '#event_keys',
                'save'       : 'button#template-add-btn',
                'back'       : 'button#template-back-btn'
            },

            events: {
                'click @ui.save'         : 'onSave',
                'click @ui.back'         : 'back',
                'change select#id_event' : 'onSelectEvent'
            },

            onRender: function() {
                var curEventKeys = eventsKeysList[this.ui.event.val()];
                this.ui.event_keys.html(curEventKeys.join('<br/>'));
                this.ui.event.show();
                this.ui.label.text("Event");
            },

            back: function(){
                App.router.navigate('/notifications/', {trigger: true});
            },

            onSave: function(){
                // temp validation
                App.Data.templates.create({
                    'event': this.ui.event.val(),
                    'text_plain': this.ui.text_plain.val(),
                    'text_html': this.ui.text_html.val(),
                    'as_html': this.ui.as_html.prop('checked')
                }, {
                    wait: true,
                    success: function(){
                        App.router.navigate('/notifications', {trigger: true})
                    }
                });
            },

            onSelectEvent: function(){
                var curEventKeys = eventsKeysList[this.ui.event.val()];
                this.ui.event_keys.html(curEventKeys.join('<br/>'));
            }
        });

        Views.NotificationEditView = Views.NotificationCreateView.extend({

            onRender: function(){
                var curEventKeys = eventsKeysList[this.ui.event.val()];
                this.ui.event_keys.html(curEventKeys.join('<br/>'));
                this.ui.event.hide();
                this.ui.label.text("Event: " + this.model.get('event').name);
                this.ui.text_plain.val(this.model.get('text_plain'));
                this.ui.text_html.val(this.model.get('text_html'));
                this.ui.as_html.prop('checked', this.model.get('as_html'));
            },

            onSave: function(){
                // temp validation
                var data = {
                    'event': this.ui.event.val(),
                    'text_plain': this.ui.text_plain.text(),
                    'text_html': this.ui.text_html.text(),
                    'as_html': this.ui.as_html.prop('checked')
                };

                this.model.set(data);

                this.model.save(undefined, {
                    wait: true,
                    success: function(){
                        App.router.navigate('/notifications', {trigger: true})
                    }
                });
            }

        });

        Views.NotificationItemView = Marionette.ItemView.extend({
            template: '#notification-item-template',

            events: {
                'click span': 'editTemplate'
            },

            onRender: function(){
            },

            editTemplate: function(){
                App.router.navigate('/notifications/edit/' + this.model.id + '/', {trigger: true});
            }
        });

        Views.NotificationsView = Marionette.CompositeView.extend({
            template: '#notifications-settings-template',
            childViewContainer: '#notification-templates',
            childView: Views.NotificationItemView
        });

        /* Public IPs Views */
        Views.PublicIPsItemView = Marionette.ItemView.extend({
            template: '#publicIPs-item-template',
            tagName: 'tr'
        });

        /* Public IPs Views */
        Views.PublicIPsView = Marionette.CompositeView.extend({
            template: '#publicIPs-template',
            childView: Views.PublicIPsItemView,
            childViewContainer: 'tbody',
            initialize: function(){
                console.log(this.collection);
            }
        });

        /* Persistent volumes entry view */
        Views.PersistentVolumesItemView = Marionette.ItemView.extend({
            template: '#persistent-volumes-item-template',
            tagName: 'tr',

            ui: {
                terminate: 'span.terminate-btn'
            },

            events: {
                'click @ui.terminate': 'terminateVolume'
            },

            terminateVolume: function(){
                var that = this;
                if (this.model.get('in_use')) {
                    return;
                }
                this.model.destroy({
                    wait: true,
                    success: function(){that.remove()}
                });
            }
        });

        /* Persistent volumes Views */
        Views.PersistentVolumesView = Marionette.CompositeView.extend({
            template: '#persistent-volumes-template',
            childView: Views.PersistentVolumesItemView,
            childViewContainer: 'tbody'
        });

        /* Profile edit volumes Views */
        Views.ProfileEditView = Backbone.Marionette.ItemView.extend({
            template: '#user-edit-template',

            ui: {
                'first_name'       : 'input#firstname',
                'last_name'        : 'input#lastname',
                'middle_initials'  : 'input#middle_initials',
                'password'         : 'input#password',
                'password_again'   : 'input#password-again',
                'email'            : 'input#email',
                'save'             : 'button#template-save-btn',
                'back'             : 'button#template-back-btn',
                'editBtn'          : '#template-edit-btn',
                'deleteBtn'        : '#template-remove-btn'
            },

            events: {
                'click @ui.back'       : 'back',
                'click @ui.save'       : 'onSave',
                'click @ui.editBtn'    : 'editTemplate',
                'click @ui.deleteBtn'  : 'deleteProfile',
            },

            templateHelpers: function(){
                return {
                    edit: this.model.in_edit,
                    first_name: this.model.get('first_name'),
                    last_name: this.model.get('last_name'),
                    middle_initials: this.model.get('middle_initials'),
                    email: this.model.get('email')
                }
            },

            onRender: function(){
                this.ui.first_name.val(this.model.get('first_name'));
                this.ui.last_name.val(this.model.get('last_name'));
                this.ui.middle_initials.val(this.model.get('middle_initials'));
                this.ui.email.val(this.model.get('email'));
            },

            back: function(){
                this.model.in_edit = false;
                this.render();
            },

            editTemplate: function(){
                this.model.in_edit = true;
                this.render();
            },

            deleteProfile: function(){
                var that = this;
                utils.modalDialogDelete({
                    title: "Terminate account?",
                    body: "Are you sure want to terminate your account ?",
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
            },

            onSave: function(){
                var that = this,
                    data = {
                        'first_name': this.ui.first_name.val(),
                        'last_name': this.ui.last_name.val(),
                        'middle_initials': this.ui.middle_initials.val(),
                        'email': this.ui.email.val()
                    };

                pass1 = this.ui.password.val();
                pass2 = this.ui.password_again.val();
                // temp validation
                if (pass1 != '') {
                    if (pass1 != pass2) {
                        alert("Passwords are not equal");
                        return
                    }
                    data.password = pass1
                }

                this.model.set(data);

                this.model.save(undefined, {
                    wait: true,
                    success: function(){
                        that.model.in_edit = false;
                        that.render();
                    }
                });
            }
        });

        Views.PermissionItemView = Marionette.ItemView.extend({
            template: '#permission-item-template',
            tagName: 'tr',
        });

        Views.PermissionsListView = Marionette.CompositeView.extend({
            template: '#permissions-template',
            childView: Views.PermissionItemView,
            childViewContainer: "tbody",

            ui: {
                permTable: '#permissions-table',
                permToggle: '.perm-toggle'
            },

            events: {
                'change input.perm-toggle': 'togglePerm'
            },

            onRender: function(){
                var that = this,
                    tr = this.ui.permTable.find('thead').append('<tr>')
                        .find('tr').append('<th>');
                $.each(roles, function(id, itm){
                    tr.append($('<th>').text(itm.rolename));
                });
            },

            togglePerm: function(evt){
                var $el = $(evt.target),
                    pid = $el.data('pid'),
                    checked = $el.is(':checked');
                $.ajax({
                    url: '/api/settings/permissions/' + pid,
                    dataType: 'JSON',
                    type: 'PUT',
                    data: {'allow': checked},
                    success: function(rs){
                        $.notify('Permission changed successfully', {
                            autoHideDelay: 10000,
                            globalPosition: 'top right',
                            className: 'success'
                        });
                    }
                });
            }
        });

        Views.SettingsLayout = Marionette.LayoutView.extend({
            template: '#settings-layout-template',
            regions: {
                main: 'div#details_content'
            },

            ui: {
                tabButton : 'ul.nav li',
                general   : 'li.general'
            },

            events: {
                'click @ui.tabButton' : 'changeTab'
            },

            changeTab: function (evt) {
                evt.preventDefault();
                var tgt = $(evt.target);
                if (tgt.hasClass('general')) App.router.navigate('/general/', {trigger: true});
                else if (tgt.hasClass('profile')) App.router.navigate('/profile/', {trigger: true});
                else if (tgt.hasClass('publicIPs')) App.router.navigate('/publicIPs/', {trigger: true});
                else if (tgt.hasClass('permissions')) App.router.navigate('/permissions/', {trigger: true});
                else if (tgt.hasClass('notifications')) App.router.navigate('/notifications/', {trigger: true});
                else if (tgt.hasClass('persistent-volumes')) App.router.navigate('/persistent-volumes/', {trigger: true});
            },

            onRender: function(){
                var href = window.location.pathname.split('/'),
                    tabs = this.ui.tabButton,
                    that = this;

                href = href[href.length - 2];

                _.each(tabs, function(item){
                    if (item.className == href) {
                        $(item).addClass('active');
                    } else if (href == 'settings') {
                        that.ui.general.addClass('active');
                    }
                    else {
                        $(item).removeClass('active')
                    }
                });
            }
        });
    });

    SettingsApp.module('SettingsCRUD', function(
        SettingsCRUD, App, Backbone, Marionette, $, _){

        SettingsCRUD.Controller = Marionette.Controller.extend({
            showSettings: function(){
                var layout_view = new App.Views.SettingsLayout();
                this.listenTo(layout_view, 'show', function(){
                    layout_view.main.show();

                });
                App.contents.show(layout_view);
            },

            showPermissions: function(){
                var layout_view = new App.Views.SettingsLayout();
                var permissions_view = new App.Views.PermissionsListView({
                    collection: SettingsApp.Data.permissions
                });
                this.listenTo(layout_view, 'show', function(){
                    layout_view.main.show(permissions_view);
                });
                App.contents.show(layout_view);
            },

            showNotifications: function(){
                var layout_view = new App.Views.SettingsLayout();
                var notifications_view = new App.Views.NotificationsView({
                    collection: SettingsApp.Data.notifications
                });
                this.listenTo(layout_view, 'show', function(){
                    layout_view.main.show(notifications_view);
                });
                App.contents.show(layout_view);
            },

            addNotifications: function(){
                var layout_view = new App.Views.SettingsLayout();
                var notifications_create_view = new App.Views.NotificationCreateView();
                this.listenTo(layout_view, 'show', function(){
                    layout_view.main.show(notifications_create_view);
                });
                App.contents.show(layout_view);
            },

            editNotifications: function(nid){
                var layout_view = new App.Views.SettingsLayout();
                var notifications_edit_view = new App.Views.NotificationEditView({
                    model: SettingsApp.Data.notifications.get(parseInt(nid))
                });
                this.listenTo(layout_view, 'show', function(){
                    layout_view.main.show(notifications_edit_view);
                });
                App.contents.show(layout_view);
            },

            editProfile: function(){
                var layout_view = new App.Views.SettingsLayout();
                var profile_edit_view = new App.Views.ProfileEditView({
                    model: SettingsApp.Data.this_user
                });
                this.listenTo(layout_view, 'show', function(){
                    layout_view.main.show(profile_edit_view);
                });
                App.contents.show(layout_view);
            },

            showGeneral: function(){
                var layout_view = new App.Views.SettingsLayout();
                var general_view = new App.Views.GeneralView();
                this.listenTo(layout_view, 'show', function(){
                    layout_view.main.show(general_view);
                });
                App.contents.show(layout_view);
            },

            showIPs: function(){
                var layout_view = new App.Views.SettingsLayout(),
                    collection = new App.Data.UserAddressCollection(),
                    public_ips_view = new App.Views.PublicIPsView({
                        collection: collection
                    }),
                    promise = collection.fetch();
                this.listenTo(layout_view, 'show', function(){
                    layout_view.main.show(public_ips_view);
                });
                promise.done(function(data){
                    App.contents.show(layout_view);
                });
            },

            showPersistentVolumes: function(){
                var layout_view = new App.Views.SettingsLayout(),
                    collection = new App.Data.PersistentStorageCollection(),
                    persistent_volumes_view = new App.Views.PersistentVolumesView({
                        collection: collection
                    }),
                    promise = collection.fetch();
                this.listenTo(layout_view, 'show', function(){
                    layout_view.main.show(persistent_volumes_view);
                });
                promise.done(function(data){
                    App.contents.show(layout_view);
                });

            },
        });

        SettingsCRUD.addInitializer(function(){
            var controller = new SettingsCRUD.Controller();
            App.router = new Marionette.AppRouter({
                controller: controller,
                appRoutes: {
                    ''                        : 'showGeneral',
                    'general/'                : 'showGeneral',
                    'profile/'                : 'editProfile',
                    'publicIPs/'              : 'showIPs',
                    'permissions/'            : 'showPermissions',
                    'notifications/'          : 'showNotifications',
                    'notifications/add/'      : 'addNotifications',
                    'persistent-volumes/'     : 'showPersistentVolumes',
                    'notifications/edit/:id/' : 'editNotifications',
                }
            });
        });

    });

    SettingsApp.on('start', function(){
        if (Backbone.history) {
            Backbone.history.start({root: '/settings/', pushState: true});
        }
    });

    return SettingsApp;
});
define(['marionette', 'utils'],
       function (Marionette, utils) {

    var SettingsApp = new Marionette.Application({
        regions: {
            contents: '#contents'
        }
    });

    SettingsApp.module('Data', function(Data, App, Backbone, Marionette, $, _){

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

    });


    SettingsApp.module('Views', function(Views, App, Backbone, Marionette, $, _){

        Views.GeneralView = Marionette.CompositeView.extend({
            template: '#general-settings-template',

            ui: {
                'timezone': '#timezone'
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
                            success: function(rs){
                                process(rs.data);
                            }
                        })
                    },
                    updater: function(v){
                        if(v.length > 3){
                            $.ajax({
                                url: '/api/settings/timezone',
                                dataType: 'JSON',
                                data: {timezone: v},
                                type: 'PUT',
                                cache: false,
                                success: function(rs){
                                    if(rs.status == 'OK')
                                        $.notify('Timezone changed to ' + rs.data, {
                                            autoHideDelay: 10000,
                                            globalPosition: 'top center',
                                            className: 'success'
                                        });
                                }
                            })
                        }
                        return v;
                    }
                });
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
                'back'       : 'button#template-back-btn',
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
                App.router.navigate('/notifications/edit/' + this.model.id + '/',
                                    {trigger: true});
            }
        });

        Views.NotificationsView = Marionette.CompositeView.extend({
            template: '#notifications-settings-template',
            childViewContainer: '#notification-templates',
            childView: Views.NotificationItemView
        });

        Views.PermissionItemView = Marionette.ItemView.extend({
            template: '#permission-item-template',
            tagName: 'tr',

            onRender: function(){
                console.log(this.model)
            }
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
                generalBtn: '#general-btn',
                permissionsBtn: '#permissions-btn',
                notificationsBtn: '#notifications-btn'
            },
            events: {
                'click #general-btn': 'redirectToGeneral',
                'click #permissions-btn': 'redirectToPermissions',
                'click #notifications-btn': 'redirectToNotifications'
            },
            redirectToGeneral: function(evt){
                App.router.navigate('/', {trigger: true});
                return false;
            },
            redirectToPermissions: function(evt){
                App.router.navigate('/permissions/', {trigger: true});
                return false;
            },
            redirectToNotifications: function(evt){
                App.router.navigate('/notifications/', {trigger: true});
                return false;
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

            showGeneral: function(){
                var layout_view = new App.Views.SettingsLayout();
                var general_view = new App.Views.GeneralView();
                this.listenTo(layout_view, 'show', function(){
                    layout_view.main.show(general_view);
                });
                App.contents.show(layout_view);
            }
        });

        SettingsCRUD.addInitializer(function(){
            var controller = new SettingsCRUD.Controller();
            App.router = new Marionette.AppRouter({
                controller: controller,
                appRoutes: {
                    '': 'showGeneral',
                    'permissions/': 'showPermissions',
                    'notifications/': 'showNotifications',
                    'notifications/add/': 'addNotifications',
                    'notifications/edit/:id/': 'editNotifications',
                    'general/': 'showGeneral'
                }
            });
        });

    });

    SettingsApp.on('start', function(){
        if (Backbone.history) {
            Backbone.history.start({root: '/settings', pushState: true});
        }
    });

    return SettingsApp;
});

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

        Data.PermissionsCollection = Backbone.Collection.extend({
            url: '/api/settings/permissions',
            model: Data.PermissionModel
        });

    });

    SettingsApp.module('Views', function(Views, App, Backbone, Marionette, $, _){

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
                })
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
                        console.log(rs)
                        $.notify('Permission changed successfully')
                    }
                });
                console.log(pid)
            }
        });

        Views.SettingsLayout = Marionette.LayoutView.extend({
            template: '#settings-layout-template',
            regions: {
                main: 'div#details_content'
            }
        });

    });

    SettingsApp.module('SettingsCRUD', function(SettingsCRUD, App, Backbone, Marionette, $, _){

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
            }
        });

        SettingsCRUD.addInitializer(function(){
            var controller = new SettingsCRUD.Controller();
            App.router = new Marionette.AppRouter({
                controller: controller,
                appRoutes: {
                    '': 'showSettings',
                    'permissions/': 'showPermissions'
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

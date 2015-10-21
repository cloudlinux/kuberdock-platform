define(['backbone', 'marionette', 'predefined_app/app'], function(Backbone, Marionette, Apps){

    var controller = Marionette.Object.extend({

        listApps: function(){
            var that = this;
            require(['predefined_app/views', 'predefined_app/model'], function(Views, Data){
                var appCollection = new Data.AppCollection(),
                    mainLayout = new Views.MainLayout(),
                    breadcrumbsData = {buttonID: 'add_pod',  buttonLink: '/#newapp',
                                       buttonTitle: 'Add new application', showControls: true};
                appCollection.fetch({
                    wait: true,
                    success: function(){
                       Apps.contents.show(mainLayout);
                    }
                });

                that.listenTo(mainLayout, 'app:showloadcontrol', function(id){
                    var breadcrumbsModel = new Backbone.Model(_.extend(
                            _.clone(breadcrumbsData),
                            {breadcrumbs: [{name: 'Predefined Apps'}, {name: 'Add new application'}]},
                            {showControls: false})),
                        breadcrumbsView = new Views.Breadcrumbs({model: breadcrumbsModel}),
                        appModel = (id !== undefined) ? appCollection.get(id) : new Data.AppModel();
                    mainLayout.breadcrumbs.show(breadcrumbsView);
                    mainLayout.main.show(new Views.AppLoader({model: appModel}));
                });

                that.listenTo(mainLayout, 'app:save', function(model){
                    var isNew = model.isNew();
                    model.save(null, {
                            wait: true,
                            success: function(){
                                var breadcrumbsModel = new Backbone.Model(_.extend(
                                        _.clone(breadcrumbsData), {breadcrumbs: [{name: 'Predefined Apps'}]})),
                                    breadcrumbsView = new Views.Breadcrumbs({model: breadcrumbsModel});
                                mainLayout.breadcrumbs.show(breadcrumbsView);
                                if (isNew) appCollection.add(model);
                                mainLayout.main.show(new Views.AppList({collection: appCollection}));
                            },
                            error: function(){
                                console.log('could not upload an app')
                            }
                        });
                });

                that.listenTo(mainLayout, 'app:cancel', function(){
                    that.listApps();
                });

                that.listenTo(mainLayout, 'show', function(){
                    var breadcrumbsModel = new Backbone.Model(_.extend(
                            _.clone(breadcrumbsData), {breadcrumbs: [{name: 'Predefined Apps'}]})),
                        breadcrumbsView = new Views.Breadcrumbs({model: breadcrumbsModel});
                    mainLayout.breadcrumbs.show(breadcrumbsView);
                    mainLayout.main.show(new Views.AppList({collection: appCollection}));
                });
            });
        }
    });
    return controller;
});
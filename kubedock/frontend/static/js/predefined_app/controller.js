define(['backbone', 'marionette', 'predefined_app/app', '../utils'],
       function(Backbone, Marionette, Apps, utils){

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

                var successModelSaving = function(context) {
                    var breadcrumbsModel = new Backbone.Model(_.extend(
                            _.clone(context.breadcrumbsData), {breadcrumbs: [{name: 'Predefined Apps'}]})),
                        breadcrumbsView = new Views.Breadcrumbs({model: breadcrumbsModel});

                    $.notify(
                        'Predefined application "' + context.model.attributes.name +
                        '" is ' + (context.isNew ? 'added':'updated'),
                        {
                            autoHideDelay: 5000,
                            clickToHide: true,
                            globalPosition: 'bottom left',
                            className: 'success'
                        }
                    );
                    context.mainLayout.breadcrumbs.show(breadcrumbsView);
                    if (context.isNew) {
                        context.appCollection.add(context.model);
                    }
                    context.mainLayout.main.show(new Views.AppList({
                        collection: context.appCollection
                    }));
                };

                var getValidationError = function(data) {
                    var res = '';
                    if (data.common) {
                        res += JSON.stringify(data.common) + '<br />';
                    }
                    if (data.customVars) {
                        res += 'Invalid custom variables:<br />' +
                            JSON.stringify(data.customVars) + '<br />';
                    }
                    if (data.values) {
                        res += 'Invalid values:<br />' +
                            JSON.stringify(data.values) + '<br />';
                    }
                    if (!res) {
                        res = JSON.stringify(data);
                    }
                    return res;
                };

                var errorModelSaving = function(context, response) {
                    if (!(response.responseJSON &&
                          response.responseJSON.data &&
                          response.responseJSON.data.validationError)){
                        return;
                    }
                    var errorText = getValidationError(
                        response.responseJSON.data.validationError);
                    errorText = 'Your template contains some errors. ' +
                        'Are you shure you want to save it with that errors?' +
                        '<br/><hr/>' +
                        errorText;
                    utils.modalDialog({
                        title: 'Invalid template',
                        body: errorText,
                        show: true,
                        small: true,
                        footer: {
                            buttonOk: function(){
                                context.model.save(null, {
                                    wait: true,
                                    success: function() {
                                        successModelSaving(context);
                                    }
                                });
                            },
                            buttonCancel: true
                        }
                    });
                };

                that.listenTo(mainLayout, 'app:save', function(model){
                    var context = {
                        mainLayout: mainLayout,
                        appCollection: appCollection,
                        isNew: model.isNew(),
                        breadcrumbsData: breadcrumbsData,
                        model: model
                    };
                    // First try to save with validation turned on.
                    // If there will be a validation error, then the user will
                    // be asked about saving template with errors. If user
                    // have confirm, then the model will be saved without
                    // validation flag.
                    model.save(null, {
                            wait: true,
                            url: model.url() + '?' + $.param({validate: true}),
                            success: function() {successModelSaving(context);},
                            error: function(model, response, options){
                                errorModelSaving(context, response);
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

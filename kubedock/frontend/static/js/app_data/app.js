define(['backbone', 'marionette'], function(Backbone, Marionette){
    "use strict";
    var App = new Backbone.Marionette.Application({
        regions: {
            contents: '#contents'
        },

        initialize: function(){
            var that = this;
            require(['app_data/model', 'app_data/utils'], function(Model, Utils){
                that.menuCollection = new Model.MenuCollection(backendData.menu);
                that.getPodCollection = function(){
                    var deferred = $.Deferred();
                    if (_.has(that, 'podCollection')) {
                        deferred.resolveWith(that, [that.podCollection]);
                    }
                    else {
                        that.podCollection = new Model.PodCollection();
                        if (backendData.podCollection !== undefined) {
                            that.podCollection.reset(backendData.podCollection);
                            deferred.resolveWith(that, [that.podCollection]);
                        }
                        else {
                            that.podCollection.fetch({
                                wait: true,
                                success: function(collection, response, options){
                                    deferred.resolveWith(that, [collection]);
                                }
                            });
                        }
                    }
                    return deferred.promise();
                };

                that.getNodeCollection = function(){
                    var deferred = $.Deferred();
                    if (_.has(that, 'nodeCollection')) {
                        deferred.resolveWith(that, [that.nodeCollection]);
                    }
                    else {
                        that.nodeCollection = new Model.NodeCollection();
                        if (backendData.nodeCollection) {
                            that.nodeCollection.reset(backendData.nodeCollection);
                            deferred.resolveWith(that, [that.nodeCollection]);
                        }
                        else {
                            that.nodeCollection.fetch({
                                wait: true,
                                success: function(collection, response, options){
                                    deferred.resolveWith(that, [collection]);
                                }
                            });
                        }
                    }
                    return deferred.promise();
                };

                that.getUserCollection = function(){
                    var deferred = $.Deferred();
                    if (_.has(that, 'userCollection')) {
                        deferred.resolveWith(that, [that.userCollection]);
                    }
                    else {
                        that.userCollection = new Model.UsersPageableCollection();
                        that.userCollection.fetch({
                            wait: true,
                            success: function(collection, response, options){
                                deferred.resolveWith(that, [collection]);
                            }
                        });
                    }
                    return deferred.promise();
                };

                that.getKubeTypes = function(){
                    var deferred = $.Deferred();
                    if (typeof kubeTypes === 'undefined') {
                        $.get('/api/pricing/kubes', function(data){
                            deferred.resolveWith(that, [_.has(data, 'data') ? data['data'] : data]);
                        });
                    }
                    else {
                        deferred.resolveWith(that, [kubeTypes]);
                    }
                    return deferred.promise();
                };

                that.getRoles = function(){
                    var deferred = $.Deferred();
                    if (typeof roles === 'undefined') {
                        $.get('/api/users/roles', function(data){
                            deferred.resolveWith(that, [_.has(data, 'data') ? data['data'] : data]);
                        });
                    }
                    else {
                        deferred.resolveWith(that, [roles]);
                    }
                    return deferred.promise();
                };

                that.getPackages = function(){
                    var deferred = $.Deferred();
                    if (typeof packages === 'undefined') {
                        $.get('/api/pricing/packages', function(data){
                            deferred.resolveWith(that, [_.has(data, 'data') ? data['data'] : data]);
                        });
                    }
                    else {
                        deferred.resolveWith(that, [packages]);
                    }
                    return deferred.promise();
                };

                that.getIPPoolCollection = function(){
                    var deferred = $.Deferred();
                    if (_.has(that, 'ippoolCollection')) {
                        deferred.resolveWith(that, [that.ippoolCollection]);
                    }
                    else {
                        that.ippoolCollection = new Model.NetworkCollection();
                        that.ippoolCollection.fetch({
                            wait: true,
                            success: function(collection, response, options){
                                deferred.resolveWith(that, [collection]);
                            }
                        });
                    }
                    return deferred.promise();
                };

                that.getSystemSettingsCollection = function(){
                    var deferred = $.Deferred();
                    if (_.has(that, 'systemSettingsCollection')) {
                        deferred.resolveWith(that, [that.systemSettingsCollection]);
                    }
                    else {
                        that.systemSettingsCollection = new Model.SettingsCollection();
                        that.systemSettingsCollection.fetch({
                            wait: true,
                            success: function(collection, response, options){
                                deferred.resolveWith(that, [collection]);
                            }
                        });
                    }
                    return deferred.promise();
                };
                
                that.commandPod = function(cmd, pod){
                    if (pod.constructor !== Model.Pod) {
                        console.log("Pod Model instance is expected!");
                        return;
                    }
                    if (/^container_/.test(cmd)) {
                        console.error('Container stop/start/delete not implemented yet.');
                        return;
                    }
                    Utils.preloader.show();
                    return pod.command(cmd, {
                        wait: true,
                        error: function(model, xhr){ Utils.notifyWindow(xhr); },
                        complete: function(){ Utils.preloader.hide(); },
                    });
                };

                that.updateContainer = function(containerModel){
                    var performUpdate = function () {
                        Utils.preloader.show();
                        return containerModel.update().always(Utils.preloader.hide)
                            .fail(function(xhr){ Utils.notifyWindow(xhr); });
                    };

                    Utils.modalDialog({
                        title: 'Update container',
                        body: "During update whole pod will be restarted. Continue?",
                        small: true,
                        show: true,
                        footer: {buttonOk: performUpdate, buttonCancel: true}
                    });
                };

                that.checkContainerForUpdate = function(containerModel){
                    Utils.preloader.show();
                    return containerModel.checkForUpdate().always(Utils.preloader.hide)
                        .fail(function(xhr){ Utils.notifyWindow(xhr); })
                        .done(function(rs){
                            if (!rs.data)
                                Utils.notifyWindow('No updates found', 'success');
                        });
                };

            });
        }
    });

    App.navigate = function(route, options){
        options || (options = {});
        Backbone.history.navigate(route, options);
    };

    App.getCurrentRoute = function(){
        return Backbone.history.fragment;
    };

    App.on('start', function(){
        var that = this;
        require(['app_data/controller', 'app_data/router', 'app_data/utils'],
                function(Controller, Router, Utils){

            var controller = new Controller();
            new Router({controller: controller});

            function eventHandler(nodes){
                var source = new EventSource("/api/stream"), events;
                var collectionChange = function(collectionGetter){
                    return function(ev){
                        collectionGetter.apply(that).done(function(collection){
                            var data = JSON.parse(ev.data),
                                item = collection.fullCollection.get(data.id);
                            if (item) {
                                item.fetch({statusCode: null}).fail(function(xhr){
                                    if (xhr.status == 404)
                                        collection.remove(item);
                                });
                            } else {  // it's a new item, or we've missed some event
                                collection.fetch();
                            }
                        });
                    };
                };

                if (typeof(EventSource) === undefined) {
                    console.log('ERROR: EventSource is not supported by browser');
                }
                else {
                    if (nodes) {
                        events = {
                            'node:change': collectionChange(that.getNodeCollection),
                            // 'ippool:change': collectionChange(that.getIPPoolCollection),
                            // 'user:change': collectionChange(that.getUserCollection),
                            'node:installLog': function(ev){
                                that.getNodeCollection().done(function(collection){
                                    var decoded = JSON.parse(ev.data),
                                        node = collection.get(decoded.id);
                                    if (typeof(node) !== 'undefined')
                                        node.appendLogs(decoded.data);
                                });
                            },
                        };
                    } else {
                        events = {
                            'pod:change': collectionChange(that.getPodCollection),
                            // 'pd:change':
                        };
                    }

                    events['notify:error'] = function(ev) {
                        console.log(ev);
                        var data = JSON.parse(ev.data);
                        Utils.notifyWindow(data.message);
                    };

                    _.mapObject(events, function(handler, eventName){
                        source.addEventListener(eventName, handler, false);
                    });
                    source.onerror = function () {
                        console.info('SSE Error');
                        source.close();
                        setTimeout(_.partial(eventHandler, nodes), 5000);
                    };
                }
            }

            if (Backbone.history) {
                Backbone.history.start({root: '/'});

                eventHandler(backendData.destination === 'nodes');
                //console.log('impersontated', backendData.impersonated ? true : false);
                if (App.getCurrentRoute() === "") {
                    if (backendData.destination === 'nodes') {
                        App.navigate('nodes');
                        controller.showNodes();
                    }
                    else {
                        App.navigate('pods');
                        controller.showPods();
                    }
                }
            }
        });
    });

    return App;
});

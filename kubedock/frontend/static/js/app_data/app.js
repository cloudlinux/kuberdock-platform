define(['backbone', 'marionette'], function(Backbone, Marionette){
    "use strict";
    var App = new Backbone.Marionette.Application({
        regions: {
            contents: '#contents',
            message: '#message-popup'
        },

        initialize: function(){
            var that = this;
            this.lastEventId = null;
            require(['app_data/model', 'app_data/utils'], function(Model, Utils){
                that.storage = window.localStorage || window.sessionStorage || {};
                that.menuCollection = new Model.MenuCollection(backendData.menu);
                that.currentUser = new Model.CurrentUserModel(backendData.user);

                // billing & resources
                that.packageCollection = new Backbone.Collection(
                    backendData.packages, {model: Model.Package});
                that.kubeTypeCollection = new Model.KubeTypeCollection(
                    backendData.kubeTypes);
                that.packageKubeCollection = new Backbone.Collection(
                    _.map(backendData.packageKubes, function(pk){
                        return {'price': pk.kube_price,
                                'kubeType': that.kubeTypeCollection.get(pk.kube_id),
                                'package': that.packageCollection.get(pk.package_id)};
                    }),
                    {model: Model.PackageKube});
                that.userPackage = that.packageCollection.get(backendData.userPackage);

                that.getPodCollection = function(){
                    var deferred = $.Deferred();
                    if (_.has(that, 'podCollection')) {
                        deferred.resolveWith(that, [that.podCollection]);
                    }
                    else {
                        that.podCollection = new Model.PodCollection();
                        if (backendData.podCollection !== undefined) {
                            that.podCollection.fullCollection.reset(
                                backendData.podCollection);
                            deferred.resolveWith(that, [that.podCollection]);
                        }
                        else {
                            that.podCollection.fetch({
                                wait: true,
                                success: function(collection, response, options){
                                    deferred.resolveWith(that, [collection]);
                                },
                                error: function(collection, response) {
                                    Utils.notifyWindow(response);
                                    deferred.rejectWith(that, [response]);
                                },
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
                            that.nodeCollection.fullCollection.reset(
                                backendData.nodeCollection);
                            deferred.resolveWith(that, [that.nodeCollection]);
                        }
                        else {
                            that.nodeCollection.fetch({
                                wait: true,
                                success: function(collection, response, options){
                                    deferred.resolveWith(that, [collection]);
                                },
                                error: function(collection, response) {
                                    Utils.notifyWindow(response);
                                    deferred.rejectWith(that, [response]);
                                },
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
                            },
                            error: function(collection, response) {
                                Utils.notifyWindow(response);
                                deferred.rejectWith(that, [response]);
                            },
                        });
                    }
                    return deferred.promise();
                };

                that.getKubeTypes = function(){
                    var deferred = $.Deferred();
                    if (typeof kubeTypes === 'undefined') {
                        $.get('/api/pricing/kubes')
                            .done(function(data){
                                deferred.resolveWith(
                                    that,  [_.has(data, 'data') ? data.data : data]);
                            })
                            .fail(function(response){
                                Utils.notifyWindow(response);
                                deferred.rejectWith(that, [response]);
                            });
                    }
                    else {
                        deferred.resolveWith(that, [kubeTypes]);
                    }
                    return deferred.promise();
                };

                that.getTimezones = function(){
                    var deferred = $.Deferred();
                    if (!_.has(that, 'timezoneList')) {
                        $.get('/api/settings/timezone-list')
                            .done(function(data){
                                that.timezoneList = _.has(data, 'data') ? data.data : data;
                                deferred.resolveWith(that,  [that.timezoneList]);
                            })
                            .fail(function(response){
                                Utils.notifyWindow(response);
                                deferred.rejectWith(that, [response]);
                            });
                    }
                    else {
                        deferred.resolveWith(that, [that.timezoneList]);
                    }
                    return deferred.promise();
                };

                that.getRoles = function(){
                    var deferred = $.Deferred();
                    if (typeof roles === 'undefined') {
                        $.get('/api/users/roles')
                            .done(function(data){
                                deferred.resolveWith(
                                    that,  [_.has(data, 'data') ? data.data : data]);
                            })
                            .fail(function(response){
                                Utils.notifyWindow(response);
                                deferred.rejectWith(that, [response]);
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
                        $.get('/api/pricing/packages')
                            .done(function(data){
                                deferred.resolveWith(
                                    that,  [_.has(data, 'data') ? data.data : data]);
                            })
                            .fail(function(response){
                                Utils.notifyWindow(response);
                                deferred.rejectWith(that, [response]);
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
                            },
                            error: function(collection, response) {
                                Utils.notifyWindow(response);
                                deferred.rejectWith(that, [response]);
                            },
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
                            },
                            error: function(collection, response){
                                Utils.notifyWindow(response);
                                deferred.rejectWith(that, [response]);
                            },
                        });
                    }
                    return deferred.promise();
                };

                that.getLicenseModel = function(){
                    var deferred = $.Deferred();
                    if (_.has(that, 'licenseModel')) {
                        deferred.resolveWith(that, [that.licenseModel]);
                    }
                    else {
                        that.LicenseModel = new Model.LicenseModel();
                        that.LicenseModel.fetch({
                            wait: true,
                            success: function(collection, response, options){
                                deferred.resolveWith(that, [collection]);
                            },
                            error: function(collection, response){
                                Utils.notifyWindow(response);
                                deferred.rejectWith(that, [response]);
                            },
                        });
                    }
                    return deferred.promise();
                };

                that.getNotificationCollection = function(){
                    var deferred = $.Deferred();
                    if (_.has(that, 'notificationCollection')) {
                        deferred.resolveWith(that, [that.notificationCollection]);
                    }
                    else {
                        that.notificationCollection = new Backbone.Collection();
                        if (backendData.adviseCollection) {
                            that.notificationCollection.reset(
                                backendData.adviseCollection);
                            deferred.resolveWith(that, [that.notificationCollection]);
                        }
                        deferred.resolveWith(that, [that.notificationCollection]);
                    }
                    return deferred.promise();
                };

                that.commandPod = function(cmd, pod, options){
                    if (pod.constructor !== Model.Pod) {
                        console.log("Pod Model instance is expected!");
                        return;
                    }
                    if (/^container_/.test(cmd)) {
                        console.error('Container stop/start/delete not implemented yet.');
                        return;
                    }
                    Utils.preloader.show();
                    return pod.command(cmd, {wait: true, patch: true}, options)
                        .always(Utils.preloader.hide)
                        .fail(Utils.notifyWindow);
                };

                that.updateContainer = function(containerModel){
                    var performUpdate = function () {
                        Utils.preloader.show();
                        return containerModel.update()
                            .always(Utils.preloader.hide)
                            .fail(Utils.notifyWindow);
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
                    return containerModel.checkForUpdate()
                        .always(Utils.preloader.hide)
                        .fail(Utils.notifyWindow)
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

            function eventHandler(nodes, url){
                if (url === undefined) url = "/api/stream";
                var source = new EventSource(url),
                    events;
                var collectionEvent = function(collectionGetter, eventType){
                    eventType = eventType || 'change';
                    return function(ev){
                        collectionGetter.apply(that).done(function(collection){
                            that.lastEventId = ev.lastEventId;
                            var data = JSON.parse(ev.data);
                            if (eventType === 'delete'){
                                collection.fullCollection.remove(data.id);
                                return;
                            }
                            var item = collection.fullCollection.get(data.id);
                            if (item) {
                                item.fetch({statusCode: null}).fail(function(xhr){
                                    if (xhr.status == 404)  // "delete" event was missed
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
                            'node:change': collectionEvent(that.getNodeCollection),
                            // 'ippool:change': collectionEvent(that.getIPPoolCollection),
                            // 'user:change': collectionEvent(that.getUserCollection),
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
                            'pod:change': collectionEvent(that.getPodCollection),
                            'pod:delete': collectionEvent(that.getPodCollection, 'delete'),
                            // 'pd:change':
                        };
                    }

                    events['notify:error'] = function(ev) {
                        that.lastEventId = ev.lastEventId;
                        var data = JSON.parse(ev.data);
                        Utils.notifyWindow(data.message);
                    };

                    events['node:deleted'] = function(ev) {
                        that.lastEventId = ev.lastEventId;
                        var data = JSON.parse(ev.data);
                        Utils.notifyWindow(data.message, 'success');
                        App.navigate('nodes');
                        controller.showNodes({deleted: data.id});
                    };

                    events['advise:show'] = function(ev) {
                        that.lastEventId = ev.lastEventId;
                        var data = JSON.parse(ev.data);
                        controller.attachNotification(data);
                    };

                    events['advise:hide'] = function(ev) {
                        that.lastEventId = ev.lastEventId;
                        var data = JSON.parse(ev.data);
                        controller.detachNotification(data);
                    };

                    _.mapObject(events, function(handler, eventName){
                        source.addEventListener(eventName, handler, false);
                    });
                    source.onopen = function(){
                        console.log('Connected!');
                    };
                    source.onerror = function () {
                        console.log('SSE Error. Reconnecting...');
                        if (source.readyState === 2){
                            var url = source.url;
                            if (that.lastEventId && url.indexOf('lastid') === -1) {
                                url += "?lastid=" + encodeURIComponent(that.lastEventId);
                            }
                            source.close();
                            setTimeout(_.partial(eventHandler, nodes, url), 5000);
                        }
                    };
                }
            }

            if (Backbone.history) {
                Backbone.history.start({root: '/'});

                eventHandler(backendData.destination === 'nodes');
                controller.showNotifications();
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

define(['backbone', 'marionette', 'app_data/utils'], function(Backbone, Marionette, Utils){
    "use strict";
    var App = new Backbone.Marionette.Application({
        regions: {
            contents: '#contents',
            message: '#message-popup'
        },

        initialize: function(){
            this._cache = backendData;
            this.lastEventId = null;
            this.storage = window.localStorage || window.sessionStorage || {};
        },

        /**
         * These resources must be fetched every time user logins in, and they
         * are widely used immediately after start, so let's just save them as
         * properties, so we won't need to go async every time we need them.
         */
        prepareInitialData: function(){
            var deferred = new $.Deferred();
            $.when(App.getCurrentUser(),
                   App.getMenuCollection(),
                   App.getPackages()).done(function(user, menu, packages){
                App.menuCollection = menu;
                App.currentUser = user;
                App.userPackage = packages.get(user.get('package_id'));
                deferred.resolveWith(App);
            }).fail(function(){ deferred.rejectWith(App, arguments); });
            return deferred;
        },


        /**
         * Create a function that will return promise for Backbone.Model,
         * Backbone.Collection, or plain data. It will try to find resource in
         * App._cache (initially it's a copy of backendData), and, if failed,
         * try to fetch from server and put in App._cache.
         * TODO: maybe it better to use Models everywhere, get rid of urls and plain data.
         *
         * @param {String} name - unique name of the resource.
         *      Used as id in _cache (and backendData)
         * @param {(Backbone.Model|Backbone.Collection)} ResourceClass -
         *      Used to fetch data from server or convert backendData.
         * @param {String} url - may be used instead of ResourceClass to
         *      get raw data.
         * @returns {Function} - function that returns a Promise
         */
        resourcePromiser: function(name, ResourceClass){
            var cache = this._cache, url;
            if (typeof ResourceClass === 'string'){
                url = ResourceClass;
                ResourceClass = null;
            }
            return _.bind(function(){
                var deferred = $.Deferred();
                if (cache[name] != null) {
                    if (ResourceClass != null && !(cache[name] instanceof ResourceClass))
                        cache[name] = new ResourceClass(cache[name]);
                    deferred.resolveWith(this, [cache[name]]);
                } else if (ResourceClass != null) {
                    new ResourceClass().fetch({
                        wait: true,
                        success: function(resource){
                            deferred.resolveWith(this, [cache[name] = resource]);
                        },
                        error: function(resource, response) {
                            Utils.notifyWindow(response);
                            deferred.rejectWith(this, [response]);
                        },
                    });
                } else {
                    $.get(url).done(function(data){
                        cache[name] = _.has(data, 'data') ? data.data : data;
                        deferred.resolveWith(this, [cache[name]]);
                    }).fail(function(response){
                        Utils.notifyWindow(response);
                        deferred.rejectWith(this, [response]);
                    });
                }
                return deferred.promise();
            }, this);
        },
    });

    App.navigate = function(route, options){
        options || (options = {});
        Backbone.history.navigate(route, options);
        return App;  // for chaining
    };

    App.getCurrentRoute = function(){
        return Backbone.history.fragment;
    };

    App.on('start', function(){
        var that = this;
        Utils.preloader.show();
        require(['app_data/controller', 'app_data/router'],
                function(Controller, Router){

            var controller = App.controller = new Controller();
            new Router({controller: controller});

            function eventHandler(nodes, url){
                if (url === undefined) url = "/api/stream";
                var source = App.sseEventSource = new EventSource(url),
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
                    console.log('ERROR: EventSource is not supported by browser');  // eslint-disable-line no-console
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

                    events['kube:add'] = events['kube:change'] = function(ev) {
                        that.lastEventId = ev.lastEventId;
                        var data = JSON.parse(ev.data);
                        that.kubeTypeCollection.add(data, {merge: true});
                    };

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
                        console.log('Connected!');  // eslint-disable-line no-console
                    };
                    source.onerror = function () {
                        console.log('SSE Error. Reconnecting...');  // eslint-disable-line no-console
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
                Backbone.history.start({root: '/', silent: true});
                Utils.preloader.hide();
                App.prepareInitialData().done(function(){
                    // trigger Routers for the current url
                    Backbone.history.loadUrl(App.getCurrentRoute());
                    controller.showNotifications();
                    eventHandler(App.currentUser.get('rolename') == 'Admin');
                });
            }
        });
    });

    return App;
});

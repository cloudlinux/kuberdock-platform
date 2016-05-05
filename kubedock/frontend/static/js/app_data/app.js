define(['backbone', 'marionette', 'app_data/utils'], function(Backbone, Marionette, Utils){
    "use strict";
    var App = new Backbone.Marionette.Application({
        regions: {
            contents: '#contents',
            message: '#message-popup'
        },

        initialize: function(){
            //this._cache = backendData;
            this._cache = {};
            this.lastEventId = null;
            this.storage = window.localStorage || window.sessionStorage || {};
            //delete this.storage.authData;
        },

        /**
         * These resources must be fetched every time user logins in, and they
         * are widely used immediately after start, so let's just save them as
         * properties, so we won't need to go async every time we need them.
         */
        prepareInitialData: function(){
            var deferred = new $.Deferred();
            App.getAuth().done(function(){
                $.when(App.getCurrentUser(),
                       App.getMenuCollection(),
                       App.getPackages()).done(function(user, menu, packages){
                    App.menuCollection = menu;
                    App.currentUser = user;
                    App.userPackage = packages.get(user.get('package_id'));
                    deferred.resolveWith(App);
                }).fail(function(){ deferred.rejectWith(App, arguments); });
            });
            return deferred;
        },

        logout: function(){
            // remove old resources
            //for (var resource in App._cache) delete App._cache[resource];
            //if (App.sseEventSource) {  // close SSE stream
            //    App.sseEventSource.close();
            //    delete App.sseEventSource;
            //    clearTimeout(App.eventHandlerReconnectTimeout);
            //}
            //$.get('/api/auth/logout');  // TODO-JWT: instead of this we'll need to remove token from App.storage
            return App;
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
                    App.getAuth().done(function(authData){
                        new ResourceClass().fetch({
                            wait: true,
                            headers: {'X-Auth-Token': authData.token},
                            success: function(resource, resp, options){
                                var token = options.xhr.getResponseHeader('X-Auth-Token');
                                if (token) {
                                    var auth = JSON.parse(App.storage.authData);
                                    auth.token = token;
                                    App.storage.authData = JSON.stringify(auth);
                                }
                                deferred.resolveWith(this, [cache[name] = resource]);
                            },
                            error: function(resource, response) {
                                Utils.notifyWindow(response);
                                deferred.rejectWith(this, [response]);
                            },
                        });
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

    App.getAuth = function(){
        console.log('getAuth called...');
        var deferred = $.Deferred();
        if (this.storage.authData != null){
            deferred.resolveWith(this, [JSON.parse(this.storage.authData)]);
        } else {
            require(['app_data/login/views', 'app_data/model'], function (Views, Model) {
                App.message.empty();  // hide any notification
                var loginView = new Views.LoginView();
                App.listenTo(loginView,'action:signin', function(data){
                    new Model.AuthModel().save(data, {
                        wait:true,
                        success: function(model, resp, opts){
                            model.unset('password');
                            data = model.attributes;
                            App.storage.authData = JSON.stringify(data);
                            deferred.resolveWith(App, [data]);
                        },
                        error: function(resp){
                            deferred.rejectWith(App, []);
                        }
                    });
                });
                console.log('About to show login view');
                App.contents.show(loginView);
            });
        }
        return deferred.promise();
    };

    /**
     * @param {string} [options.url='/api/stream']
     * @param {number} [options.lastID]
     */
    App.eventHandler = function(options){
        options = options || {};
        App.getAuth().done(function(auth){
            var url = options.url || '/api/stream',
                lastID = options.lastID,
                token = auth.token,
                nodes = App.currentUser.roleIs('Admin'),
                that = this;

            url += (url.indexOf('?') === -1 ? '?' : '&')
                + $.param(lastID != null ? {token2: token, lastid: lastID} : {token2: token});
            console.log('eventing to:', url);
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
                return;
            }
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
                App.controller.showNodes({deleted: data.id});
            };

            events['advise:show'] = function(ev) {
                that.lastEventId = ev.lastEventId;
                var data = JSON.parse(ev.data);
                App.controller.attachNotification(data);
            };

            events['advise:hide'] = function(ev) {
                that.lastEventId = ev.lastEventId;
                var data = JSON.parse(ev.data);
                App.controller.detachNotification(data);
            };

            _.mapObject(events, function(handler, eventName){
                source.addEventListener(eventName, handler, false);
            });
            source.onopen = function(){
                console.log('Connected!');  // eslint-disable-line no-console
            };
            source.onerror = function () {
                console.log('SSE Error. Reconnecting...');  // eslint-disable-line no-console
                console.log(source);
                if (source.readyState !== 2)
                    return;
                source.close();
                var lastEventId = that.lastEventId || options.lastID,
                    newOptions = _.extend(_.clone(options), {lastID: lastEventId});
                setTimeout(_.bind(that.eventHandler, that, newOptions), 5000);
            };
        });
    };

    App.initApp = function(){
        //Utils.preloader.show();
        require(['app_data/controller', 'app_data/router'],
                function(Controller, Router){

            var controller = App.controller = new Controller();
            new Router({controller: controller});

            if (Backbone.history) {
                try {
                    Backbone.history.start({root: '/', silent: true});
                } catch(e){;}  // eslint-disable-line no-extra-semi
                //Utils.preloader.hide();
                App.prepareInitialData().done(function(){
                    // trigger Routers for the current url
                    Backbone.history.loadUrl(App.getCurrentRoute());
                    controller.showNotifications();
                    console.log('init');
                    App.eventHandler();
                });
            }
        });
    };

    App.on('start', App.initApp);

    return App;
});

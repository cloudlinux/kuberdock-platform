define(['backbone', 'marionette', 'app_data/utils'], function(Backbone, Marionette, Utils){
    "use strict";
    var App = new Backbone.Marionette.Application({
        regions: {
            contents: '#contents',
            message: '#message-popup'
        },

        initialize: function(){
            this._cache = {};
            this.lastEventId = null;
            this.storage = window.localStorage || window.sessionStorage || {};
        },

        /**
         * Remove auth data and all cached data; reinitialize app.
         *
         * @param {boolean} keepToken - use it for loginAs/logoutAs
         * @returns {Promise} - promise to be logged in :)
         */
        cleanUp: function(keepToken){
            this.initialized = false;
            $.xhrPool.abortAll();
            if (!keepToken)
                delete this.storage.authData;  // delete token
            _.each([  // delete all initial data
                'menuCollection', 'currentUser', 'userPackage',
                'packageCollection', 'kubeTypeCollection', 'packageKubeCollection'
            ], function(name){ delete this[name]; }, this);
            for (var resource in this._cache) delete this._cache[resource];
            if (this.sseEventSource) {  // close SSE stream
                this.sseEventSource.close();
                delete this.sseEventSource;
                clearTimeout(this.eventHandlerReconnectTimeout);
            }
            return this;
        },

        /**
         * Update token in storage.
         *
         * @param {Object} authData - modified data from App.getAuth
         */
        updateAuth: function(token){
            App.storage.authData = token;
        },

        /**
         * Create a function that will return promise for Backbone.Model,
         * Backbone.Collection, or plain data. It will try to find resource in
         * App._cache (initially it's a copy of backendData), and, if failed,
         * try to fetch from server and put in App._cache.
         * TODO: maybe it better to use Models everywhere, get rid of urls and plain data.
         *
         * @param {string} name - unique name of the resource.
         *      Used as id in _cache (and backendData)
         * @param {Backbone.Model|Backbone.Collection|string} ResourceClass -
         *      Used to fetch data from server or convert backendData.
         *      Url as a string may be used to get raw data.
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
                        success: function(resource, resp, options){
                            deferred.resolveWith(App, [cache[name] = resource]);
                        },
                        error: function(resource, response) {
                            Utils.notifyWindow(response);
                            deferred.rejectWith(App, [response]);
                        },
                    });
                } else {
                    $.ajax({
                        authWrap: true,
                        url: url,
                    }).done(function(data){
                        cache[name] = _.has(data, 'data') ? data.data : data;
                        deferred.resolveWith(App, [cache[name]]);
                    }).fail(function(response){
                        Utils.notifyWindow(response);
                        deferred.rejectWith(App, [response]);
                    });
                }
                return deferred.promise();
            }, this);
        },

        /**
         * Check that billing is enabled and count type of user's
         * package is "fixed"
         *
         * @returns {Promise} - promise of boolean value.
         */
        isFixedBilling: function(){
            var deferred = $.Deferred();
            this.getSystemSettingsCollection().done(function(settings){
                var billingType = settings.byName('billing_type').get('value');
                deferred.resolveWith(this, [
                    this.userPackage.get('count_type') === 'fixed' &&
                        billingType.toLowerCase() !== 'no billing']);
            }).fail(deferred.reject);
            return deferred.promise();
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

    /**
     * Get user's auth data from local storage.
     * If user is not logged in, return nothing.
     *
     * @returns {Object|undefined} - auth data
     */
    App.getCurrentAuth = function(){
        var authData = this.storage.authData,
            tokenPos = window.location.href.indexOf('token2'),
            token;
        if (tokenPos !== -1 && window.history.pushState) {
            var newurl = Utils.removeURLParameter(window.location.href, 'token2');
            window.history.pushState({path:newurl}, '', newurl);
        }
        if (authData){
            token = _.chain(authData.split('.')).first(2)
                .map(atob).object(['header', 'payload']).invert()
                .mapObject(JSON.parse).value();
            if (token.header.exp > +new Date() / 1000)
                return authData;
        }
    };

    /**
     * Get user's auth data. If user is not logged in, show login view and
     * return auth data as soon as user logs in.
     *
     * @returns {Promise} - promise of auth data
     */
    App.getAuth = function(){
        var deferred = $.Deferred(),
            authData = this.getCurrentAuth();
        if (authData)
            return deferred.resolveWith(this, [authData]).promise();
        this.cleanUp().controller.doLogin().done(function(authData){
            this.initApp().then(deferred.resolve, deferred.reject);
        });
        return deferred.promise();
    };

    /**
     * Connect to SSE stream
     *
     * @param {Object} [options]
     * @param {string} [options.url='/api/stream']
     * @param {number} [options.lastID]
     */
    App.eventHandler = function(options){
        options = options || {};
        var token = App.getCurrentAuth();
        if (!token)
            return;
        var url = options.url || '/api/stream',
            lastID = options.lastID,
            nodes = App.currentUser.roleIs('Admin'),
            that = this;

        url += (url.indexOf('?') === -1 ? '?' : '&')
            + $.param(lastID != null
                      ? {token2: token, lastid: lastID}
                      : {token2: token});
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
                            if (xhr.status === 404)  // "delete" event was missed
                                collection.remove(item);
                        });
                    } else {  // it's a new item, or we've missed some event
                        collection.fetch();
                    }
                });
            };
        };

        if (typeof EventSource === undefined) {
            console.log(  // eslint-disable-line no-console
                'ERROR: EventSource is not supported by browser');
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
                        if (typeof node !== 'undefined')
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

        events['notify:warning'] = function(ev) {
            that.lastEventId = ev.lastEventId;
            var data = JSON.parse(ev.data);
            Utils.notifyWindow(data.message, 'warning');
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

        events.refresh = function(ev) {
            App.cleanUp();
            document.location.reload(true);
        };

        _.mapObject(events, function(handler, eventName){
            source.addEventListener(eventName, handler, false);
        });
        source.onopen = function(){
            console.log('Connected!');  // eslint-disable-line no-console
        };
        source.onerror = function () {
            console.log('SSE Error. Reconnecting...');  // eslint-disable-line no-console
            var timeOut = 5000;
            if (source.readyState === 0){
                Utils.notifyWindow(
                    'The page you are looking for is temporarily unavailable. '
                    + 'Please try again later');
                timeOut = 30000;
            }
            if (source.readyState !== 2)
                return;
            source.close();

            // Try to ping API first: if the token has expired or got blocked,
            // the user will be automatically redirected to the "log in" page.
            App.currentUser.fetch().always(function(){
                var lastEventId = that.lastEventId || options.lastID,
                    newOptions = _.extend(_.clone(options), {lastID: lastEventId});
                setTimeout(_.bind(that.eventHandler, that, newOptions), timeOut);
            });
        };
    };

    /**
     * Prepare initial data, connect to SSE, render the first view.
     *
     * @returns {Promise} - Promise of auth data, SSE, and initial data in App.
     */
    App.initApp = function(){
        var deferred = new $.Deferred();
        App.getAuth().done(function(authData){
            if (App.initialized){
                deferred.resolveWith(App, [authData]);
                return;
            }
            $.when(App.getCurrentUser(),
                   App.getMenuCollection(),
                   App.getPackages()).done(function(user, menu, packages){
                // These resources must be fetched every time user logins in, and they
                // are widely used immediately after start, so let's just save them as
                // properties, so we won't need to go async every time we need them.
                App.menuCollection = menu;
                App.currentUser = user;
                App.userPackage = packages.get(user.get('package_id'));
                // open SSE stream
                App.eventHandler();
                // trigger Routers for the current url
                Backbone.history.loadUrl(App.getCurrentRoute());
                App.controller.showNotifications();
                App.initialized = true;
                deferred.resolveWith(App, [authData]);
            }).fail(function(){ deferred.rejectWith(App, arguments); });
        });
        return deferred.promise();
    };

    App.on('start', function(){
        Utils.preloader.show();
        require(['app_data/controller', 'app_data/router'],
                function(Controller, Router){

            var controller = App.controller = new Controller();
            new Router({controller: controller});

            if (Backbone.history) {
                Backbone.history.start({root: '/', silent: true});
                Utils.preloader.hide();
                App.initApp();
            }
        });
    });


    // track all unfinished requests, so we can abort them on logout
    $.xhrPool = [];
    $(document).ajaxSend(function(e, xhr, options){
        $.xhrPool.push(xhr);

        if (options.authWrap){
            var token = App.getCurrentAuth();
            if (token){
                xhr.done(function(){
                    if (xhr && (xhr.status === 401 || xhr.status === 403)){
                        App.cleanUp().initApp();
                    } else if (App.getCurrentAuth()){
                        var token = xhr.getResponseHeader('X-Auth-Token');
                        if (token) {
                            App.updateAuth(token);
                        }
                    }
                })
                .fail(function(xhr){
                    if (xhr.status === 401 || xhr.status === 403) {
                        App.cleanUp().initApp();
                    }
                }).setRequestHeader('X-Auth-Token', token);
            } else {
                xhr.abort();
                App.cleanUp().initApp();
            }
        }
    });
    $(document).ajaxComplete(function(e, xhr){
        $.xhrPool.splice(_.indexOf($.xhrPool, xhr), 1);
    });
    $.xhrPool.abortAll = function() {
        _.each(this.splice(0), function(xhr){ xhr.abort(); });
    };

    return App;
});

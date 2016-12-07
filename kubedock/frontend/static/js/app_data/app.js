define(['backbone', 'marionette', 'app_data/utils'], function(Backbone, Marionette, Utils){
    "use strict";


    var App = new Backbone.Marionette.Application({
        rootLayout: new (Backbone.Marionette.LayoutView.extend({
            el: 'body',
            template: require('app_data/layout.tpl'),
            regions: {
                nav: 'div#nav',
                contents: '#contents',
                message: '#message-popup',
            },
            onBeforeShow(){ Utils.preloader.show(); },
            onShow(){ Utils.preloader.hide(); },
        })),

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
            if (this.sse) {  // close SSE stream
                this.sse.kill();
                delete this.sse;
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

        resourcePromiser: function(name, ResourceClass){
            return Utils.resourcePromiser(this._cache, name, ResourceClass, this);
        },

        /**
         * Remove resource from cache
         *
         */
        resourceRemoveCache: function(name) {
            var cache = this._cache;
            cache[name] = null;
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
        var tokenPos = window.location.href.indexOf('token2');
        if (tokenPos !== -1 && window.history.pushState) {
            var newurl = Utils.removeURLParameter(window.location.href, 'token2');
            window.history.pushState({path:newurl}, '', newurl);
        }
        return Utils.checkToken(this.storage.authData);
    };

    /**
     * Get user's auth data. If user is not logged in, show login view and
     * return auth data as soon as user logs in.
     *
     * @returns {Promise} - promise of auth data
     */
    App.getAuth = function(){
        let deferred = $.Deferred(),
            authData = this.getCurrentAuth();
        if (authData){
            let token = Utils.parseJWT(authData);
            if (token.payload.auth){
                // need to replace SSO token with session token
                $.ajax({
                    url: '/api/v1/users/self',
                    headers: {'X-Auth-Token': authData},
                }).then((data, status, xhr) => {
                    this.updateAuth(xhr.getResponseHeader('X-Auth-Token'));
                    deferred.resolveWith(this, [this.getCurrentAuth()]);
                }, () => this.cleanUp().getAuth());
            } else {
                return deferred.resolveWith(this, [authData]).promise();
            }
        } else {
            this.cleanUp().controller.doLogin().then(authData => {
                this.initApp().then(deferred.resolve, deferred.reject);
            });
        }
        return deferred.promise();
    };

    /**
     * Connect to SSE stream
     */
    App.eventHandler = function(options){
        let token = App.getCurrentAuth();
        if (!token)
            return;
        let sse = new Utils.EventHandler({token, error: () => {
            let timeOut = 5000;
            if (sse.source.readyState === 0){
                Utils.notifyWindow(
                    'The page you are looking for is temporarily unavailable. ' +
                    'Please try again later');
                timeOut = 30000;
            }
            if (sse.source.readyState !== 2)
                return;

            // Try to ping API first: if the token has expired or got blocked,
            // the user will be automatically redirected to the "log in" page.
            this.currentUser.fetch().always(() => {
                setTimeout(() => this.addEventListenersSSE(sse.retry()), timeOut);
            });
        }});
        this.sse = sse;
        this.addEventListenersSSE(sse);
    };

    App.addEventListenersSSE = function(sse){
        let events,
            nodes = App.currentUser.roleIs('Admin'),
            collectionEvent = (...args) => Utils.collectionEvent(sse, ...args);

        if (nodes) {
            events = {
                'node:change': collectionEvent(App.getNodeCollection),
                // 'ippool:change': collectionEvent(App.getIPPoolCollection),
                // 'user:change': collectionEvent(App.getUserCollection),
                'node:installLog': function(ev){
                    App.getNodeCollection().done(function(collection){
                        var decoded = JSON.parse(ev.data),
                            node = collection.get(decoded.id);
                        if (typeof node !== 'undefined')
                            node.appendLogs(decoded.data);
                    });
                },
            };
        } else {
            events = {
                'pod:change': collectionEvent(App.getPodCollection),
                'pod:delete': collectionEvent(App.getPodCollection, 'delete'),
                // 'pd:change':
            };
        }

        events['kube:add'] = events['kube:change'] = function(ev) {
            sse.lastEventId = ev.lastEventId;
            var data = JSON.parse(ev.data);
            App.kubeTypeCollection.add(data, {merge: true});
        };

        events['notify:warning'] = function(ev) {
            sse.lastEventId = ev.lastEventId;
            var data = JSON.parse(ev.data);
            Utils.notifyWindow(data.message, 'warning');
        };

        events['notify:error'] = function(ev) {
            sse.lastEventId = ev.lastEventId;
            var data = JSON.parse(ev.data);
            Utils.notifyWindow(data.message);
        };

        events['node:deleted'] = function(ev) {
            sse.lastEventId = ev.lastEventId;
            var data = JSON.parse(ev.data);
            Utils.notifyWindow(data.message, 'success');
            App.navigate('nodes');
            App.controller.showNodes({deleted: data.id});
        };

        events['advise:show'] = function(ev) {
            sse.lastEventId = ev.lastEventId;
            var data = JSON.parse(ev.data);
            App.controller.attachNotification(data);
        };

        events['advise:hide'] = function(ev) {
            sse.lastEventId = ev.lastEventId;
            var data = JSON.parse(ev.data);
            App.controller.detachNotification(data);
        };

        events.refresh = function(ev) {
            App.cleanUp();
            document.location.reload(true);
        };

        _.mapObject(events, function(handler, eventName){
            sse.source.addEventListener(eventName, handler, false);
        });
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
                App.controller.showMenu();
                App.initialized = true;
                deferred.resolveWith(App, [authData]);
            }).fail(function(){ deferred.rejectWith(App, arguments); });
        });
        return deferred.promise();
    };

    App.on('start', function(){
        Utils.preloader.show();
        const Controller = require('app_data/controller');
        const Router = require('app_data/router');
        new Router({controller: App.controller = new Controller()});

        App.rootLayout.render();

        if (Backbone.history) {
            Backbone.history.start({root: '/', silent: true});
            Utils.preloader.hide();
            App.initApp();
        }
    });


    // track all unfinished requests, so we can abort them on logout
    $.xhrPool = [];

    App.ajaxSendWrapper = function(e, xhr, options) {
        $.xhrPool.push(xhr);

        if (options.authWrap){
            var token = App.getCurrentAuth();
            if (token){
                xhr.done(function(){
                    if (xhr && (xhr.status === 401)){
                        App.cleanUp().initApp();
                    } else if (App.getCurrentAuth()){
                        var token = xhr.getResponseHeader('X-Auth-Token');
                        if (token) {
                            App.updateAuth(token);
                        }
                    }
                })
                .fail(function(xhr){
                    if (xhr.status === 401) {
                        App.cleanUp().initApp();
                    }
                }).setRequestHeader('X-Auth-Token', token);
            } else {
                xhr.abort();
                App.cleanUp().initApp();
            }
        }
    };

    $(document).ajaxSend(App.ajaxSendWrapper);
    $(document).ajaxComplete(function(e, xhr){
        $.xhrPool.splice(_.indexOf($.xhrPool, xhr), 1);
    });
    $.xhrPool.abortAll = function() {
        _.each(this.splice(0), function(xhr){ xhr.abort(); });
    };

    return App;
});

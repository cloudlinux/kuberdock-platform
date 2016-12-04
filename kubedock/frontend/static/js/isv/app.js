import * as utils from 'app_data/utils';


const RootLayout = Marionette.LayoutView.extend({
    template: require('isv/misc/templates/root_layout.tpl'),
    regions: {
        topbar: '.kd-topbar',
        sidebar: '.kd-sidebar',
        contents: '.kd-content',
    },
    onBeforeShow(){ utils.preloader2.show(); },
    onShow(){ utils.preloader2.hide(); },
});


const App = new Marionette.Application({
    initialize(){
        this._cache = {};
        this.lastEventId = null;
        this.storage = window.localStorage || window.sessionStorage || {};

        let defaultGlobalConfig = {
            apiHost: `${window.location.protocol}//${window.location.host}`,
            rootElement: '.kd-isv-container',
            externalData: {
                price: '',
            },
            externalLinks: {
                billing: '',
                switchPackage: '',
                resetPassword: '',
            },
        };
        this.config = Object.assign(defaultGlobalConfig, window.KD_GLOBAL || {});
    },

    navigate(route, options = {}){
        Backbone.history.navigate(route, options);
        return this;  // for chaining
    },

    getCurrentRoute(){
        return Backbone.history.fragment;
    },

    resourcePromiser(name, ResourceClass){
        return utils.resourcePromiser(this._cache, name, ResourceClass, this);
    },

    /**
     * Remove auth data and all cached data; reinitialize app.
     *
     * @param {boolean} keepToken - use it for loginAs/logoutAs
     * @returns {Promise} - promise to be logged in :)
     */
    cleanUp(keepToken){
        this.initialized = false;
        $.xhrPool.abortAll();
        if (!keepToken)
            delete this.storage.authData;  // delete token
        _.each([  // delete all initial data
            'currentUser', 'userPackage',
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
    updateAuth(token){
        if (App.storage.authData){
            let oldToken = utils.parseJWT(App.storage.authData);
            let newToken = utils.parseJWT(token);
            if (oldToken.header.exp > newToken.header.exp)
                return;  // old token will live longer
        }
        App.storage.authData = token;
    },

    /**
     * Connect to SSE stream
     */
    eventHandler(){
        let token = App.getCurrentAuth(),
            url = App.config.apiHost + '/api/stream';
        if (!token)
            return;
        let sse = new utils.EventHandler({token, url, error: () => {
            let timeOut = 5000;
            if (sse.source.readyState === 0){
                utils.notifyWindow(
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
        this.addEventListenersSSE(sse);
    },

    addEventListenersSSE(sse){
        let events = {
            'pod:change': utils.collectionEvent(sse, this.getPodCollection),
            'pod:delete': utils.collectionEvent(sse, this.getPodCollection, 'delete'),
            'notify:warning': ev => {
                sse.lastEventId = ev.lastEventId;
                var data = JSON.parse(ev.data);
                utils.notifyWindow(data.message, 'warning');
            },
            'notify:error': ev => {
                sse.lastEventId = ev.lastEventId;
                var data = JSON.parse(ev.data);
                utils.notifyWindow(data.message);
            },
            'refresh': ev => {
                App.cleanUp();
                document.location.reload(true);
            },
        };

        _.mapObject(events, function(handler, eventName){
            sse.source.addEventListener(eventName, handler, false);
        });
    },


    /**
     * Get user's auth data from local storage.
     * If user is not logged in, return nothing.
     *
     * @returns {Object|undefined} - auth data
     */
    getCurrentAuth(){
        var tokenPos = window.location.href.indexOf('token2');
        if (tokenPos !== -1 && window.history.pushState) {
            var newurl = utils.removeURLParameter(window.location.href, 'token2');
            window.history.pushState({path: newurl}, '', newurl);
        }
        return utils.checkToken(this.storage.authData);
    },

    /**
     * Get user's auth data. If user is not logged in, show login view and
     * return auth data as soon as user logs in.
     *
     * @returns {Promise} - promise of auth data
     */
    getAuth(){
        var deferred = $.Deferred(),
            authData = this.getCurrentAuth();
        if (authData)
            return deferred.resolveWith(this, [authData]).promise();
        this.cleanUp().controller.doLogin().done(function(authData){
            this.initApp().then(deferred.resolve, deferred.reject);
        });
        return deferred.promise();
    },

    /**
     * Prepare initial data, connect to SSE, render the first view.
     *
     * @returns {Promise} - Promise of auth data, SSE, and initial data in App.
     */
    initApp(){
        var deferred = new $.Deferred();
        this.getAuth().done(authData => {
            if (this.initialized){
                deferred.resolveWith(this, [authData]);
                return;
            }
            $.when(this.getCurrentUser(), this.getPackages()).done((user, packages) => {
                // These resources must be fetched every time user logins in, and they
                // are widely used immediately after start, so let's just save them as
                // properties, so we won't need to go async every time we need them.
                this.currentUser = user;
                this.userPackage = packages.get(user.get('package_id'));
                // open SSE stream
                this.eventHandler();
                // trigger Routers for the current url
                Backbone.history.loadUrl(this.getCurrentRoute());
                this.initialized = true;
                deferred.resolveWith(this, [authData]);
            }).fail(() => { deferred.rejectWith(this, arguments); });
        });
        return deferred.promise();
    },
});

App.on('start', function(){
    utils.preloader.show();
    const Controller = require('isv/controller').default;
    const Router = require('isv/router').default;
    new Router({controller: this.controller = new Controller()});

    this.rootLayout = new RootLayout({el: this.config.rootElement});
    this.rootLayout.render();

    if (Backbone.history) {
        Backbone.history.start({root: '/', silent: true});
        utils.preloader.hide();
        this.initApp();
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
                    if (token)
                        App.updateAuth(token);
                }
            })
            .fail(function(xhr){
                if (xhr.status === 401)
                    App.cleanUp().initApp();
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

export default App;

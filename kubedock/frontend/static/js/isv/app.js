/*
 * KuberDock - is a platform that allows users to run applications using Docker
 * container images and create SaaS / PaaS based on these applications.
 * Copyright (C) 2017 Cloud Linux INC
 *
 * This file is part of KuberDock.
 *
 * KuberDock is free software; you can redistribute it and/or
 * modify it under the terms of the GNU General Public License
 * as published by the Free Software Foundation; either version 2
 * of the License, or (at your option) any later version.
 *
 * KuberDock is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with KuberDock; if not, see <http://www.gnu.org/licenses/>.
 */

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

    apiUrl(...path){
        return [this.config.apiHost, 'api', ...path].join('/');
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
        ], name => this[name] = undefined);
        for (var resource in this._cache)
            this._cache[resource] = undefined;
        if (this._updateTokenTimeout)
            clearTimeout(this._updateTokenTimeout);
        if (this.sse) {  // close SSE stream
            this.sse.kill();
            this.sse = undefined;
        }
        return this;
    },

    /**
     * Update token in storage.
     *
     * @param {Object} authData - modified data from App.getAuth
     */
    updateAuth(token){
        if (this._updateTokenTimeout)
            clearTimeout(this._updateTokenTimeout);
        let newToken = utils.parseJWT(token);
        if (App.storage.authData){
            let oldToken = utils.parseJWT(App.storage.authData);
            if (oldToken.header.exp > newToken.header.exp &&
                    !oldToken.payload.auth)
                return;  // old token will live longer
        }
        App.storage.authData = token;
        // Ping API to receive a new token 10s before this one expires.
        // But in one hour without any action, it's safe to drop expired token.
        // This would keep user logged in while he does anything on the page.
        let doNotRenewTokenAfter = 60 * 60 * 1000;
        this._updateTokenTimeout = setTimeout(() => {
            if (new Date() - this.idleSince < doNotRenewTokenAfter)
                this.getCurrentUser({updateCache: true});
            else
                this.cleanUp().controller.doLogin();
        }, newToken.header.exp * 1000 - new Date() - 10000);
    },

    /**
     * Connect to SSE stream
     */
    eventHandler(){
        let token = App.getCurrentAuth(),
            url = App.apiUrl('stream');
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
        return new Promise((resolve, reject) => {
            let authData = this.getCurrentAuth();
            if (authData){
                let token = utils.parseJWT(authData);
                if (token.payload.auth){
                    // need to replace SSO token with session token
                    $.ajax({
                        url: this.apiUrl('users/self'),
                        headers: {'X-Auth-Token': authData},
                    }).then((data, status, xhr) => {
                        this.updateAuth(xhr.getResponseHeader('X-Auth-Token'));
                        resolve(this.getCurrentAuth());
                    }, () => this.cleanUp().controller.doLogin());
                } else {
                    resolve(authData);
                }
                return;
            }
            this.cleanUp().controller.doLogin();
            reject();
        });
    },

    /**
     * Prepare initial data, connect to SSE, render the first view.
     *
     * @returns {Promise} - Promise of auth data, SSE, and initial data in App.
     */
    initApp(){
        return new Promise((resolve, reject) => {
            this.getAuth().then(authData => {
                if (this.initialized){
                    resolve(authData);
                    return;
                }
                let initialData = [this.getCurrentUser(), this.getPackages()];
                Promise.all(initialData).then(([user, packages]) => {
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
                    resolve(authData);
                }, reject);
            });
        });
    },
});

App.on('start', function(){
    utils.preloader2.show();
    const Controller = require('isv/controller').default;
    const Router = require('isv/router').default;
    new Router({controller: this.controller = new Controller()});

    this.rootLayout = new RootLayout({el: this.config.rootElement});
    this.rootLayout.render();

    if (Backbone.history) {
        Backbone.history.start({root: '/', silent: true});
        utils.preloader2.hide();
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
    for (let xhr of this.splice(0))
        xhr.abort();
};

App.idleSince = +new Date();
$(document).on('click mousemove keyup', _.throttle(
    () => App.idleSince = +new Date(),
    5000, {trailing: false}));

export default App;

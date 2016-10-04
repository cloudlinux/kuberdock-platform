/* eslint-env mocha */
mocha.allowUncaught();

import {assert} from 'chai';
import sinon from 'sinon';
import app from 'app_data/app';


describe('App Tests', function () {
    describe('ajaxSendWrapper', function(){
        let updateAuth, cleanUp, initApp, xhr, options;
        let sandbox = sinon.sandbox.create();

        beforeEach(function(){

            sandbox.stub(app, 'getCurrentAuth', ()=>'token');
            updateAuth = sandbox.stub(app, 'updateAuth');
            cleanUp = sandbox.stub(app, 'cleanUp', () => app);
            initApp = sandbox.stub(app, 'initApp');
            xhr = {
                status: 200,
                getResponseHeader: function () {
                    return 'token';
                },
                done: function (callback) {
                    callback();
                    return this;
                },
                fail: function () {
                    return this;
                },
                setRequestHeader: function () {
                }
            };
            options = {};
        });

        afterEach(function () {
            sandbox.restore();
        });

        it("200 OK without authWrap", function () {
            app.ajaxSendWrapper(null, xhr, options);
            assert(cleanUp.notCalled);
            assert(initApp.notCalled);
            assert(updateAuth.notCalled);
        });

        it("200 OK with authWrap", function () {
            options.authWrap = true;
            app.ajaxSendWrapper(null, xhr, options);
            assert(cleanUp.notCalled);
            assert(initApp.notCalled);
            assert(updateAuth.called);
        });

        it("401 done", function () {
            options.authWrap = true;
            xhr.status = 401;
            app.ajaxSendWrapper(null, xhr, options);
            assert(cleanUp.called);
            assert(initApp.called);
            assert(updateAuth.notCalled);
        });

        it("403 done", function () {
            options.authWrap = true;
            xhr.status = 403;
            app.ajaxSendWrapper(null, xhr, options);
            assert(cleanUp.notCalled);
            assert(initApp.notCalled);
            assert(updateAuth.called);
        });

        it("401 fail", function () {
            options.authWrap = true;
            xhr.status = 401;
            xhr.done = function () {
                return this;
            };
            xhr.fail = function (callback) {
                callback(this);
                return this;
            };
            app.ajaxSendWrapper(null, xhr, options);
            assert(cleanUp.called);
            assert(initApp.called);
            assert(updateAuth.notCalled);
        });
    });
});

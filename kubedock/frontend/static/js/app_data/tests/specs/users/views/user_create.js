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

/* eslint-env mocha */
/* eslint-disable no-unused-expressions */
/* eslint indent: [1, 2] */
mocha.allowUncaught();

import {expect} from 'chai';
import sinon from 'sinon';
import {
  UserCreateView as View,
  __RewireAPI__ as ViewRewireAPI
} from 'app_data/users/views';
import {rewired} from 'app_data/tests/test_utils';


describe('users.views.UserCreateView', function(){
  describe('restoreByEmail', function(){

    let box, fakeUsers, App, utils, Model, resetRewired;
    let email = 'tesssst@cloudlinux.com';

    beforeEach(function(){
      [{App, Model, utils}, resetRewired] = rewired(ViewRewireAPI,
                                                    'App', 'Model', 'utils');
      box = sinon.sandbox.create();
      fakeUsers = {fetch: box.stub()};
      box.stub(App, 'getUserCollection').returns($.Deferred().resolve(fakeUsers));
      box.stub(App, 'navigate').returns(App);
      App.controller = {showUsers: box.stub()};
      box.stub(utils, 'notifyWindow');
      box.stub(View.prototype, 'initialize');
      box.stub(Model.UserModel, 'restoreByEmail');
    });
    afterEach(function(){ box.restore(); resetRewired(); });

    it('should undelete user after OK button was hit (full check)', function(done){
      fakeUsers.fetch.yieldsToAsync('success');
      Model.UserModel.restoreByEmail.returns($.Deferred().resolve().promise());
      box.stub(utils, 'modalDialog', (options) => _.defer(options.footer.buttonOk));

      new View().restoreByEmail(email);
      expect(App.getUserCollection).to.have.been.calledOnce;

      App.getUserCollection.firstCall.returnValue.done(() => {
        expect(utils.modalDialog).to.have.been.calledOnce;
        let options = utils.modalDialog.firstCall.args[0];
        expect(options).to.have.property('title', 'User exists');
        expect(options).to.have.deep.property('footer.buttonOk');
        expect(options).to.have.deep.property('footer.buttonCancel');
        _.defer(() => {
          expect(Model.UserModel.restoreByEmail).to.have.been.calledOnce
            .and.calledWith(email);
          Model.UserModel.restoreByEmail.firstCall.returnValue.done(function(){
            expect(utils.notifyWindow).to.have.been.calledOnce;
            expect(utils.notifyWindow.firstCall.args[1]).to.equal('success');
            expect(App.navigate).to.have.been.calledOnce.and.calledWith('users');
            expect(App.controller.showUsers).to.have.been.calledOnce;
            done();
          });
        });
      });
    });

    it('should notify if undeleted failed', function(done){
      box.stub(utils, 'modalDialog', (options) => _.defer(options.footer.buttonOk));
      Model.UserModel.restoreByEmail.returns($.Deferred().reject().promise());

      new View().restoreByEmail(email);
      _.defer(() => {
        expect(fakeUsers.fetch).to.have.not.been.called;

        expect(utils.notifyWindow).to.have.been.calledOnce;
        expect(utils.notifyWindow.firstCall.args[1]).to.not.equal('success');
        let message = utils.notifyWindow.firstCall.args[0];
        expect(message).to.contain('Could not').and.contain(email);
        done();
      });
    });

    it('should forward to users list if Cancel button was hit', function(done){
      box.stub(utils, 'modalDialog', (options) => _.defer(options.footer.buttonCancel));

      new View().restoreByEmail(email);
      _.defer(() => {
        expect(Model.UserModel.restoreByEmail).to.have.not.been.called;
        expect(fakeUsers.fetch).to.have.not.been.called;
        expect(utils.notifyWindow).to.have.not.been.called;

        expect(App.navigate).to.have.been.calledOnce.and.calledWith('users');
        expect(App.controller.showUsers).to.have.been.calledOnce;
        done();
      });
    });

  });

  describe('onSave', function(){

    let box, fakeUsers, App, utils, resetRewired;
    let userData = {email: 'tesssst@cloudlinux.com', username: 'test-uname'};

    beforeEach(function(){
      [{App, utils}, resetRewired] = rewired(ViewRewireAPI, 'App', 'utils');
      box = sinon.sandbox.create();
      fakeUsers = {add: sinon.stub()};
      box.stub(App, 'navigate').returns(App);
      box.stub(App, 'getUserCollection').returns($.Deferred().resolve(fakeUsers).promise());
      box.stub(View.prototype, 'initialize');
      box.stub(View.prototype, 'validate').returns($.Deferred().resolve().promise());
      box.stub(View.prototype, 'restoreByEmail');
      box.stub(View.prototype, 'getData').returns(userData);
      View.prototype.model = {
        save: box.stub(),
        get: box.stub().withArgs('username').returns(userData.username)};
      box.stub(utils.preloader, 'hide');
      box.stub(utils.preloader, 'show');
      box.stub(utils, 'notifyWindow');
    });
    afterEach(function(){ box.restore(); resetRewired(); });

    it('should forward to users list and show notification (full check)', function(done){
      View.prototype.model.save.returns($.Deferred().resolve().promise());
      let view = new View();
      view.onSave();

      _.defer(() => {
        expect(App.getUserCollection).to.have.been.calledOnce;
        expect(view.validate).to.have.been.calledOnce.and.calledWith(true);
        expect(utils.preloader.show).to.have.been.calledOnce.and.calledBefore(view.model.save);
        expect(view.model.save).to.have.been.calledOnce.and.calledWith(userData, {wait: true});

        expect(utils.preloader.hide).to.have.been.calledOnce;
        expect(fakeUsers.add).to.have.been.calledOnce.and.calledWith(view.model);
        expect(App.navigate).to.have.been.calledOnce.and.calledWith('users', {trigger: true});
        expect(utils.notifyWindow).to.have.been.calledOnce;
        expect(utils.notifyWindow.firstCall.args[1]).to.be.equal('success');
        done();
      });
    });

    it('should undelete in case of BillingError "user exists"', function(done){
      View.prototype.model.save.returns($.Deferred().reject({
        responseJSON: {type: 'BillingError', data: 'user exists email'},
      }).promise());
      let view = new View();
      view.onSave();

      _.defer(() => {
        expect(view.restoreByEmail).to.have.been.calledWith(userData.email);
        done();
      });
    });

  });
});

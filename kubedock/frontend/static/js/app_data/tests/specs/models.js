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
import Model from 'app_data/model';
import App from 'app_data/app';


describe('model.UserModel', function(){
  describe('restoreByEmail', function(){

    let box;
    let email = 'tesssst@cloudlinux.com';

    beforeEach(function(){
      box = sinon.sandbox.create();
      box.stub(Backbone.Model.prototype, 'save');
      box.stub(App, 'getUserCollection');
    });
    afterEach(function(){ box.restore(); });

    it('should undelete user and refetch user collection', function(done){
      Backbone.Model.prototype.save.returns($.Deferred().resolve().promise());
      App.getUserCollection.returns($.Deferred().resolve().promise());
      let promise = Model.UserModel.restoreByEmail(email);

      expect(Backbone.Model.prototype.save).to.have.been.calledOnce;
      expect(App.getUserCollection).to.have.been
        .calledAfter(Backbone.Model.prototype.save)
        .and.calledWith({updateCache: true});
      promise.then(() => done(), () => done('should be fulfilled'));
    });

    it('should reject in case of failed "undelete"', function(done){
      Backbone.Model.prototype.save.returns($.Deferred().reject().promise());
      Model.UserModel.restoreByEmail(email)
        .then(() => done('should be rejected'), () => done());
    });

    it('should reject in case of failed refetch', function(done){
      Backbone.Model.prototype.save.returns($.Deferred().resolve().promise());
      App.getUserCollection.returns($.Deferred().reject().promise());
      Model.UserModel.restoreByEmail(email)
        .then(() => done('should be rejected'), () => done());
    });
  });
});

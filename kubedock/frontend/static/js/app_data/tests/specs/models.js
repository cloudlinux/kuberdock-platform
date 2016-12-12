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

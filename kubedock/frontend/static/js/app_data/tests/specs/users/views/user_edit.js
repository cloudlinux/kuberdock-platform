/* eslint-env mocha */
/* eslint-disable no-unused-expressions */
mocha.allowUncaught();

import {expect} from 'chai';
import sinon from 'sinon';
import {
  UsersEditView as View,
  UserFormBaseView as FormView
} from 'app_data/users/views';
import Model from 'app_data/model';

describe('users.views.UsersEditView', function(){
    describe('isEqual && toggleShowAddBtn', function(){
        let sandbox = sinon.sandbox.create();

        afterEach(function () {
            sandbox.restore();
        });

        it('should hide "Save button" if all fields are not changed', function() {
            let fakeUser = {
                    active : true,
                    email  : 'example@example.com',
                    first_name : 'First name',
                    last_name : 'Last name',
                    middle_initials : 'Middle name',
                    rolename : 'User',
                    suspended : false,
                    timezone : 'GMT (+00:00)',
                    username : 'testUser',
                    package : 'Standard package'
                },
                view = new View({
                    model : new Model.UserModel(fakeUser)
                });

            view.constructor.__super__.ui = {
                'user_status'     : {val:sandbox.stub().returns('1')},
                'email'           : {val:sandbox.stub().returns('example@example.com')},
                'first_name'      : {val:sandbox.stub().returns('First name')},
                'last_name'       : {val:sandbox.stub().returns('Last name')},
                'middle_initials' : {val:sandbox.stub().returns('Middle name')},
                'password'        : {val:sandbox.stub().returns('')},
                'password_again'  : {val:sandbox.stub().returns('')},
                'package_select'  : {val:sandbox.stub().returns('Standard package')},
                'role_select'     : {val:sandbox.stub().returns('User')},
                'user_suspend'    : {prop:sandbox.stub().returns(false)},
                'timezone'        : {val:sandbox.stub().returns('GMT (+00:00)')},
                'username'        : {val:sandbox.stub().returns('testUser')},
                'user_add_btn'    : {
                                        show:sandbox.stub().returns(true),
                                        hide: sandbox.stub().returns(true)},
            };
            var ui = view.constructor.__super__.ui;

            view.toggleShowAddBtn();
            expect(view.isEqual()).to.be.equal(true);
            expect(ui.user_add_btn.hide.called).to.be.true;
            expect(ui.user_add_btn.show.called).to.be.false;
        });


        it('should show "Save button" if eny fields are changed', function() {
            let fakeUser = {
                    active : true,
                    email  : 'example@example.com',
                    first_name : 'First name',
                    last_name : 'Last name',
                    middle_initials : 'Middle name',
                    rolename : 'User',
                    suspended : false,
                    timezone : 'GMT (+00:00)',
                    username : 'testUser',
                    package : 'Standard package'
                },
                view = new View({
                    model : new Model.UserModel(fakeUser)
                });

            view.constructor.__super__.ui = {
                'user_status'     : {val:sandbox.stub().returns('1')},
                'email'           : {val:sandbox.stub().returns('example@example.com')},
                'first_name'      : {val:sandbox.stub().returns('First name')},
                'last_name'       : {val:sandbox.stub().returns('Last name')},
                'middle_initials' : {val:sandbox.stub().returns('Middle name')},
                'password'        : {val:sandbox.stub().returns('')},
                'password_again'  : {val:sandbox.stub().returns('')},
                'package_select'  : {val:sandbox.stub().returns('Standard package')},
                'role_select'     : {val:sandbox.stub().returns('User')},
                'user_suspend'    : {prop:sandbox.stub().returns(false)},
                'timezone'        : {val:sandbox.stub().returns('GMT (+00:00)')},
                'username'        : {val:sandbox.stub().returns('testUser')},
                'user_add_btn'    : {
                                        show:sandbox.stub().returns(true),
                                        hide: sandbox.stub().returns(true)},
            };
            let ui = view.constructor.__super__.ui,
                objKeys = Object.keys(view.constructor.__super__.ui),
                clearObjKeys = _.without(objKeys, 'user_add_btn', 'user_suspend'),
                randomKey = clearObjKeys[_.random(0, clearObjKeys.length - 1)];

            ui[randomKey].val.returns(true);
            view.toggleShowAddBtn();
            expect(view.isEqual()).to.be.equal(false);
            expect(ui.user_add_btn.hide.called).to.be.false;
            expect(ui.user_add_btn.show.called).to.be.true;
        });
    });
});

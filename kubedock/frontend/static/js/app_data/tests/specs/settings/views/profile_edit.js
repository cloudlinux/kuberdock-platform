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
mocha.allowUncaught();

import {expect} from 'chai';
import sinon from 'sinon';
import { ProfileEditView as View } from 'app_data/settings/views';
import Model from 'app_data/model';

describe('settings.views.ProfileEditView', function(){
    describe('isEqual && toggleShowSaveButton', function(){
        let sandbox = sinon.sandbox.create();

        afterEach(function () { sandbox.restore(); });

        it('should hide "Save button" if all fields are not changed', function() {
            let fakeModel = {
                    'first_name'      : 'a',
                    'last_name'       : 'b',
                    'middle_initials' : 'c',
                    'email'           : 'example@example.com',
                    'password'        : '',
                    'password_again'  : '',
                    'timezone'        : 'GMT',
                },
                view = new View({
                    model : new Model.CurrentUserModel(fakeModel)
                });
            view.model.in_edit = true;
            view.ui = {
                'first_name'      : {val:sandbox.stub().returns('a')},
                'last_name'       : {val:sandbox.stub().returns('b')},
                'middle_initials' : {val:sandbox.stub().returns('c')},
                'email'           : {val:sandbox.stub().returns('example@example.com')},
                'password'        : {val:sandbox.stub().returns('')},
                'password_again'  : {val:sandbox.stub().returns('')},
                'timezone'        : {val:sandbox.stub().returns('GMT')},
                'save'            : {show:sandbox.stub().returns(true),
                                     hide: sandbox.stub().returns(true)}
            };

            view.toggleShowSaveButton();
            expect(view.isEqual()).to.be.equal(true);
            expect(view.ui.save.hide.called).to.be.true;
            expect(view.ui.save.show.called).to.be.false;
        });

        it('should return "false" if any fields are changed', function() {
            let fakeModel = {
                    'first_name'      : 'a',
                    'last_name'       : 'b',
                    'middle_initials' : 'c',
                    'email'           : 'example@example.com',
                    'password'        : '',
                    'password_again'  : '',
                    'timezone'        : 'GMT'
                },
                view = new View({
                    model : new Model.CurrentUserModel(fakeModel)
                });
            view.ui = {
                'first_name'      : {val:sandbox.stub().returns('a')},
                'last_name'       : {val:sandbox.stub().returns('b')},
                'middle_initials' : {val:sandbox.stub().returns('c')},
                'email'           : {val:sandbox.stub().returns('example@example.com')},
                'password'        : {val:sandbox.stub().returns('')},
                'password_again'  : {val:sandbox.stub().returns('')},
                'timezone'        : {val:sandbox.stub().returns('GMT')},
                'save'            : {show:sandbox.stub().returns(true),
                                     hide: sandbox.stub().returns(true)}
            };

            let objKeys = Object.keys(view.ui),
                clearObjKeys = _.without(objKeys, 'save'),
                randomKey = clearObjKeys[_.random(0, clearObjKeys.length - 1)];

            view.ui[randomKey].val.returns('testValue');
            view.toggleShowSaveButton();
            expect(view.isEqual()).to.be.equal(false);
            expect(view.ui.save.hide.called).to.be.false;
            expect(view.ui.save.show.called).to.be.true;
        });
    });
});

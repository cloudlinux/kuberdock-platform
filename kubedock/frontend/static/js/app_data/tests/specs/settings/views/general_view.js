/* eslint-env mocha */
/* eslint-disable no-unused-expressions */
mocha.allowUncaught();

import {expect, assert} from 'chai';
import sinon from 'sinon';
import {
  GeneralView as View,
  __RewireAPI__ as ViewRewireAPI
} from 'app_data/settings/views';
import {rewired} from 'app_data/tests/test_utils';
import Model from 'app_data/model';

describe('settings.views.GeneralView', function(){
    describe('validate', function(){
        let notify, utils, resetRewired;
        let sandbox = sinon.sandbox.create();

        beforeEach(function(){
            [{utils}, resetRewired] = rewired(ViewRewireAPI, 'utils');

            notify = sandbox.stub(utils, 'notifyWindow');
        });

        afterEach(function () {
            sandbox.restore();
            resetRewired();
        });

        it('billing settings WHMCS - any field is empty ', function() {
            let fakeCollection = [
                    {name: 'billing_type', value: 'WHMCS'},
                    {name:  'billing_url', value: 'test' },
                    {name:  'billing_username', value: 'test' },
                    {name:  'billing_password', value: 'test' }
                ],
                view = new View({
                    collection: new Model.SettingsCollection(fakeCollection)
                });
            expect(view.validate()).to.be.equal(true);
            fakeCollection[_.random(1, fakeCollection.length - 1)].value = '';
            view.collection = new Model.SettingsCollection(fakeCollection);
            expect(view.validate()).to.be.equal(false);
            assert(notify.calledWith('All fields are required'));
        });

        it('dns management system Cpanel - any field is empty ', function() {
            let fakeCollection = [
                    {name: 'dns_management_system', value: 'cpanel_dnsonly'},
                    {name:  'dns_management_cpanel_dnsonly_host', value: 'test' },
                    {name:  'dns_management_cpanel_dnsonly_user', value: 'test' },
                    {name:  'dns_management_cpanel_dnsonly_token', value: 'test' }
                ],
                view = new View({
                    collection: new Model.SettingsCollection(fakeCollection)
                });
            expect(view.validate()).to.be.equal(true);
            fakeCollection[_.random(1, fakeCollection.length - 1)].value = '';
            view.collection = new Model.SettingsCollection(fakeCollection);
            expect(view.validate()).to.be.equal(false);
            assert(notify.calledWith('All fields are required'));
        });

        it('dns management system AWS - any field is empty ', function() {
            let fakeCollection = [
                    {name: 'dns_management_system', value: 'aws_route53'},
                    {name:  'dns_management_aws_route53_id', value: 'test' },
                    {name:  'dns_management_aws_route53_secret', value: 'test' }
                ],
                view = new View({
                    collection: new Model.SettingsCollection(fakeCollection)
                });
            expect(view.validate()).to.be.equal(true);
            fakeCollection[_.random(1, fakeCollection.length - 1)].value = '';
            view.collection = new Model.SettingsCollection(fakeCollection);
            expect(view.validate()).to.be.equal(false);
            assert(notify.calledWith('All fields are required'));
        });

        it('dns management system Cloudflare - any field is empty ', function() {
            let fakeCollection = [
                    {name: 'dns_management_system', value: 'cloudflare'},
                    {name:  'dns_management_cloudflare_email', value: 'test' },
                    {name:  'dns_management_cloudflare_token', value: 'test' },
                    {name:  'dns_management_cloudflare_certtoken', value: 'test' }
                ],
                view = new View({
                    collection: new Model.SettingsCollection(fakeCollection)
                });
            expect(view.validate()).to.be.equal(true);
            fakeCollection[_.random(1, fakeCollection.length - 1)].value = '';
            view.collection = new Model.SettingsCollection(fakeCollection);
            expect(view.validate()).to.be.equal(false);
            assert(notify.calledWith('All fields are required'));
        });
    });
});

/* eslint-env mocha */
mocha.allowUncaught();

import {expect} from 'chai';
import sinon from 'sinon';
import {
  IppoolCreateSubnetworkView as View,
   __RewireAPI__ as ViewRewireAPI
} from 'app_data/ippool/views';
import {rewired} from 'app_data/tests/test_utils';

describe('ippool.views.IppoolCreateSubnetworkView', function(){
    describe('validate', function(){

        let box, utils, resetRewired;

        beforeEach(function(){
          [{utils}, resetRewired] = rewired(ViewRewireAPI, 'utils');
          box = sinon.sandbox.create();
          box.stub(utils, 'notifyInline');
        });
        afterEach(function(){ box.restore(); resetRewired(); });

        let view,
            badNetworks = [
                '0',
                '192',
                '192.1',
                '192.168.',
                '192.168.',
                '192.168.255',
                '192.168.0.1',
                '192.168.0.1/',
                '192.168.0.1/0',
                '192.168.0.1/33',
                '255.168.0.1/33'
            ],
            goodNetworks = [
                '10.10.0.0/26',
                '192.168.0.0/30',
                '255.168.0.1/32'
            ];

        for (let value of badNetworks) {
            it(`should return "false" to networks "${value}"`, function() {
                let fakeData = {
                        network : value,
                        autoblock : ''
                    };

                view = new View();
                view.ipPoolMode = true;
                expect(view.validate(fakeData)).to.be.equal(false);
                expect(utils.notifyInline).to.have.been.calledOnce;
            });
        }

        it('should return "false" if autoblock is incorrect', function() {
            let fakeData = {
                    network : '192.168.0.1/32',
                    autoblock : '312312'
                };

            view = new View();
            view.ipPoolMode = true;
            expect(view.validate(fakeData)).to.be.equal(false);
            expect(utils.notifyInline).to.have.been.calledOnce;
        });

        for (let value of goodNetworks) {
            it(`should return "true" to networks "${value}"`, function() {
                let fakeData = {
                        network : value,
                        autoblock : ''
                    };

                view = new View();
                view.ipPoolMode = true;
                expect(view.validate(fakeData)).to.be.equal(true);
            });
        }

        it('should return "true" if all params is correct', function() {
            let fakeData = {
                    network : '192.168.0.0/30',
                    autoblock : '192.168.0.1'
                };

            view = new View();
            view.ipPoolMode = true;
            expect(view.validate(fakeData)).to.be.equal(true);
        });
    });

    describe('correctSubnet', function(){
        let view,
            fakeNetwork = [
                '011cfd',
                '192.$#',
                '1*2.1',
                '192.168.das',
                '192.168.1w',
                '192.168.255w',
                '192.168.0.1ccs',
                '192.168.0.1/sdd',
                '192.168.0.1/0dsd',
                '19s2.168.0.1/33',
                '255.1s68.0.1/33'
            ];

        for (let value of fakeNetwork) {
            it(`should return the same network to "${value}"`, function() {
                view = new View();
                expect(view.correctSubnet(value)).to.be.equal(value);
            });
        }

        it('should return the correct network "192.168.0.1/32"', function() {
            view = new View();
            expect(view.correctSubnet('192.168.0.01/32')).to.be.equal('192.168.0.1/32');
        });
    });
});

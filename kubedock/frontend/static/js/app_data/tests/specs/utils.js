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
mocha.allowUncaught();

import chai from 'chai';
import * as utils from 'app_data/utils';
import {__RewireAPI__ as UtilsRewireAPI} from 'app_data/utils';


describe('Utils Tests', function(){

    describe('hasScroll Test', function() {
        after(function () {
            $('body').show().height('auto');
        });

        it("hasScroll", function () {
            $('body').show().height(10000);
            chai.expect(utils.hasScroll()).to.be.equal(true);
            $('body').height(0).hide();
            chai.expect(utils.hasScroll()).to.be.equal(false);
        });

    });

    describe('scrollTo Test', function() {
        after(function(){
            $('body').height('auto');
            $('#toScroll').remove();
        });

        it("scrollTo", function (done) {
            var $toScroll = $('<div id="toScroll" style="position: absolute; ' +
                'top:300px">test</div>').appendTo('body');
            $('body').height(10000);
            utils.scrollTo($toScroll);
            window.setTimeout(function () { // if next expect assert
                chai.expect($('body').scrollTop()).to.be.equal($toScroll.offset().top - 50);
                done();
            }, 550);
        });

    });

    it("toHHMMSS", function(){
        chai.expect(
            utils.toHHMMSS(0)
        ).to.be.equal('0:00:00');
        chai.expect(
            utils.toHHMMSS(1)
        ).to.be.equal('0:00:01');
        chai.expect(
            utils.toHHMMSS(60)
        ).to.be.equal('0:01:00');
        chai.expect(
            utils.toHHMMSS(60 * 60)
        ).to.be.equal('1:00:00');
    });

    it("dateYYYYMMDD", function() {
        chai.expect(
            utils.dateYYYYMMDD(new Date(2016, 8, 1))
        ).to.be.equal('2016-09-01');
        chai.expect(
            utils.dateYYYYMMDD(new Date(2016, 8, 31))
        ).to.be.equal('2016-10-01');
        chai.expect(
            utils.dateYYYYMMDD(new Date(2016, 8, 31), '.')
        ).to.be.equal('2016.10.01');
    });

    // example test with mocked import
    it('dateYYYYMMDD should call moment.js', function(done){
        let testDate = new Date();
        let momentMock = function(date){
            chai.expect(date).to.be.equal(testDate);
            return {
                format(formatString){
                    chai.expect(formatString).to.be.equal('YYYY-MM-DD');
                    done();
                }
            };
        };
        UtilsRewireAPI.__with__({moment: momentMock})(function(){
            utils.dateYYYYMMDD(testDate);
        });
    });

    it("localizeDatetime", function () {
        var date = new Date(Date.UTC(2016, 8, 1, 0, 0, 0));
        chai.expect(
            utils.localizeDatetime({
                'dt': date,
                'tz': 0,
                'formatString': null
            }
            )
        ).to.be.equal('2016-09-01 00:00:00 (+00:00)');
        chai.expect(
            utils.localizeDatetime({
                'dt': date,
                'tz': 'Europe/Moscow',
                'formatString': null
            }
            )
        ).to.be.equal('2016-09-01 03:00:00 (+03:00)');
        chai.expect(
            utils.localizeDatetime(date, 'Europe/Moscow', 'YYYY-MM-DD HH:mm:ss')
        ).to.be.equal('2016-09-01 03:00:00');
    });

    it("removeURLParameter", function () {
        chai.expect(
            utils.removeURLParameter("http://site.com/url?param1=a;param2=2#hash", 'param2')
        ).to.be.equal('http://site.com/url?param1=a#hash');
        chai.expect(
            utils.removeURLParameter("http://site.com/url?param1=a&param2=2#hash", 'param1')
        ).to.be.equal('http://site.com/url?param2=2#hash');
        chai.expect(
            utils.removeURLParameter("http://site.com/url?param1=a;param2=2", 'param2')
        ).to.be.equal('http://site.com/url?param1=a');
        chai.expect(
            utils.removeURLParameter("http://site.com/url?param1=a;param2=2", 'param3')
        ).to.be.equal('http://site.com/url?param1=a&param2=2');
        chai.expect(
            utils.removeURLParameter("http://site.com/url?param%201=a;param2=2", 'param 1')
        ).to.be.equal('http://site.com/url?param2=2');
    });

    it("deepClone", function () {
        chai.expect(
            utils.deepClone("string")
        ).to.be.equal("string");
        chai.expect(
            utils.deepClone(new Date(2016, 8, 2, 0, 0, 0))
        ).to.be.equalDate(new Date(2016, 8, 2, 0, 0, 0));
        chai.expect(
            utils.deepClone(function () { return 42; })()
        ).to.be.equal(42);
        chai.expect(
            utils.deepClone([1, 'a'])
        ).to.deep.equal([1, 'a']);
        chai.expect(
            utils.deepClone([1, 'a'])
        ).to.deep.equal([1, 'a']);
        chai.expect(
            utils.deepClone({key1: 'val1', key2: 'val2'})
        ).to.deep.equal({key1: 'val1', key2: 'val2'});
        chai.expect(
            utils.deepClone([{key1: 'val1', key2: 'val2'}, {k3:'v3', k4:'v4'}])
        ).to.deep.equal([{key1: 'val1', key2: 'val2'}, {k3:'v3', k4:'v4'}]);

    });

    describe('modalDialog Tests', function() {
        // from templates/index.html
        var modalDialogHtml = '\
            <div class="modal fade">\
                <div class="modal-dialog">\
                    <div class="modal-content">\
                        <div class="modal-header">\
                            <button type="button" class="close" data-dismiss="modal"\
                             aria-label="Close">\
                                <span aria-hidden="true"></span>\
                            </button>\
                            <h4 class="modal-title"></h4>\
                        </div>\
                        <div class="modal-body"></div>\
                        <div class="modal-footer buttons">\
                            <button type="button" class="blue" data-dismiss="modal">ok</button>\
                        </div>\
                    </div>\
                </div>\
            </div>\
        ';
        var $modal;

        before(function () {
            $modal = $(modalDialogHtml).appendTo('body');
        });

        after(function () {
            $modal.remove();
        });

        it("modalDialog", function () {
            $('.modal-backdrop').remove();
            var $modal2 = utils.modalDialog({
                title: "title",
                body: "body",
                show: true,
                footer: {
                    buttonOk: function(){},
                    buttonCancel: true
                }
            });
            chai.expect($modal2.html()).to.be.equal($modal.html());
            chai.expect($modal2.find('h4.modal-title').html()).to.be.equal('title');
            chai.expect($modal2.find('div.modal-body').html()).to.be.equal('body');
            chai.expect($modal2).to.not.have.class('in');

            // test button types
            var buttonTypes = {'delete':'Delete',
                                'saveAnyway':'Save Anyway',
                                'deleteAnyway': 'Delete Anyway',
                                'anyOtherValue': 'Ok'
                               };

            for (var buttonType in buttonTypes){
                $('.modal-backdrop').remove();
                $modal2 = utils.modalDialog({
                    title: "title",
                    body: "body",
                    show: false,
                    type: buttonType,
                    footer: {
                        buttonOk: function(){},
                        buttonCancel: true
                    }
                });
                chai.expect($modal2.find('button.btn.blue').html()).to.be.equal(
                    buttonTypes[buttonType]
                );

            }
            // hide cancle
            $('.modal-backdrop').remove();
            $modal2 = utils.modalDialog({
                title: "title",
                body: "body",
                show: false,
                footer: {
                    buttonOk: function(){},
                    buttonCancel: false
                }
            });
            chai.expect($modal2.find('button.btn').length).to.be.equal(1);

        });

        it("modalDialogDelete", function () {
            $('.modal-backdrop').remove();
            var $modal2 = utils.modalDialogDelete({
                title: "title",
                body: "body",
                show: false,
                footer: {
                    buttonOk: function(){},
                    buttonCancel: true
                }
            });
            chai.expect($modal2.find('button.btn.blue').html()).to.be.equal('Delete');
        });

    });


    describe("notifyWindow", function () {

        after(function(){ $('.notifyjs-wrapper').remove(); });

        it("notifyWindow", function (done) {

            // fake jqXHR message
            var fakejqXHR = {
                'responseJSON': {
                    'data': 'test message',
                    'status': 'ok'
                },
                'status': 200,
                getResponseHeader: function(contentType){ return 'text/html'; }
            };

            $.notify.defaults({autoHideDelay: 50, showDuration: 50, hideDuration: 50});

            utils.notifyWindow(fakejqXHR);
            chai.expect($('.notify-msg').html()).to.be.equal('test message');

            // test error codes
            var messageTemplate = 'It seems like something goes wrong (%error%). Reload page,' +
                ' try again later, or contact support if problem appears again.';

            delete fakejqXHR.responseJSON;

            fakejqXHR.status = 500;
            utils.notifyWindow(fakejqXHR);
            chai.expect($('.notify-msg').html()).to.be.equal(
                messageTemplate.replace('%error%', 'Internal server error')
            );

            fakejqXHR.status = 502;
            utils.notifyWindow(fakejqXHR);
            chai.expect($('.notify-msg').html()).to.be.equal(
                messageTemplate.replace('%error%', 'Server is unavailable')
            );

            fakejqXHR.status = 504;
            utils.notifyWindow(fakejqXHR);
            chai.expect($('.notify-msg').html()).to.be.equal(
                messageTemplate.replace('%error%', 'Timeout error')
            );

            // costom server message
            fakejqXHR.status = 501;
            fakejqXHR.statusText = 'Not Implemented';
            utils.notifyWindow(fakejqXHR);
            chai.expect($('.notify-msg').html()).to.be.equal(
                messageTemplate.replace('%error%', 'Not Implemented')
            );

            // string message
            utils.notifyWindow('string message', 'success');
            chai.expect($('.notify-msg').html()).to.be.equal('string message');
            chai.expect($('.notify-count').html()).to.be.equal('');
            // repeat message
            utils.notifyWindow('string message', 'success');
            chai.expect($('.notify-count').html()).to.be.equal('');

            // show notify count only for error messages
            utils.notifyWindow('error message', 'error');
            utils.notifyWindow('error message', 'error');
            chai.expect($('.notify-count').html()).to.be.equal('2');

            _.delay(() => {
                // all "success" notification should be closed automatically
                chai.expect($('.notify-msg').length).to.be.equal(5);
                utils.notifyWindowClose();  // close all errors too
                _.delay(() => {
                    chai.expect($('.notify-msg').length).to.be.equal(0);
                    done();
                }, 60);
            }, 160);
        });
    });


    // function readClipboard (){
    //     var val,
    //         $txa = $('<textarea />', {css: {position: 'fixed'}})
    //             .appendTo("body").focus();
    //
    //     if (window.clipboardData){
    //         val = window.clipboardData.getData('Text');
    //     } else
    //     if (document.execCommand('paste')){ // CH, FF, Edge, IE
    //         val = $txa.val();
    //     } else {
    //         val = prompt(  // eslint-disable-line no-alert
    //             'Paste from clipboard:\nCmd+V, Enter');
    //     }
    //     $txa.remove();
    //     return val;
    // }
    // it("copyLink", function () {
    //     /***
    //      * Copy link work only on user event.
    //      */
    //     this.timeout(15000);
    //     var testText = 'http://copied_url.com/url';
    //     utils.copyLink(testText, 'successMessage', 'messageState');
    //     var result = readClipboard();
    //     chai.expect(result).to.be.equal(testText);
    // });
});

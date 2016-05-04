define(['app_data/app', 'app_data/utils', 'marionette',
        'tpl!app_data/login/templates/login.tpl'],
    function(App, utils, Marionette, loginTpl){
        'use strict';
        var views = {};

        views.LoginView = Marionette.ItemView.extend({
            template: loginTpl,
            className: "login-page clearfix",

            ui: {
                'login': '.login',
                'username': '#login-form-username-field',
                'password': '#login-form-password-field',
            },

            events: {
                'click @ui.login': 'signIn',
                'keypress @ui.username': 'signIn',
                'keypress @ui.password': 'signIn',
            },

            initialize: function(options){ this.next = options.next || ''; },
            login: function(evt){
                if (evt.type === 'keypress' && evt.which !== 13)
                    return;  // not 'Enter' key

                var username = this.ui.username.val(),
                    password = this.ui.password.val();
                if (!username){
                    utils.notifyWindow('Please, enter useraname.');
                    this.ui.username.focus();
                } else if (!password) {
                    utils.notifyWindow('Please, enter password.');
                    this.ui.password.focus();
                }

                utils.preloader.show();
                var that = this;
                // TODO-JWT: instead of this, send request to /api/token2
                $.ajax({
                    url: '/login',
                    type: 'POST',
                    data: {
                        'login-form-username-field': username,
                        'login-form-password-field': password,
                    },
                }).fail(function(){
                    utils.preloader.hide();
                    // TODO-JWT: show error
                }).done(function(){
                    // TODO-JWT: save token in App.storage
                    App.prepareInitialData().done(function(){
                        App.eventHandler();
                        App.navigate(that.next, {trigger: true});
                        App.controller.showNotifications();
                        utils.preloader.hide();
                    });
                });
            },
            
            signIn: function(evt){
                evt.stopPropagation();
                if (evt.type === 'keypress' && evt.which !== 13) return;
                var username = this.ui.username.val().trim(),
                    password = this.ui.password.val().trim();
                this.triggerMethod('action:signin',
                    {username: username, password: password});
            }


        });

        return views;
});
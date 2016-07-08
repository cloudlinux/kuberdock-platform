define(['app_data/app', 'app_data/model', 'app_data/utils', 'marionette',
        'tpl!app_data/login/templates/login.tpl'],
    function(App, Model, utils, Marionette, loginTpl){
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
            signIn: function(evt){
                evt.stopPropagation();
                if (evt.type === 'keypress' && evt.which !== 13) return;
                var auth = {
                    username: this.ui.username.val().trim(),
                    password: this.ui.password.val().trim(),
                };

                if (!auth.username){
                    utils.notifyWindow('Please, enter useraname.');
                    this.ui.username.focus();
                    return;
                }
                if (!auth.password) {
                    utils.notifyWindow('Please, enter password.');
                    this.ui.password.focus();
                    return;
                }

                utils.preloader.show();
                var authModel = new Model.AuthModel(),
                    view = this;
                authModel.save(auth, {wait:true})
                    .always(utils.preloader.hide)
                    .done(function(){
                        utils.notifyWindowClose();
                        view.triggerMethod('action:signin', authModel);
                    })
                    .fail(function(xhr){
                        utils.notifyWindow(xhr.status === 401
                            ? 'Invalid credentials provided' : xhr);
                        view.ui.username.focus();
                    });
            }


        });

        return views;
});

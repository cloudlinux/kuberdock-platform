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

import Model from 'app_data/model';
import * as utils from 'app_data/utils';
import loginTpl from 'app_data/login/templates/login.tpl';

export const LoginView = Marionette.ItemView.extend({
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

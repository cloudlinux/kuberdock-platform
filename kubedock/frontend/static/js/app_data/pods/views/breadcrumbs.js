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

define([
    'app_data/app', 'app_data/utils',
    'app_data/breadcrumbs/views',
    'bootstrap-editable'
], function(App, utils, Breadcrumbs){

    var views = {};

    views.EditableName = Breadcrumbs.Text.extend({
        class: 'peditable',

        save: function(name){
            var successMsg = 'New pod name "' + name + '" is saved';
            this.model.set({name: name});
            if (this.model.isNew()){
                utils.notifyWindow(successMsg, 'success');
            } else {
                utils.preloader.show();
                this.model.command('set', {name: name})
                    .always(utils.preloader.hide).fail(utils.notifyWindow)
                    .done(function(){ utils.notifyWindow(successMsg, 'success'); });
            }
        },

        onRender: function(){
            var that = this;
            App.getPodCollection().done(function(podCollection){
                that.$el.editable({
                    type: 'text',
                    mode: 'inline',
                    value: that.model.get('name'),
                    success: function(response, newValue){ that.save(newValue); },
                    validate: function(newValue){
                        newValue = newValue.trim();

                        var msg;
                        if (!newValue)
                            msg = 'Please, enter pod name.';
                        else if (newValue.length > 63)
                            msg = 'The maximum length of the Pod name must' +
                                  ' be less than 64 characters.';
                        else if (_.without(
                            podCollection.where({name: newValue}), that.model).length)
                            msg = 'Pod with name "' + newValue +
                                  '" already exists. Try another name.';
                        if (msg){
                            // TODO: style for ieditable error messages
                            // (use it instead of notifyWindow)
                            utils.notifyWindow(msg);
                            return ' ';
                        }
                    }
                });
            });
        },
    });

    return views;
});

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
    'app_data/app', 'marionette',
    'app_data/misc/templates/message_list.tpl',
    'app_data/misc/templates/message_list_item.tpl',
    'app_data/misc/templates/page_not_found.tpl',
], function(
    App, Marionette,
    messageListTpl, messageListItemTpl,
    pageNotFoundTpl
){

    var views = {};

    views.MessageListItem = Marionette.ItemView.extend({
        template: messageListItemTpl,
        className: function(){
            return this.model.get('type') || 'info';
        }
    });

    views.MessageList = Marionette.CompositeView.extend({
        template: messageListTpl,
        childView: views.MessageListItem,
        childViewContainer: '#message-body',
        className: 'message-box',

        ui: {
            'toggler': '.toggler',
            'messageBody': '#message-body'
        },

        events: {
            'click @ui.toggler': 'toggleBody'
        },

        toggleBody: function(evt){
            evt.stopPropagation();
            if (this.ui.messageBody.hasClass('visible')) {
                this.ui.messageBody.show();
            } else {
                this.ui.messageBody.hide();
            }
            this.ui.toggler.toggleClass('move');
            this.ui.messageBody.toggleClass('visible');
            this.ui.messageBody.parent().toggleClass('visible');
        },

        onShow: function(){
            if (this.collection.where({type: 'warning'}).length > 0 ) {
                this.ui.toggler.click();
            }
        }
    });

    views.PageNotFound = Marionette.ItemView.extend({
        template: pageNotFoundTpl
    });

    return views;
});

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

define(['app_data/app', 'app_data/paginator/paginator.tpl'], function(App, paginatorTpl){

    var paginator = {};

    paginator.PaginatorView = Backbone.Marionette.ItemView.extend({
        template: paginatorTpl,

        initialize: function(options){
            this.model = new Backbone.Model({
                v: options.view,
                c: options.view.collection
            });
            this.listenTo(options.view.collection, 'update reset', this.render);
        },

        events: {
            'click li.pseudo-link' : 'paginateIt'
        },

        paginateIt: function(evt){
            evt.stopPropagation();
            var tgt = $(evt.target);
            if (tgt.hasClass('disabled')) return;
            if (tgt.hasClass('paginatorPrev')) this.model.get('c').getPreviousPage();
            else if (tgt.hasClass('paginatorNext')) this.model.get('c').getNextPage();
            this.model.get('v').render();
            this.render();
        },
    });

    return paginator;

});

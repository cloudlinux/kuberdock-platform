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
import breadcrumbLayoutTpl from 'app_data/breadcrumbs/templates/breadcrumb_layout.tpl';
import breadcrumbControlsTpl from 'app_data/breadcrumbs/templates/breadcrumb_controls.tpl';
import 'tooltip';

/**
 * Common breadcrumbs layout.
 *
 * It contains default region called "controls", for controls on the right
 * side of breadcrumbs, and list of regions for provided points.
 *
 * @param {string[]} options.points - list of strings. Each point will make
 *  a region to attach link, plain text or enything else.
 */
export const Layout = Backbone.Marionette.LayoutView.extend({
    template: breadcrumbLayoutTpl,
    className: 'breadcrumbs-wrapper',
    tagName: 'div',
    regions: function(options){
        var regions = {controls: '.control-group'};
        _.each(options.points, function(point, i){
            regions[point] = '.breadcrumb li:eq(' + i + ')';
        });
        return regions;
    },

    initialize: function(options){ this.points = options.points; },
    templateHelpers: function(){ return {points: this.points}; },
});

/**
 * Use this to add plain text beadcrumb-point
 *
 * @param options.text
 */
export const Text = Backbone.Marionette.ItemView.extend({
    tagName: 'span',
    initialize: function() {
        this.template = _.wrap(this.getOption('text'), _.escape);
    },
});

/**
 * Use this to add link beadcrumb-point
 *
 * @param options.text
 * @param options.href
 */
export const Link = Text.extend({
    tagName: 'a',
    attributes: function(){ return {href: this.getOption('href')}; },
});


/**
 * Base view for controls in the breadcrumbs.
 *
 * @param {Model.BreadcrumbsControls} options.model
 * or plain attributes of model:
 * @param {boolean} options.search - to show search or not
 * @param {boolean|Object} options.button -
 *      false - to hide button, or
 *      {id, title, href} - button spec
 */
export const Controls = Backbone.Marionette.ItemView.extend({
    template: breadcrumbControlsTpl,
    tagName: 'div',

    ui: {
        'searchButton' : '.nav-search',
        'search'       : 'input#nav-search-input',
        'tooltip'      : '[data-toggle="tooltip"]'
    },

    events: {
        'keyup @ui.search'      : 'search',
        'click @ui.searchButton': 'showSearch',
        'blur @ui.search'       : 'closeSearch',
    },

    initialize: function(options){
        this.model = options.model || new Model.BreadcrumbsControls(options);
    },

    onRender: function() {
        this.ui.tooltip.tooltip();
    },

    search: function(evt){
        this.trigger('search', evt.target.value.trim());
    },

    showSearch: function(){
        this.ui.searchButton.addClass('active');
        this.ui.search.focus();
    },

    closeSearch: function(){
        if (this.ui.search.val().trim() === '')
            this.ui.searchButton.removeClass('active');
    }
});

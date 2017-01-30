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
    'app_data/app',
    'app_data/pa/templates/header_for_anon.tpl',
    'app_data/pa/templates/plans_layout.tpl',
    'app_data/pa/templates/plans/list.tpl',
    'app_data/pa/templates/plans/item.tpl',

    'app_data/pa/templates/settings_layout.tpl',
    'app_data/pa/templates/settings/resource_fields.tpl',
    'app_data/pa/templates/settings/resource_item.tpl',
], function(
    App,
    headerForAnonTpl,
    plansLayoutTpl,
    plansListTpl,
    plansItemTpl,

    settingsLayoutTpl,
    settingsResourceFieldsTpl,
    settingsResourceItemTpl

){
    'use strict';
    var views = {};

    views.HeaderForAnon = Marionette.ItemView.extend({
        template: headerForAnonTpl,
        tagName: 'header',
    });

    views.PlansLayout = Marionette.LayoutView.extend({
        template: plansLayoutTpl,
        regions: {
            breadcrumbs: '.pa-breadcrumbs',
            plans: '.pa-plans',
        },
        className: 'plans-change',

        childEvents: {
            'choosePackage' : 'choosePackage',
        },

        choosePackage: function(plan){
            this.trigger('choosePackage', plan.model.collection.indexOf(plan.model), plan.model);
        },
    });

    views.Plan = Marionette.ItemView.extend({
        template: plansItemTpl,
        className: function(){
            var className = 'plan';
            if (this.model.get('recommended')) className += ' recommended';
            return className;
        },
        ui: {
            showMore: '.show-more',
            planDetails: '.plan-details',
            chooseButton: '.choose-button',
        },
        events: {
            'click @ui.showMore': 'showMore',

        },
        triggers: {
            'click @ui.chooseButton': 'choosePackage',
        },

        initialize: function(options){
            this.model.set('current', false);
            this.pod = options.pod;
        },
        showMore: function(e){
            var target = $(e.target);
            target.toggleClass('rotate');
            this.ui.planDetails.slideToggle('fast');
        },
        choosePackage: function(){
            this.pod.cmdSwitchPackage(this.model.collection.indexOf(this.model))
                .done(_.bind(function(){
                    App.navigate('pods/' + this.pod.id, {trigger: true});
                }, this));
        },
    });

    views.PlansList = Marionette.CompositeView.extend({
        template: plansListTpl,
        childView: views.Plan,
        childViewContainer: '.plans',
        initialize: function(options){ this.pod = options.pod; },
        childViewOptions: function(){ return {pod: this.pod}; },
    });

    views.AppSettingsLayout = Marionette.LayoutView.extend({
        template: settingsLayoutTpl,
        regions: {
            resource: '#recource-fields',
        },

        ui: {
            submitButton: '#submit-button',
            backButton: '#back-button',
        },
        events: {
            'click @ui.submitButton': 'submitApp',
            'click @ui.backButton': 'returnToPackage',
        },

        submitApp: function(){
            var settings = this.resource.currentView.getValues();
            this.trigger('submitApp', settings);
        },
        returnToPackage: function() {
            this.trigger('choosePackage');
        }


    });

    views.SettingsResourceFieldsItem = Marionette.ItemView.extend({
        template: settingsResourceItemTpl,
        events: {
            'change input': 'updateValue'
        },
        updateValue: function(){
            this.model.set('value', this.$el.find('input').val());
        }

    });

    views.SettingsResourceList = Marionette.CompositeView.extend({
        template: settingsResourceFieldsTpl,
        childView: views.SettingsResourceFieldsItem,
        childViewContainer: '.body',

        getValues: function(){
            var data = {};
            this.collection.models.forEach(function (item) {
                data[item.get('name')] = item.get('value') != null
                    ? item.get('value') : item.get('default_value');
            });
            return data;
        }

    });


    return views;
});

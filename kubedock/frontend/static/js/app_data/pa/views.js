define([
    'app_data/app',
    'app_data/pa/templates/header_for_anon.tpl',
    'app_data/pa/templates/plans_layout.tpl',
    'app_data/pa/templates/plans/list.tpl',
    'app_data/pa/templates/plans/item.tpl',
], function(
    App,
    headerForAnonTpl,
    plansLayoutTpl,
    plansListTpl,
    plansItemTpl
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
        className: 'plans-change'
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
            'click @ui.chooseButton': 'choosePackage',
        },

        initialize: function(options){ this.pod = options.pod; },
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

    return views;
});

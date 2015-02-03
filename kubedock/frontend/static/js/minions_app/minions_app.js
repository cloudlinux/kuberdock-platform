"use strict";

var MinionsApp = new Backbone.Marionette.Application({
    regions: {
        contents: '#contents'
    }
});


MinionsApp.module('Data', function(Data, App, Backbone, Marionette, $, _){

    var unwrapper = function(response) {
        if (response.hasOwnProperty('data'))
            return response['data'];
        return response;
    };

    Data.MinionModel = Backbone.Model.extend({
        urlRoot: '/api/minions/',
        parse: unwrapper
    });

    Data.MinionsCollection = Backbone.PageableCollection.extend({
        url: '/api/minions/',
        model: Data.MinionModel,
        parse: unwrapper,
        mode: 'client',
        state: {
            pageSize: 10
        }
    });
});


MinionsApp.module('Views', function(Views, App, Backbone, Marionette, $, _){

    //=================Copy from app.js ===========================================================
    Views.PaginatorView = Backbone.Marionette.ItemView.extend({
        template: '#paginator-template',

        initialize: function(options) {
            this.model = new Backbone.Model({
                v: options.view,
                c: options.view.collection
            });
            this.listenTo(this.model.get('c'), 'remove', function(){
//                this.model.get('v').render();     //don't need, maybe in my case
                this.render();
            });
        },

        events: {
            'click li.pseudo-link': 'paginateIt'
        },

        paginateIt: function(evt){
            // TODO NEED MERGE ====================================================================
            evt.stopPropagation();
            var tgt = $(evt.target);
            var coll = this.model.get('c');
            if (tgt.hasClass('paginatorFirst')) coll.getFirstPage();
            else if (tgt.hasClass('paginatorPrev') && coll.hasPreviousPage()) coll.getPreviousPage();
            else if (tgt.hasClass('paginatorNext') && coll.hasNextPage()) coll.getNextPage();
            else if (tgt.hasClass('paginatorLast')) coll.getLastPage();
//            this.model.get('v').render();     //don't need, maybe in my case
            this.render();
        }
    });
    //=============================================================================================











    Views.MinionItem = Backbone.Marionette.ItemView.extend({
        template: '#minion-item-template',
        tagName: 'tr',

        events: {
            'click button#deleteMinion': 'deleteMinion',
            'click button#detailedMinion' : 'detailedMinion',
            'click button#upgradeMinion' : 'detailedMinion',
            'click button#detailedTroublesTab' : 'detailedTroublesTab'
        },

        deleteMinion: function(){
            this.model.destroy();   // no wait, because removed in any case
        },

        detailedMinion: function(){
            App.router.navigate('/detailed/' + this.model.id + '/settings/', {trigger: true});
        },

        detailedTroublesTab: function(){
            App.router.navigate('/detailed/' + this.model.id + '/troubles/', {trigger: true});
        }

    });

    Views.MinionsListView = Backbone.Marionette.CompositeView.extend({
        template: '#minions-list-template',
        childView: Views.MinionItem,
        childViewContainer: "tbody",

        events: {
            'click button#add_minion' : 'addMinion'
        },

        collectionEvents: {
            "remove": function () {this.render()}
        },

        templateHelpers: function(){
          return {
              totalMinions: this.collection.fullCollection.length
          }
        },

        addMinion: function(){
            App.router.navigate('/add/', {trigger: true});
        }
    });

















    // =========== Add minion wizard ====================================
    Views.MinionAddWizardLayout = Backbone.Marionette.LayoutView.extend({
        template: '#minion-add-layout-template',

        regions: {
            header: '#minion-header',
            find_step: '#minion-find-step',
            final_step: '#minion-final-step'
        }
    });

    Views.MinionFindStep = Backbone.Marionette.ItemView.extend({
        template: '#minion-find-step-template',

        ui: {
            'minion_name': 'input#minion_address',
            'spinner': '#address-spinner'
        },

        events:{
            'change @ui.minion_name': 'validateStep'
        },

        validateStep: function (evt) {
            var val = evt.target.value;
            if (val !== '') {
                var that = this;
                this.ui.spinner.spin({color: '#437A9E'});
                Backbone.ajax({ url:"/api/minions/checkhost/" + val }).done(function (data) {
                    that.state.set('isFinished', true);
                    that.state.set('ip', data.ip);
                    that.state.set('hostname', data.hostname);
                }).error(function(resp) {
                    that.state.set('isFinished', false);
                    alert(resp.responseJSON.status);
                });
                that.ui.spinner.spin(false);
            } else {
                this.state.set('isFinished', false);
            }
        },

        initialize: function () {
            this.state = new Backbone.Model({ isFinished: false });
        }
    });

    Views.MinionFinalStep = Backbone.Marionette.ItemView.extend({
        template: '#minion-final-step-template',

        ui: {
//            'minion_ssh': 'select#minion_ssh',
            'minion_add_btn': 'button#minion-add-btn'
        },

        events:{
//            'change @ui.minion_ssh': 'validateStep',
            'click @ui.minion_add_btn': 'complete'      // only if valid
        },

//        validateStep: function (evt) {
//            if (evt.target.value !== '') {
//                this.state.set('isFinished', true);
//            } else {
//                this.state.set('isFinished', false);
//            }
//        },

        complete: function () {
            var that = this;
            App.Data.minions.create({
                ip: this.state.get('ip'),
                hostname: this.state.get('hostname'),
                status: 'pending',
                annotations: {'sw_version': 'v1.1'}, // TODO implement real
                labels: {'tier': 'testing'}          // TODO implement real
            }, {
                wait: true,
                success: function(){
                    that.trigger('show_console');
                },
                error: function(){
                    alert('error while saving! Maybe some fields required.')
                }
            });
        },

        initialize: function () {
            this.state = new Backbone.Model({ isFinished: false });
        }
    });

    Views.ConsoleView = Backbone.Marionette.ItemView.extend({
        template: '#minion-console-template',
        model: new Backbone.Model({'text': []}),

        events: {
            'click button#main' : function () { App.router.navigate('/', {trigger: true}) }
        },

        initialize: function () {
            this.model.set('text', []);
            this.listenTo(App.vent, 'update_console_log', function (data) {
                var lines = this.model.get('text');
                lines.push(data);
                this.model.set('text', lines);
                this.render();
            })
        }
    });
    // =========== //Add minion wizard ==================================






























    // =========== Detailed view ========================================
    Views.MinionDetailedLayout = Backbone.Marionette.LayoutView.extend({
        template: '#minion-detailed-layout-template',

        regions: {
            tab_content: 'div#tab-content'
        },

        events: {
            'click ul.nav li': 'changeTab',
            'click button#minion-add-btn': 'saveMinion'
        },

        initialize: function (options) {
            this.tab = options.tab;
            this.minion_id = options.minion_id;
        },

        changeTab: function (evt) {
            evt.preventDefault();
            var tgt = $(evt.target);
            var url_ = '/detailed/' + this.minion_id;
            if (tgt.hasClass('minionSettingsTab')) App.router.navigate(url_ + '/settings/', {trigger: true});
            else if (tgt.hasClass('minionStatsTab')) App.router.navigate(url_ + '/stats/', {trigger: true});
            else if (tgt.hasClass('minionTroublesTab')) App.router.navigate(url_ + '/troubles/', {trigger: true});
        },

//        onRender: function(){
            // load annotations and labels
//            this.ui.description.val(this.model.get('description'));
//            this.ui.active_chkx.prop('checked', this.model.get('active'));
//        },
        
        saveMinion: function () {
            // validation
            this.model.set({
                // change annotations and labels
//                'description': this.ui.description.val(),
//                'active': this.ui.active_chkx.prop('checked'),
            });

            this.model.save(undefined, {
                wait: true,
                success: function(){
                    App.router.navigate('/', {trigger: true})
                },
                error: function(){
                    alert('error while updating! Maybe some fields required.')
                }
            });
        },

        templateHelpers: function(){
          return {
              tab: this.tab
          }
        }
    });

    Views.MinionSettingsTabView = Backbone.Marionette.ItemView.extend({
        template: '#minion-settings-tab-template'
    });

    Views.MinionStatsTabView = Backbone.Marionette.ItemView.extend({
        template: '#minion-stats-tab-template'
    });

    Views.MinionTroublesTabView = Backbone.Marionette.ItemView.extend({
        template: '#minion-troubles-tab-template'
    });
    // =========== //Detailed view ======================================
















    Views.MinionsLayout = Backbone.Marionette.LayoutView.extend({
        template: '#minions-layout-template',

        regions: {
            main: 'div#main',
            pager: 'div#pager'
        }
    });

});


MinionsApp.module('MinionsCRUD', function(MinionsCRUD, App, Backbone, Marionette, $, _){

    MinionsCRUD.Controller = Marionette.Controller.extend({

        showMinions: function(){
            var layout_view = new App.Views.MinionsLayout();
            var minions_list_view = new App.Views.MinionsListView({collection: App.Data.minions});
            var minion_list_pager = new App.Views.PaginatorView({view: minions_list_view});

            this.listenTo(layout_view, 'show', function(){
                layout_view.main.show(minions_list_view);
                layout_view.pager.show(minion_list_pager);
            });

            App.contents.show(layout_view);
        },

        showAddMinion: function(){
            var layout_view = new App.Views.MinionAddWizardLayout();
            var find_step = new App.Views.MinionFindStep();
            var final_step = new App.Views.MinionFinalStep();
            var console_view = new App.Views.ConsoleView();

            this.listenTo(find_step.state, 'change', function () {
                layout_view.trigger('show');
            });

            this.listenTo(find_step.state, 'change', function () {
                final_step.state.set('ip', find_step.state.get('ip'));
                final_step.state.set('hostname', find_step.state.get('hostname'));
            });

            this.listenTo(final_step, 'show_console', function () {
                layout_view.find_step.empty();
                layout_view.final_step.show(console_view);
            });

            this.listenTo(layout_view, 'show', function(){
                layout_view.find_step.show(find_step);
                find_step.state.get('isFinished') ? layout_view.final_step.show(final_step) : {};
            });

            App.contents.show(layout_view);
        },

        showDetailedMinion: function(minion_id, tab){
            var minion = App.Data.minions.get(minion_id);
            var layout_view = new App.Views.MinionDetailedLayout({tab: tab, minion_id: minion_id, model: minion});

            this.listenTo(layout_view, 'show', function(){
                switch (layout_view.tab) {
                    case 'settings': {
                        var minion_settings_tab_view = new App.Views.MinionSettingsTabView({ model: minion });
                        layout_view.tab_content.show(minion_settings_tab_view);
                    } break;
                    case 'stats': {
                        var minion_stats_tab_view = new App.Views.MinionStatsTabView({ model: minion });
                        layout_view.tab_content.show(minion_stats_tab_view);
                    } break;
                    case 'troubles': {
                        var minion_troubles_tab_view = new App.Views.MinionTroublesTabView({ model: minion });
                        layout_view.tab_content.show(minion_troubles_tab_view);
                    } break;
                }
            });
            App.contents.show(layout_view);
        }
    });

    MinionsCRUD.addInitializer(function(){
        var controller = new MinionsCRUD.Controller();

        App.router = new Marionette.AppRouter({
            controller: controller,
            appRoutes: {
                '': 'showMinions',
                'add/': 'showAddMinion',
                'detailed/:id/:tab/': 'showDetailedMinion'
            }
        });

        if (typeof(EventSource) === undefined) {
            console.log('ERROR: EventSource is not supported by browser');
        } else {
            var source = new EventSource("/api/stream");
            source.addEventListener('ping', function (ev) {
                App.Data.minions.fetch()
            }, false);
            source.addEventListener('install_logs', function (ev) {
                App.vent.trigger('update_console_log', ev.data);
            }, false);
        }
    });

});


MinionsApp.on('start', function(){
    if (Backbone.history) {
        Backbone.history.start({root: '/minions/', pushState: true});
    }
});


$(function(){
    MinionsApp.start();
});

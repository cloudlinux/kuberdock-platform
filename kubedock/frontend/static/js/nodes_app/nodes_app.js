"use strict";

var NodesApp = new Backbone.Marionette.Application({
    regions: {
        contents: '#contents'
    }
});


NodesApp.module('Data', function(Data, App, Backbone, Marionette, $, _){

    var unwrapper = function(response) {
        if (response.hasOwnProperty('data'))
            return response['data'];
        return response;
    };

    Data.NodeModel = Backbone.Model.extend({
        urlRoot: '/api/nodes/',
        parse: unwrapper
    });

    Data.NodesCollection = Backbone.PageableCollection.extend({
        url: '/api/nodes/',
        model: Data.NodeModel,
        parse: unwrapper,
        mode: 'client',
        state: {
            pageSize: 10
        }
    });
});


NodesApp.module('Views', function(Views, App, Backbone, Marionette, $, _){

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











    Views.NodeItem = Backbone.Marionette.ItemView.extend({
        template: '#node-item-template',
        tagName: 'tr',

        events: {
            'click button#deleteNode': 'deleteNode',
            'click button#detailedNode' : 'detailedNode',
            'click button#upgradeNode' : 'detailedNode',
            'click button#detailedTroublesTab' : 'detailedTroublesTab'
        },

        deleteNode: function(){
            this.model.destroy();   // no wait, because removed in any case
        },

        detailedNode: function(){
            App.router.navigate('/detailed/' + this.model.id + '/settings/', {trigger: true});
        },

        detailedTroublesTab: function(){
            App.router.navigate('/detailed/' + this.model.id + '/troubles/', {trigger: true});
        }

    });

    Views.NodesListView = Backbone.Marionette.CompositeView.extend({
        template: '#nodes-list-template',
        childView: Views.NodeItem,
        childViewContainer: "tbody",

        events: {
            'click button#add_node' : 'addNode'
        },

        collectionEvents: {
            "remove": function () {this.render()}
        },

        templateHelpers: function(){
          return {
              totalNodes: this.collection.fullCollection.length
          }
        },

        addNode: function(){
            App.router.navigate('/add/', {trigger: true});
        }
    });

















    // =========== Add Node wizard ====================================
    Views.NodeAddWizardLayout = Backbone.Marionette.LayoutView.extend({
        template: '#node-add-layout-template',

        regions: {
            header: '#node-header',
            find_step: '#node-find-step',
            final_step: '#node-final-step'
        }
    });

    Views.NodeFindStep = Backbone.Marionette.ItemView.extend({
        template: '#node-find-step-template',

        ui: {
            'node_name': 'input#node_address',
            'spinner': '#address-spinner'
        },

        events:{
            'change @ui.node_name': 'validateStep'
        },

        validateStep: function (evt) {
            var val = evt.target.value;
            if (val !== '') {
                var that = this;
                this.ui.spinner.spin({color: '#437A9E'});
                Backbone.ajax({ url:"/api/nodes/checkhost/" + val }).done(function (data) {
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

    Views.NodeFinalStep = Backbone.Marionette.ItemView.extend({
        template: '#node-final-step-template',

        ui: {
//            'node_ssh': 'select#node_ssh',
            'node_add_btn': 'button#node-add-btn'
        },

        events:{
//            'change @ui.node_ssh': 'validateStep',
            'click @ui.node_add_btn': 'complete'      // only if valid
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
            App.Data.nodes.create({
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
        template: '#node-console-template',
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
    // =========== //Add Node wizard ==================================






























    // =========== Detailed view ========================================
    Views.NodeDetailedLayout = Backbone.Marionette.LayoutView.extend({
        template: '#node-detailed-layout-template',

        regions: {
            tab_content: 'div#tab-content'
        },

        events: {
            'click ul.nav li': 'changeTab',
            'click button#node-add-btn': 'saveNode'
        },

        initialize: function (options) {
            this.tab = options.tab;
            this.node_id = options.node_id;
        },

        changeTab: function (evt) {
            evt.preventDefault();
            var tgt = $(evt.target);
            var url_ = '/detailed/' + this.node_id;
            if (tgt.hasClass('nodeSettingsTab')) App.router.navigate(url_ + '/settings/', {trigger: true});
            else if (tgt.hasClass('nodeStatsTab')) App.router.navigate(url_ + '/stats/', {trigger: true});
            else if (tgt.hasClass('nodeLogsTab')) App.router.navigate(url_ + '/logs/', {trigger: true});
            else if (tgt.hasClass('nodeTroublesTab')) App.router.navigate(url_ + '/troubles/', {trigger: true});
        },

//        onRender: function(){
            // load annotations and labels
//            this.ui.description.val(this.model.get('description'));
//            this.ui.active_chkx.prop('checked', this.model.get('active'));
//        },
        
        saveNode: function () {
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

    Views.NodeSettingsTabView = Backbone.Marionette.ItemView.extend({
        template: '#node-settings-tab-template'
    });

    Views.NodeStatsTabView = Backbone.Marionette.ItemView.extend({
        template: '#node-stats-tab-template'
    });

    Views.NodeLogsTabView = Backbone.Marionette.ItemView.extend({
        template: '#node-logs-tab-template',

        ui: {
            textarea: '.node-logs'
        },

        initialize: function () {
            this.model.set('logs', []);
            this.listenTo(App.vent, 'update_node_log_' + this.model.get('ip'), function (data) {
                var lines = this.model.get('logs');
                lines.push(data);
                lines = lines.slice(-100);
                this.model.set('logs', lines);
                this.render();
                _.defer(function(caller){
                    caller.ui.textarea.scrollTop(caller.ui.textarea[0].scrollHeight);
                }, this);
            })
        }
    });

    Views.NodeTroublesTabView = Backbone.Marionette.ItemView.extend({
        template: '#node-troubles-tab-template'
    });
    // =========== //Detailed view ======================================
















    Views.NodesLayout = Backbone.Marionette.LayoutView.extend({
        template: '#nodes-layout-template',

        regions: {
            main: 'div#main',
            pager: 'div#pager'
        }
    });

});


NodesApp.module('NodesCRUD', function(NodesCRUD, App, Backbone, Marionette, $, _){

    NodesCRUD.Controller = Marionette.Controller.extend({

        showNodes: function(){
            var layout_view = new App.Views.NodesLayout();
            var nodes_list_view = new App.Views.NodesListView({collection: App.Data.nodes});
            var node_list_pager = new App.Views.PaginatorView({view: nodes_list_view});

            this.listenTo(layout_view, 'show', function(){
                layout_view.main.show(nodes_list_view);
                layout_view.pager.show(node_list_pager);
            });

            App.contents.show(layout_view);
        },

        showAddNode: function(){
            var layout_view = new App.Views.NodeAddWizardLayout();
            var find_step = new App.Views.NodeFindStep();
            var final_step = new App.Views.NodeFinalStep();
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

        showDetailedNode: function(node_id, tab){
            var node = App.Data.nodes.get(node_id);
            var layout_view = new App.Views.NodeDetailedLayout({tab: tab, node_id: node_id, model: node});

            this.listenTo(layout_view, 'show', function(){
                switch (layout_view.tab) {
                    case 'settings': {
                        var node_settings_tab_view = new App.Views.NodeSettingsTabView({ model: node });
                        layout_view.tab_content.show(node_settings_tab_view);
                    } break;
                    case 'stats': {
                        var node_stats_tab_view = new App.Views.NodeStatsTabView({ model: node });
                        layout_view.tab_content.show(node_stats_tab_view);
                    } break;
                    case 'logs': {
                        var node_logs_tab_view = new App.Views.NodeLogsTabView({ model: node });
                        layout_view.tab_content.show(node_logs_tab_view);
                    } break;
                    case 'troubles': {
                        var node_troubles_tab_view = new App.Views.NodeTroublesTabView({ model: node });
                        layout_view.tab_content.show(node_troubles_tab_view);
                    } break;
                }
            });
            App.contents.show(layout_view);
        }
    });

    NodesCRUD.addInitializer(function(){
        var controller = new NodesCRUD.Controller();

        App.router = new Marionette.AppRouter({
            controller: controller,
            appRoutes: {
                '': 'showNodes',
                'add/': 'showAddNode',
                'detailed/:id/:tab/': 'showDetailedNode'
            }
        });

        if (typeof(EventSource) === undefined) {
            console.log('ERROR: EventSource is not supported by browser');
        } else {
            var source = new EventSource("/api/stream");
            source.addEventListener('pull_nodes_state', function (ev) {
                App.Data.nodes.fetch()
            }, false);
            source.addEventListener('install_logs', function (ev) {
                App.vent.trigger('update_console_log', ev.data);
            }, false);
            NodesApp.Data.nodes.forEach(function (node) {
        	source.addEventListener('node-log-' + node.get('ip'), function (ev) {
        	    App.vent.trigger('update_node_log_' + node.get('ip'), ev.data);
        	}, false);
            });
        }
    });

});


NodesApp.on('start', function(){
    if (Backbone.history) {
        Backbone.history.start({root: '/nodes/', pushState: true});
    }
});


$(function(){
    NodesApp.start();
});

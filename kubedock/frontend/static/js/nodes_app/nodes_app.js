"use strict";

/*function modalDialog(options){
    var modal = $('.modal');
    if(options.title) modal.find('.modal-title').html(options.title);
    if(options.body) modal.find('.modal-body').html(options.body);
    if(options.large) modal.addClass('bs-example-modal-lg');
    if(options.small) modal.addClass('bs-example-modal-sm');
    if(options.show) modal.modal('show');
    return modal;
}*/

function modalDialog(options){
    var modal = $('.modal'),
        modalDialog = modal.find('.modal-dialog');
    modalDialog.css('margin-top', ( $(window).height() / 2 - 140 ));
    if(options.title) modal.find('.modal-title').html(options.title);
    if(options.body) modal.find('.modal-body').html(options.body);
    if(options.large) modal.addClass('bs-example-modal-lg');
    if(options.small) modal.addClass('bs-example-modal-sm');
    if(options.show) modal.modal('show');
    if(options.footer){
        modal.find('.modal-footer').empty();
        if(options.footer.buttonOk){
            modal.find('.modal-footer').append(
                $('<button type="button" class="btn blue" ' +
                      'data-dismiss="modal">').unbind('click')
                    .bind('click', options.footer.buttonOk)
                    .text('OK')
            )
        }
        if(options.footer.buttonCancel){
            if(options.footer.buttonCancel === true){
                modal.find('.modal-footer').prepend(
                    $('<button type="button" class="btn"' +
                          'data-dismiss="modal">Cancel</button>')
                )
            }
        }
    }
    return modal;
};

function modelError(b, t){
    modalDialog({
        title: t ? t : 'Error',
        body: typeof b == "string" ? b : b.responseJSON ? JSON.stringify(b.responseJSON): b.responseText,
        show: true
    });
}

function localizeDatetime(dt, tz){
    try {
        return moment(dt).tz(tz).format('YYYY-MM-DD hh:mm:ss');
    } catch (e){
        console.log(e);
    }
    return dt;
}

var NodesApp = new Backbone.Marionette.Application({
    regions: {
        contents: '#contents'
    }
});

var _ajaxStatusCodes = {
    statusCode: {
        400: function(xhr){
            var err = xhr.statusText;
            if(xhr.responseJSON && xhr.responseJSON.data)
                err = xhr.responseJSON.data;
            if(typeof err === "object")
                err = JSON.stringify(err);
            $.notify(err, {
                autoHideDelay: 15000,
                clickToHide: true,
                globalPosition: 'top center',
                className: 'error'
            });
        },
        401: function (xhr) {
            var err = xhr.statusText;
            if(xhr.responseJSON && xhr.responseJSON.data)
                err = xhr.responseJSON.data;
            if(typeof err === "object")
                err = JSON.stringify(err);
            $.notify(err, {
                autoHideDelay: 5000,
                globalPosition: 'top center',
                className: 'danger'
            });

            // Redirect to the login page.
                window.location.href = "/login";
        },
        403: function (xhr) {
            // 403 -- Access denied
//                    Backbone.history.navigate("login", true);
        },
        404: function(xhr){
            $('body').html(
                '404 Page not found'
            );
        },
        500: function(xhr){
            var err = xhr.statusText;
            if(xhr.responseJSON && xhr.responseJSON.data)
                err = xhr.responseJSON.data;
            if(typeof err === "object")
                err = JSON.stringify(err);
            $.notify(err, {
                autoHideDelay: 5000,
                globalPosition: 'top center',
                className: 'danger'
            });
        }
    }
};

NodesApp.module('Data', function(Data, App, Backbone, Marionette, $, _){

    Backbone.ajax = function() {
        // Invoke $.ajaxSetup in the context of Backbone.$
        Backbone.$.ajaxSetup.call(Backbone.$, _ajaxStatusCodes);
        return Backbone.$.ajax.apply(Backbone.$, arguments);
    };

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

        ui: {
            'deleteNode' : '#deleteNode',
        },

        events: {
            'click'                                 : 'checkItem',
            'click @ui.deleteNode'                  : 'deleteNode',
            'click button#detailedNode'             : 'detailedNode',
            'click button#upgradeNode'              : 'detailedNode',
            'click button#detailedConfigurationTab' : 'detailedConfigurationTab',
        },

        templateHelpers: function(){
            var model = this.model,
                kubeType = '';
            _.each(kubeTypes, function(itm){
                if(itm.id == model.get('kube_type'))
                    kubeType = itm.name;
            });
            return {
                'kubeType' : kubeType
            }
        },

        deleteNode: function(){
            var that = this,
                name = that.model.get('hostname');
            modalDialog({
                title: "Delete " + name + "?",
                body: "Are you sure want to delete node '" + name + "'?",
                small: true,
                show: true,
                footer: {
                    buttonOk: function(){
                        that.model.destroy();
                    },
                    buttonCancel: true
                }
            });
        },

        detailedNode: function(){
            App.router.navigate('/detailed/' + this.model.id + '/general/', {trigger: true});
        },

        detailedConfigurationTab: function(){
            App.router.navigate('/detailed/' + this.model.id + '/configuration/', {trigger: true});
        },

        checkItem: function(){
            this.$el.toggleClass('checked').siblings().removeClass('checked');
        }
    });

    Views.NodesListView = Backbone.Marionette.CompositeView.extend({
        template: '#nodes-list-template',
        childView: Views.NodeItem,
        childViewContainer: "tbody",

        ui: {
            'addNode': 'button#add_node',
        },

        events: {
            'click @ui.addNode' : 'addNode',
        },

        collectionEvents: {
            "remove": function () {
                this.render()
            }
        },

        templateHelpers: function(){
            return {
                totalNodes: this.collection.fullCollection.length
            }
        },

        addNode: function(){
            App.router.navigate('/add/', {trigger: true});
        },

    });

    // =========== Add Node wizard ====================================
    Views.NodeAddWizardLayout = Backbone.Marionette.LayoutView.extend({
        template: '#node-add-layout-template',

        regions: {
            header: '#node-header',
            find_step: '#node-find-step',
            final_step: '#node-final-step'
        },

        ui: {
            'nodes_page' : 'div#nodes-page'
        },

        events:{
            'click @ui.nodes_page' : 'breadcrumbClick'
        },

        breadcrumbClick: function(){
           App.router.navigate('/', {trigger: true})
        }
    });

    Views.NodeFindStep = Backbone.Marionette.ItemView.extend({
        template: '#node-find-step-template',

        initialize: function () {
            this.state = new Backbone.Model({ isFinished: true });
        }
    });

    Views.NodeFinalStep = Backbone.Marionette.ItemView.extend({
        template: '#node-final-step-template',

        ui: {
            'node_add_btn'     : 'button#node-add-btn',
            'node_cancel_btn'  : 'button#node-cancel-btn',
            'node_type_select' : 'select.kube_type',
            'node_name'        : 'input#node_address',
            'spinner'          : '#address-spinner',
        },

        events:{
            'click @ui.node_add_btn'      : 'complete',
            'click @ui.node_cancel_btn'   : 'cancel',
            'change @ui.node_type_select' : 'change_kube_type',
            'change @ui.node_name'        : 'validateStep',
            'click @ui.node_name'         : 'removeExtraClass',
        },

        change_kube_type: function(evt) {
            if (this.ui.node_type_select.value !== null) {
                this.ui.node_type_select.addClass('success');
                this.state.set('kube_type', parseInt(evt.target.value));
            }
        },

        complete: function () {
            var that = this;
            App.Data.nodes.create({
                ip: this.state.get('ip'),
                hostname: this.state.get('hostname'),
                status: 'pending',
                kube_type: this.state.get('kube_type'),
                install_log: ''
            }, {
                wait: false,
//                wait: true,
                success: function(){
                    // TODO redirect to this node page
//                    that.trigger('show_console');
                    App.router.navigate('/', {trigger: true});
                },
                error: function(){
                    modelError('error while saving! Maybe some fields required.');
                }
            });
        },

        validateStep: function (evt) {
            var val = evt.target.value;
            if (val !== '') {
                var that = this;
                this.ui.spinner.spin({color: '#437A9E'});
                Backbone.ajax({ url:"/api/nodes/checkhost/" + val }).done(function (data) {
                    that.state.set('ip', data.ip);
                    that.state.set('hostname', data.hostname);
                    that.ui.node_name.addClass('success');
                }).error(function(resp) {
                    modelError(resp);
                    that.ui.node_name.addClass('error');
                });
                that.ui.spinner.spin(false);
            }
        },

        removeExtraClass: function(){
            this.ui.node_name.hasClass('error') ? this.ui.node_name.removeClass('error') : '';
            this.ui.node_name.hasClass('success') ? this.ui.node_name.removeClass('success') : '';
        },

        cancel: function () {
            App.router.navigate('/', {trigger: true});
        },

        initialize: function () {
            this.state = new Backbone.Model({ isFinished: false });
        }
    });

    // TODO delete this view at all, not needed
    Views.ConsoleView = Backbone.Marionette.ItemView.extend({
        template: '#node-console-template',
        model: new Backbone.Model({'text': []}),

        events: {
            'click button#main' : function () { App.router.navigate('/', {trigger: true}) }
        }
    });
    // =========== //Add Node wizard ==================================

    // =========== Detailed view ========================================
    Views.NodeDetailedLayout = Backbone.Marionette.LayoutView.extend({
        template: '#node-detailed-layout-template',

        regions: {
            tab_content: 'div#tab-content'
        },

        ui: {
            'nodes_page' : 'div#nodes-page',
            'redeploy'   : 'button#redeploy_node',
            'delete'     : 'button#delete_node',
        },

        events: {
            'click ul.nav li'           : 'changeTab',
            'click button#node-add-btn' : 'saveNode',
            'click @ui.nodes_page'      : 'breadcrumbClick',
            'click @ui.redeploy'        : 'redeployNode',
            'click @ui.delete'          : 'deleteNode',
        },

        initialize: function (options) {
            this.tab = options.tab;
            this.node_id = options.node_id;
        },

        changeTab: function (evt) {
            evt.preventDefault();
            var tgt = $(evt.target);
            var url_ = '/detailed/' + this.node_id;
            if (tgt.hasClass('nodeGeneralTab')) App.router.navigate(url_ + '/general/', {trigger: true});
            else if (tgt.hasClass('nodeStatsTab')) App.router.navigate(url_ + '/stats/', {trigger: true});
            else if (tgt.hasClass('nodeLogsTab')) App.router.navigate(url_ + '/logs/', {trigger: true});
            else if (tgt.hasClass('nodeMonitoringTab')) App.router.navigate(url_ + '/monitoring/', {trigger: true});
            else if (tgt.hasClass('nodeTimelinesTab')) App.router.navigate(url_ + '/timelines/', {trigger: true});
            else if (tgt.hasClass('nodeConfigurationTab')) App.router.navigate(url_ + '/configuration/', {trigger: true});
        },

        saveNode: function () {
            this.model.save(undefined, {
                wait: true,
                success: function(){
                    App.router.navigate('/', {trigger: true})
                },
                error: function(){
                    modelError('error while updating! Maybe some fields required.');
                }
            });
        },

        redeployNode: function() {
            $.ajax({
                url: '/api/nodes/redeploy/' + this.model.id,
            });
        },

        deleteNode: function() {
            var that = this,
                name = that.model.get('hostname');
            modalDialog({
                title: "Delete " + name + "?",
                body: "Are you sure want to delete node '" + name + "'?",
                small: true,
                show: true,
                footer: {
                    buttonOk: function(){
                        that.model.destroy();
                        App.router.navigate('/', {trigger: true})
                    },
                    buttonCancel: true
                }
            });
        },

        breadcrumbClick: function(){
           App.router.navigate('/', {trigger: true})
        },

        templateHelpers: function(){
          return {
              tab: this.tab
          }
        }
    });

    Views.NodeGeneralTabView = Backbone.Marionette.ItemView.extend({
        template: '#node-general-tab-template',

        ui: {
            'nodeLogsTab'       : 'span.log-tab',
            'logSpollerButton'  : '.spoiler-btn.log'
        },

        events: {
            'click @ui.nodeLogsTab'      : 'nodeLogsTab',
            'click @ui.logSpollerButton' : 'logSpoller',
        },

        nodeLogsTab: function(){
            App.router.navigate('/detailed/' + this.model.id + '/logs/', {trigger: true});
        },

        logSpoller: function(){
            this.ui.logSpollerButton.parent().children('.spoiler-body').collapse('toggle');
        },

        initialize: function () {
            this.listenTo(App.vent, 'update_console_log', function () {
                this.render();
            })
        }
    });

    Views.NodeStatsTabView = Backbone.Marionette.ItemView.extend({
        template: '#node-stats-tab-template'
    });

    Views.NodeLogsTabView = Backbone.Marionette.ItemView.extend({
        template: '#node-logs-tab-template',

        ui: {
            textarea: '.node-logs'
        },

        initialize: function() {
            this.model.set('logs', []);
            function get_logs() {
                var ip = this.model.get('ip');
                var today = new Date();
                var year = today.getUTCFullYear();
                var month = today.getUTCMonth() + 1;
                var day = today.getUTCDate();
                var index = 'syslog-' + year + '.' +
                    ('0' + month).slice(-2) +'.' +
                    ('0' + day).slice(-2);
                var hostname = this.model.get('hostname');
                var host = hostname.split('.')[0];
                var size = 100;
                var url = '/logs/' + ip + '/' + index +
                    '/_search?q=host:("' + hostname + '" OR "' + host + '")' +
                    '&size=' + size + '&sort=@timestamp:desc';
                $.ajax({
                    url: url,
                    dataType : 'json',
                    context: this,
                    success: function(data) {
                        var lines = _.map(data['hits']['hits'], function(line) {
                            return line['_source'];
                        });
                        lines.reverse();
                        this.model.set('logs', lines);
                        this.render();
                        _.defer(function(caller){
                            caller.ui.textarea.scrollTop(caller.ui.textarea[0].scrollHeight);
                        }, this);
                    }
                });
                this.model.set('timeout', setTimeout($.proxy(get_logs, this), 10000));
            }
            $.proxy(get_logs, this)();
        },

        onBeforeDestroy: function () {
            clearTimeout(this.model.get('timeout'));
        }
    });

    Views.NodeMonitoringTabView = Backbone.Marionette.ItemView.extend({
        template: '#node-monitoring-tab-template',
    });

    Views.NodeTimelinesTabView = Backbone.Marionette.ItemView.extend({
        template: '#node-timelines-tab-template',
    });

    Views.NodeConfigurationTabView = Backbone.Marionette.ItemView.extend({
        template: '#node-configuration-tab-template'
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
                    case 'general': {
                        var node_general_tab_view = new App.Views.NodeGeneralTabView({ model: node });
                        layout_view.tab_content.show(node_general_tab_view);
                    } break;
                    case 'stats': {
                        var node_stats_tab_view = new App.Views.NodeStatsTabView({ model: node });
                        layout_view.tab_content.show(node_stats_tab_view);
                    } break;
                    case 'logs': {
                        var node_logs_tab_view = new App.Views.NodeLogsTabView({ model: node });
                        layout_view.tab_content.show(node_logs_tab_view);
                    } break;
                    case 'monitoring': {
                        var node_monitoring_tab_view = new App.Views.NodeMonitoringTabView({ model: node });
                        layout_view.tab_content.show(node_monitoring_tab_view);
                    } break;
                    case 'timelines': {
                        var node_timelines_tab_view = new App.Views.NodeTimelinesTabView({ model: node });
                        layout_view.tab_content.show(node_timelines_tab_view);
                    } break;

                    case 'configuration': {
                        var node_configuration_tab_view = new App.Views.NodeConfigurationTabView({ model: node });
                        layout_view.tab_content.show(node_configuration_tab_view);
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
                var decoded = JSON.parse(ev.data);
//                console.log(decoded);
                var node = App.Data.nodes.findWhere({'hostname': decoded.for_node});
                if (typeof node != 'undefined') {
                    node.set('install_log', node.get('install_log') + decoded.data + '\n');
                    App.vent.trigger('update_console_log');
                }
            }, false);
            source.onerror = function (e) {
                // without this handler, even empty, browser doesn't do reconnect
                console.log("SSE Error handler");
                // TODO Setup here timer to reconnect, maybe via location.reload
            };
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
    $('[data-toggle="tooltip"]').tooltip()
});

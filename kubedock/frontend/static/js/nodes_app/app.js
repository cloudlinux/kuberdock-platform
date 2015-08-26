define(['backbone', 'marionette', 'utils', 'notify', 'backbone-paginator', 'selectpicker', 'jquery-spin']
        , function(Backbone, Marionette, utils) {

    var NodesApp = new Backbone.Marionette.Application({
        regions: {
            contents: '#contents'
        }
    });

    NodesApp.module('Data', function(Data, App, Backbone, Marionette, $, _) {
        var unwrapper = function(response) {
            if (response.hasOwnProperty('data'))
                return response['data'];
            return response;
        };

        Data.NodeModel = Backbone.Model.extend({
            urlRoot: '/api/nodes/',
            parse: unwrapper,
            defaults: {
                'ip': ''
            }
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

        Data.nodes = new Data.NodesCollection(nodesCollection);
    });

    NodesApp.module('Views', function(Views, App, Backbone, Marionette, $, _){

        //================= Paginator TODO NEED MERGE =================//
        Views.PaginatorView = Backbone.Marionette.ItemView.extend({
            template: '#paginator-template',

            initialize: function(options) {
                this.model = new Backbone.Model({
                    v: options.view,
                    c: options.view.collection
                });
                this.listenTo(options.view.collection, 'remove', this.render);
                this.listenTo(options.view.collection, 'reset', this.render);
            },

            events: {
                'click li.pseudo-link': 'paginateIt'
            },

            paginateIt: function(evt){
                evt.stopPropagation();
                var tgt = $(evt.target);
                var coll = this.model.get('c');
                if (tgt.hasClass('paginatorFirst')) coll.getFirstPage();
                else if (tgt.hasClass('paginatorPrev') && coll.hasPreviousPage()) coll.getPreviousPage();
                else if (tgt.hasClass('paginatorNext') && coll.hasNextPage()) coll.getNextPage();
                else if (tgt.hasClass('paginatorLast')) coll.getLastPage();
                this.render();
            }
        });

        //================= NodeItem =================//
        Views.NodeItem = Backbone.Marionette.ItemView.extend({
            template: '#node-item-template',
            tagName: 'tr',

            ui: {
                'deleteNode'       : '#deleteNode',
                'detailedNode'     : 'button#detailedNode',
                'upgradeNode'      : 'button#upgradeNode',
                'configurationTab' : 'button#detailedConfigurationTab'
            },

            events: {
                'click'                      : 'checkItem',
                'click @ui.deleteNode'       : 'deleteNode',
                'click @ui.detailedNode'     : 'detailedNode',
                'click @ui.upgradeNode'      : 'detailedNode',
                'click @ui.configurationTab' : 'detailedConfigurationTab',
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

            deleteNode: function() {
                var that = this,
                    name = that.model.get('hostname');

                utils.modalDialogDelete({
                    title: "Delete " + name + "?",
                    body: "Are you sure want to delete node '" + name + "'?",
                    small: true,
                    show: true,
                    footer: {
                        buttonOk: function() {
                            that.model.destroy({wait: true});
                            App.router.navigate('/', {trigger: true});
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

        //================= NodeList =================//
        Views.NodesListView = Backbone.Marionette.CompositeView.extend({
            template: '#nodes-list-template',
            collection: App.Data.nodes,
            childView: Views.NodeItem,
            childViewContainer: "tbody",

            ui: {
                'navSearch'   : '.nav-search',
                'addNode'     : 'button#add_node',
                'node_search' : 'input#nav-search-input',
                'th'          : 'table th'
            },

            events: {
                'click @ui.addNode'     : 'addNode',
                'keyup @ui.node_search' : 'filter',
                'click @ui.navSearch'   : 'showSearch',
                'blur @ui.node_search'  : 'closeSearch',
                'click @ui.th'          : 'toggleSort'
            },

            collectionEvents: {
                "remove": function () {
                    this.render()
                }
            },

            initialize: function() {
                this.fakeCollection = this.collection.fullCollection.clone();

                this.listenTo(this.collection, 'reset', function (col, options) {
                    options = _.extend({ reindex: true }, options || {});
                    if(options.reindex && options.from == null && options.to == null) {
                        this.fakeCollection.reset(col.models);
                    }
                });
                this.counter = 1;
            },

            toggleSort: function(e) {
                var target = $(e.target),
                    targetClass = target.attr('class');

                this.collection.setSorting(targetClass, this.counter);
                this.collection.fullCollection.sort();
                this.counter = this.counter * (-1)
                target.find('.caret').toggleClass('rotate').parent()
                      .siblings().find('.caret').removeClass('rotate');
            },

            filter: function() {
                var value = this.ui.node_search[0].value,
                    valueLength = value.length;

                if (valueLength >= 2){
                    this.collection.fullCollection.reset(_.filter(this.fakeCollection.models, function(e) {
                        if(e.get('hostname').indexOf( value || '') >= 0) return e
                    }), { reindex: false });
                } else{
                    this.collection.fullCollection.reset(this.fakeCollection.models, { reindex: false});
                }
                this.collection.getFirstPage();
            },

            showSearch: function(){
                this.ui.navSearch.addClass('active');
                this.ui.node_search.focus();
            },

            closeSearch: function(){
                this.ui.navSearch.removeClass('active');
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

        // ================= Add Node wizard =================//
        Views.NodeAddWizardLayout = Backbone.Marionette.LayoutView.extend({
            template: '#node-add-layout-template',

            regions: {
                header        : '#node-header',
                node_add_step : '#node-add-step'
            },

            ui: {
                'nodes_page' : 'div#nodes-page',
            },

            events:{
                'click @ui.nodes_page' : 'breadcrumbClick'
            },

            breadcrumbClick: function(){
               App.router.navigate('/', {trigger: true})
            }
        });

        //================= Add Node Page =================//
        Views.NodeAddStep = Backbone.Marionette.ItemView.extend({
            template: '#node-add-step-template',

            ui: {
                'node_add_btn'     : 'button#node-add-btn',
                'node_cancel_btn'  : 'button#node-cancel-btn',
                'node_type_select' : 'select.kube_type',
                'node_name'        : 'input#node_address',
                'spinner'          : '#address-spinner',
                'selectpicker'     : '.selectpicker',
            },

            events:{
                'click @ui.node_cancel_btn'   : 'cancel',
                'click @ui.node_add_btn'      : 'complete',
                'click @ui.node_name'         : 'removeExtraClass',
                'change @ui.node_type_select' : 'change_kube_type',
                'change @ui.node_name'        : 'validateStep',
            },

            change_kube_type: function(evt) {
                if (this.ui.node_type_select.value !== null) this.state.set('kube_type', parseInt(evt.target.value));
            },

            complete: function () {
                var that = this;
                var val = this.state.get('hostname');
                if (val !== '') {
                    App.Data.nodes.create({
                        hostname: val,
                        status: 'pending',
                        kube_type: this.state.get('kube_type'),
                        install_log: ''
                    }, {
                        wait: true,
                        success: function(){
                            App.router.navigate('/', {trigger: true});
                            $.notify("Added node successfully", {
                                autoHideDelay: 5000,
                                clickToHide: true,
                                globalPosition: 'bottom left',
                                className: 'success',
                            });
                        },
                    });
                }
            },

            validateStep: function (evt) {
                var val = evt.target.value;
                if (val !== '') {
                    var that = this;
                    this.ui.spinner.spin({color: '#437A9E'});
                    Backbone.ajax({ url:"/api/nodes/checkhost/" + val, async: false }).done(function (data) {
                        that.state.set('hostname', val);
                    }).error(function(resp) {
                        that.state.set('hostname', '');
                        that.ui.node_name.addClass('error');
                    });
                    that.ui.spinner.spin(false);
                }
            },

            removeExtraClass: function(){
                this.ui.node_name.hasClass('error') ? this.ui.node_name.removeClass('error') : '';
            },

            cancel: function () {
                App.router.navigate('/', {trigger: true});
            },

            onRender: function(){
                this.state.set('kube_type', parseInt(this.ui.node_type_select.val()));
                this.ui.selectpicker.selectpicker();
            },

            initialize: function () {
                this.state = new Backbone.Model({ isFinished: false });
            }
        });

        // ================= Detailed View =================//
        Views.NodeDetailedLayout = Backbone.Marionette.LayoutView.extend({
            template: '#node-detailed-layout-template',

            regions: {
                tab_content: 'div#tab-content'
            },

            ui: {
                'nodes_page' : 'div#nodes-page',
                'redeploy'   : 'button#redeploy_node',
                'delete'     : 'button#delete_node',
                'addBtn'     : 'button#node-add-btn',
                'tabItem'    : 'ul.nav li'
            },

            events: {
                'click @ui.tabItem'    : 'changeTab',
                'click @ui.addBtn'     : 'saveNode',
                'click @ui.nodes_page' : 'breadcrumbClick',
                'click @ui.redeploy'   : 'redeployNode',
                'click @ui.delete'     : 'deleteNode',
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
                    error: function() {
                        utils.modelError('Error while updating! Maybe some fields required.');
                    }
                });
            },

            redeployNode: function() {
                var that = this,
                    name = that.model.get('hostname');

                utils.modalDialog({
                    title: "Re-install " + name + "?",
                    body: "Are you sure want to re-install node '" + name + "'?",
                    small: true,
                    show: true,
                    footer: {
                        buttonOk: function(){
                            $.ajax({
                                url: '/api/nodes/redeploy/' + that.model.id,
                            });
                        },
                        buttonCancel: true
                    }
                });
            },

            deleteNode: function() {
                var that = this,
                    name = that.model.get('hostname');

                utils.modalDialogDelete({
                    title: "Delete " + name + "?",
                    body: "Are you sure want to delete node '" + name + "'?",
                    small: true,
                    show: true,
                    footer: {
                        buttonOk: function(){
                            that.model.destroy({wait: true});
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

        //================= Node Genegal Tab =================//
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

        //================= Node Stats Tab =================//
        Views.NodeStatsTabView = Backbone.Marionette.ItemView.extend({
            template: '#node-stats-tab-template'
        });

        //================= Node Stats Tab  =================//
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
                        },
                        statusCode: {
                            404: function(xhr) {
                                $.notify('Log not founded', {
                                    autoHideDelay: 5000,
                                    globalPosition: 'bottom left',
                                    className: 'error'
                                });
                            }
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

        //================= Node Monitoring Tab =================//
        Views.NodeMonitoringTabView = Backbone.Marionette.ItemView.extend({
            template: '#node-monitoring-tab-template',
        });

        //================= Node Timelines Tab =================//
        Views.NodeTimelinesTabView = Backbone.Marionette.ItemView.extend({
            template: '#node-timelines-tab-template',
        });

        //================= Node Configuration Tab =================//
        Views.NodeConfigurationTabView = Backbone.Marionette.ItemView.extend({
            template: '#node-configuration-tab-template'
        });

        //================= Node Layout View =================//
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
                var nodes_list_view = new App.Views.NodesListView({
                    collection: App.Data.nodes
                });
                var node_list_pager = new App.Views.PaginatorView({view: nodes_list_view});

                this.listenTo(layout_view, 'show', function(){
                    layout_view.main.show(nodes_list_view);
                    layout_view.pager.show(node_list_pager);
                });
                App.contents.show(layout_view);
            },

            showAddNode: function(){
                var layout_view = new App.Views.NodeAddWizardLayout();
                var node_add_step = new App.Views.NodeAddStep();

                this.listenTo(layout_view, 'show', function(){
                    layout_view.node_add_step.show(node_add_step)
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

        NodesCRUD.addInitializer(function() {
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
                    // console.log(decoded);
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

    return NodesApp;
});
define(['nodes_app/app', 'marionette', 'utils',
        'tpl!nodes_app/templates/node_detailed_layout.tpl',
        'tpl!nodes_app/templates/node_general_tab.tpl',
        'tpl!nodes_app/templates/node_stats_tab.tpl',
        'tpl!nodes_app/templates/node_logs_tab.tpl',
        'tpl!nodes_app/templates/node_monitoring_tab.tpl',
        'tpl!nodes_app/templates/node_timelines_tab.tpl',
        'tpl!nodes_app/templates/node_configuration_tab.tpl',
        'tpl!nodes_app/templates/node_add_layout.tpl',
        'tpl!nodes_app/templates/node_add_step.tpl',
        'tpl!nodes_app/templates/node_empty.tpl',
        'tpl!nodes_app/templates/node_item.tpl',
        'tpl!nodes_app/templates/node_list.tpl',
        'tpl!nodes_app/templates/node_paginator.tpl',
        'tpl!nodes_app/templates/node_layout.tpl',
        'tpl!nodes_app/templates/node_item_graph.tpl',
        'bootstrap', 'jqplot', 'jqplot-axis-renderer', 'selectpicker'],
       function(App, Marionette, utils,
                nodeDetailedLayoutTpl,
                nodeGeneralTabTpl,
                nodeStatsTabTpl,
                nodeLogsTabTpl,
                nodeMonitoringTabTpl,
                nodeTimelinesTabTpl,
                nodeConfigurationTabTpl,
                nodeAddLayoutTpl,
                nodeAddStepTpl,
                nodeEmptyTpl,
                nodeItemTpl,
                nodeListTpl,
                nodePaginatorTpl,
                nodeLayoutTpl,
                nodeItemGraphTpl){

    var views = {};

    views.PaginatorView = Backbone.Marionette.ItemView.extend({
        template: nodePaginatorTpl,

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

    //================= NodeEmpty =================//
    views.NodeEmpty = Backbone.Marionette.ItemView.extend({
        template: nodeEmptyTpl,
        tagName: 'tr'
    });

    //================= NodeItem =================//
    views.NodeItem = Backbone.Marionette.ItemView.extend({
        template: nodeItemTpl,
        tagName: 'tr',

        ui: {
            'deleteNode'       : '.deleteNode',
            'detailedNode'     : 'button.detailedNode',
            'upgradeNode'      : 'button#upgradeNode',
            //'configurationTab' : 'button#detailedConfigurationTab'
        },

        events: {
            'click'                      : 'checkItem',
            'click @ui.deleteNode'       : 'deleteNode',
            'click @ui.detailedNode'     : 'detailedNode',
            'click @ui.upgradeNode'      : 'detailedNode',
            //'click @ui.configurationTab' : 'detailedConfigurationTab',
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
                preloader = $('#page-preloader'),
                name = that.model.get('hostname');

            utils.modalDialogDelete({
                title: "Delete " + name + "?",
                body: "Are you sure want to delete node '" + name + "'?",
                small: true,
                show: true,
                footer: {
                    buttonOk: function() {
                        preloader.show();
                        that.model.destroy({
                            wait: true,
                            success: function(){
                                preloader.hide();
                            },
                            error: function(){
                                preloader.hide();
                            }
                        });
                    },
                    buttonCancel: true
                }
            });
        },

        detailedNode: function(){
            App.navigate(this.model.id + '/general/', {trigger: true});
        },

        //detailedConfigurationTab: function(){
        //    App.navigate('/detailed/' + this.model.id + '/configuration/', {trigger: true});
        //},

        checkItem: function(){
            this.$el.toggleClass('checked').siblings().removeClass('checked');
        }
    });

    //================= NodeList =================//
    views.NodesListView = Backbone.Marionette.CompositeView.extend({
        //collection         : App.Data.nodes,
        template           : nodeListTpl,
        childView          : views.NodeItem,
        emptyView          : views.NodeEmpty,
        childViewContainer : "tbody",

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

        addNode: function(){
            App.navigate('add', {trigger: true});
        },
    });

    // ================= Add Node wizard =================//
    views.NodeAddWizardLayout = Backbone.Marionette.LayoutView.extend({
        template: nodeAddLayoutTpl,

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
           App.navigate('/', {trigger: true})
        }
    });

    //================= Add Node Page =================//
    views.NodeAddStep = Backbone.Marionette.ItemView.extend({
        template: nodeAddStepTpl,

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
            'change @ui.node_type_select' : 'change_kube_type',
        },

        change_kube_type: function(evt) {
            if (this.ui.node_type_select.value !== null) this.state.set('kube_type', parseInt(evt.target.value));
        },

        templateHelpers: {
            kubeTypes: kubeTypes
        },

        complete: function () {
            var that = this,
                preloader = $('#page-preloader'),
                val = this.ui.node_name.val(),
                pattern =  /^(?=.{1,255}$)[0-9A-Z](?:(?:[0-9A-Z]|-){0,61}[0-9A-Z])?(?:\.[0-9A-Z](?:(?:[0-9A-Z]|-){0,61}[0-9A-Z])?)*\.?$/i;

            switch (true)
            {
            case !val:
                utils.notifyWindow('Enter valid hostname');
                this.ui.node_name.focus();
                break;
            case val && !pattern.test(val):
                utils.notifyWindow('Hostname can\'t contain some special symbols like "#", "%", "/" or start with "."');
                this.ui.node_name.focus();
                break;
            default:
                preloader.show();
                App.nodesCollection.create({
                    hostname: val,
                    status: 'pending',
                    kube_type: this.state.get('kube_type'),
                    install_log: ''
                }, {
                    wait: true,
                    success: function(){
                        preloader.hide();
                        App.navigate('/', {trigger: true});
                        $.notify('Node "' + val + '" successfully added', {
                            autoHideDelay: 5000,
                            clickToHide: true,
                            globalPosition: 'bottom left',
                            className: 'success',
                        });
                    },
                    error: function(model, response){
                        preloader.hide();
                        utils.notifyWindow(response.responseJSON.data);
                    }
                });
            }
        },

        cancel: function () {
            App.navigate('/', {trigger: true});
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
    views.NodeDetailedLayout = Backbone.Marionette.LayoutView.extend({
        template: nodeDetailedLayoutTpl,

        regions: {
            tab_content: 'div#tab-content'
        },

        ui: {
            'nodes_page' : 'div#nodes-page',
            'redeploy'   : 'button#redeploy_node',
            'delete'     : 'button#delete_node',
            'tabItem'    : 'ul.nav li'
        },

        events: {
            'click @ui.tabItem'    : 'changeTab',
            'click @ui.nodes_page' : 'breadcrumbClick',
            'click @ui.redeploy'   : 'redeployNode',
            'click @ui.delete'     : 'deleteNode'
        },

        initialize: function (options) {
            this.tab = options.tab;
            this.node_id = options.node_id;
        },

        childEvents: {
            render: function() {
              console.log('A child view has been rendered.');
            }
        },

        changeTab: function (evt) {
            evt.preventDefault();
            var tgt = $(evt.target);
            if (tgt.hasClass('nodeGeneralTab')) App.navigate(this.node_id + '/general/', {trigger: true});
            else if (tgt.hasClass('nodeStatsTab')) App.navigate(this.node_id + '/stats/', {trigger: true});
            else if (tgt.hasClass('nodeLogsTab')) App.navigate(this.node_id + '/logs/', {trigger: true});
            else if (tgt.hasClass('nodeMonitoringTab')) App.navigate(this.node_id + '/monitoring/', {trigger: true});
            else if (tgt.hasClass('nodeTimelinesTab')) App.navigate(this.node_id + '/timelines/', {trigger: true});
            else if (tgt.hasClass('nodeConfigurationTab')) App.navigate(this.node_id + '/configuration/', {trigger: true});
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
                preloader = $('#page-preloader'),
                name = that.model.get('hostname');

            utils.modalDialogDelete({
                title: "Delete " + name + "?",
                body: "Are you sure want to delete node '" + name + "'?",
                small: true,
                show: true,
                footer: {
                    buttonOk: function(){
                        preloader.show();
                        that.model.destroy({
                            wait: true,
                            success: function(){
                                preloader.hide();
                                App.navigate('/', {trigger: true})
                            },
                            error: function(){
                                preloader.hide();
                            }
                        });
                    },
                    buttonCancel: true
                }
            });
        },

        breadcrumbClick: function(){
           App.navigate('/', {trigger: true})
        },

        templateHelpers: function(){
          return {
              tab: this.tab
          }
        }
    });

    //================= Node Genegal Tab =================//
    views.NodeGeneralTabView = Backbone.Marionette.ItemView.extend({
        template: nodeGeneralTabTpl,

        ui: {
            'nodeLogsTab'       : 'span.log-tab',
            'logSpollerButton'  : '.spoiler-btn.log'
        },

        events: {
            'click @ui.nodeLogsTab'      : 'nodeLogsTab',
            'click @ui.logSpollerButton' : 'logSpoller',
        },

        nodeLogsTab: function(){
            App.navigate(this.model.id + '/logs/', {trigger: true});
        },

        logSpoller: function(){
            this.ui.logSpollerButton.parent().children('.spoiler-body').collapse('toggle');
        },

        initialize: function () {
            this.listenTo(App.vent, 'update_console_log', this.render);
            this.listenTo(App.nodesCollection, 'reset', this.render);
        }
    });

    //================= Node Stats Tab =================//
    views.NodeStatsTabView = Backbone.Marionette.ItemView.extend({
        template: nodeStatsTabTpl
    });

    //================= Node Stats Tab  =================//
    views.NodeLogsTabView = Backbone.Marionette.ItemView.extend({
        template: nodeLogsTabTpl,

        ui: {
            textarea: '.node-logs'
        },

        initialize: function() {
            this.listenTo(App.nodesCollection, 'reset', this.render);

            this.model.set('logs', []);
            function get_logs() {
                var hostname = this.model.get('hostname'),
                    size = 100,
                    url = '/api/logs/node/' + hostname + '?size=' + size;
                $.ajax({
                    url: url,
                    dataType : 'json',
                    type: 'GET',
                    context: this,
                    success: function(data) {
                        var lines = _.map(data.data.hits, function(line) {
                            return line._source;
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
                            utils.notifyWindow('Logs aren\'t found');
                        },
                        200: function(xhr){
                            if (xhr.data.hits.length == 0){
                                this.ui.textarea.append('<p>Nothing to show because node log is empty.</p');
                            }
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
    views.NodeMonitoringTabViewItem = Backbone.Marionette.ItemView.extend({
        template: nodeItemGraphTpl,

        ui: {
            chart: '.graph-item'
        },

        initialize: function(options) {
            this.nodeId = options.nodeId;
            this.listenTo(App.nodesCollection, 'reset', this.render);
        },

        makeGraph: function(){
            var lines = this.model.get('lines'),
                node = App.nodesCollection.get(this.nodeId),
                running = node.get('status') === 'running',
                points = [],
                options = {
                    title: this.model.get('title'),
                    axes: {
                        xaxis: {
                            label: 'time',
                            renderer: $.jqplot.DateAxisRenderer,
                        },
                        yaxis: {label: this.model.get('ylabel'), min: 0}
                    },
                    seriesDefaults: {
                        showMarker: false,
                        rendererOptions: {
                            smooth: true,
                            animation: {
                                show: true
                            }
                        }
                    },
                    series: this.model.get('series'),
                    legend: {
                        show: true,
                        placement: 'insideGrid'
                    },
                    grid: {
                        background: '#ffffff',
                        drawBorder: false,
                        shadow: false
                    },
                    noDataIndicator: {
                        show: true,
                        indicator: !running ? "Couldn't connect to the node (maybe it's rebooting)..." :
                            "Collecting data... plot will be dispayed in a few minutes.",
                        axes: {
                            xaxis: {
                                min: utils.localizeDatetimeForUser(new Date(+new Date() - 1000*60*20)),
                                max: utils.localizeDatetimeForUser(new Date()),
                                tickOptions: {formatString:'%H:%M'},
                                tickInterval: '5 minutes',
                            },
                            yaxis: {min: 0, max: 150, tickInterval: 50}
                        }
                    },
                };
            if (this.model.has('seriesColors')) {
                options.seriesColors = this.model.get('seriesColors');
            }

            for (var i=0; i<lines; i++) {
                if (points.length < i+1) {
                    points.push([])
                }
            }

            // If there is only one point, jqplot will display ugly plot with
            // weird grid and no line.
            // Remove this point to force jqplot to show noDataIndicator.
            if (this.model.get('points').length == 1)
                this.model.get('points').splice(0);

            this.model.get('points').forEach(function(record){
                for (var i=0; i<lines; i++) {
                    points[i].push([
                        utils.localizeDatetimeForUser(record[0]),
                        record[i+1]
                    ]);
                }
            });
            this.ui.chart.jqplot(points, options);
        },

        onDomRefresh: function(){
            try {
                this.makeGraph();
            }
            catch(e){
                console.log('Cannot display graph' + e);
            }
        },
    });

    views.NodeMonitoringTabView = Backbone.Marionette.CollectionView.extend({
        childView: views.NodeMonitoringTabViewItem,
        childViewOptions: function() { return { nodeId: this.options.nodeId }; },
    });

    //================= Node Timelines Tab =================//
    views.NodeTimelinesTabView = Backbone.Marionette.ItemView.extend({
        template: nodeTimelinesTabTpl
    });

    //================= Node Configuration Tab =================//
    views.NodeConfigurationTabView = Backbone.Marionette.ItemView.extend({
        template: nodeConfigurationTabTpl
    });

    //================= Node Layout View =================//
    views.NodesLayout = Backbone.Marionette.LayoutView.extend({
        template: nodeLayoutTpl,

        regions: {
            main: 'div#main',
            pager: 'div#pager'
        }
    });
    return views;
});

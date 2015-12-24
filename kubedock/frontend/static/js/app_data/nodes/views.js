define(['app_data/app', 'app_data/controller', 'marionette', 'utils',
        'tpl!app_data/nodes/templates/node_detailed_layout.tpl',
        'tpl!app_data/nodes/templates/node_general_tab.tpl',
        'tpl!app_data/nodes/templates/node_stats_tab.tpl',
        'tpl!app_data/nodes/templates/node_logs_tab.tpl',
        'tpl!app_data/nodes/templates/node_monitoring_tab.tpl',
        'tpl!app_data/nodes/templates/node_timelines_tab.tpl',
        'tpl!app_data/nodes/templates/node_configuration_tab.tpl',
        'tpl!app_data/nodes/templates/node_add_layout.tpl',
        'tpl!app_data/nodes/templates/node_add_step.tpl',
        'tpl!app_data/nodes/templates/node_empty.tpl',
        'tpl!app_data/nodes/templates/node_item.tpl',
        'tpl!app_data/nodes/templates/node_list.tpl',
        'tpl!app_data/nodes/templates/node_paginator.tpl',
        'tpl!app_data/nodes/templates/node_layout.tpl',
        'tpl!app_data/nodes/templates/node_item_graph.tpl',
        'bootstrap', 'jqplot', 'jqplot-axis-renderer',
        'selectpicker', 'nicescroll'],
       function(App, Controller, Marionette, utils,
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

    //views.SideBar = Backbone.Marionette.ItemView.extend({
    //    tagName: 'div',
    //    className: 'col-sm-3 col-md-2 sidebar',
    //    template: sideBarTpl,
    //
    //    initialize: function(options){
    //        this.nodeId = options.nodeId;
    //    },
    //
    //    ui: {
    //        'tabItem'    : 'ul.nav li'
    //    },
    //
    //    events: {
    //        'click @ui.tabItem'    : 'changeTab',
    //    },
    //
    //    changeTab: function (evt) {
    //        evt.preventDefault();
    //        var tgt = $(evt.target);
    //        if (tgt.hasClass('nodeGeneralTab')) App.navigate('nodes/' + this.nodeId + '/general', {trigger: true});
    //        else if (tgt.hasClass('nodeStatsTab')) App.navigate('nodes/' + this.nodeId + '/stats', {trigger: true});
    //        else if (tgt.hasClass('nodeLogsTab')) App.navigate('nodes/' + this.nodeId + '/logs', {trigger: true});
    //        else if (tgt.hasClass('nodeMonitoringTab')) App.navigate('nodes/' + this.nodeId + '/monitoring', {trigger: true});
    //        else if (tgt.hasClass('nodeTimelinesTab')) App.navigate('nodes/' + this.nodeId + '/timelines', {trigger: true});
    //        else if (tgt.hasClass('nodeConfigurationTab')) App.navigate('nodes/' + this.nodeId + '/configuration', {trigger: true});
    //    },
    //});

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

    views.NodeEmpty = Backbone.Marionette.ItemView.extend({
        template: nodeEmptyTpl,
        tagName: 'tr'
    });

    views.NodeItem = Backbone.Marionette.ItemView.extend({
        template: nodeItemTpl,
        tagName: 'tr',

        ui: {
            'deleteNode'       : '.deleteNode',
            'detailedNode'     : 'button.detailedNode',
            'upgradeNode'      : 'button#upgradeNode',
        },

        events: {
            'click'                      : 'checkItem',
            'click @ui.deleteNode'       : 'deleteNode',
            'click @ui.detailedNode'     : 'detailedNode',
            'click @ui.upgradeNode'      : 'detailedNode',
            //'click @ui.configurationTab' : 'detailedConfigurationTab',
        },

        modelEvents: {
            'change': 'render'
        },

        templateHelpers: function(){
            var model = this.model,
                kubeType = '';
            _.each(backendData.kubeTypes, function(itm){
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
            App.navigate('nodes/' + this.model.id + '/general', {trigger: true});
        },

        //detailedConfigurationTab: function(){
        //    App.navigate('/detailed/' + this.model.id + '/configuration/', {trigger: true});
        //},

        checkItem: function(){
            this.$el.toggleClass('checked').siblings().removeClass('checked');
        }
    });

    views.NodesListView = Backbone.Marionette.CompositeView.extend({
        template           : nodeListTpl,
        childView          : views.NodeItem,
        emptyView          : views.NodeEmpty,
        childViewContainer : "tbody",

        ui: {
            navSearch   : '.nav-search',
            addNode     : 'button#add_node',
            searchNode  : 'input#nav-search-input',
            th          : 'table th'
        },

        events: {
            'click @ui.addNode'     : 'addNode',
            'keyup @ui.searchNode'  : 'filterCollection',
            'click @ui.navSearch'   : 'showSearch',
            'blur @ui.searchNode '  : 'closeSearch',
            'click @ui.th'          : 'toggleSort'
        },

        initialize: function(options){
            this.searchString = options.searchString;
            this.counter = 1;
        },

        filterCollection: function(){
            var value = this.ui.searchNode.val();
            if (value.length >= 2){
                this.trigger('collection:name:filter', value);
            }
        },

        onShow: function(){
            if (this.searchString) {
                this.showSearch();
                this.ui.searchNode.val(this.searchString);
            }
        },

        //collectionEvents: {
        //    "remove": function () {
        //        this.render()
        //    }
        //},

        toggleSort: function(e) {
            console.log('sort fired');
            var target = $(e.target),
                targetClass = target.attr('class');

            this.collection.setSorting(targetClass, this.counter);
            this.collection.fullCollection.sort();
            this.counter = this.counter * (-1)
            target.find('.caret').toggleClass('rotate').parent()
                  .siblings().find('.caret').removeClass('rotate');
        },

        showSearch: function(){
            this.ui.navSearch.addClass('active');
            this.ui.searchNode.focus();
        },

        closeSearch: function(){
            this.ui.navSearch.removeClass('active');
        },

        addNode: function(){
            App.navigate('nodes/add', {trigger: true});
        },
    });

    views.NodeAddWizardLayout = Backbone.Marionette.LayoutView.extend({
        template: nodeAddLayoutTpl,

        regions: {
            nav           : '#nav',
            header        : '#node-header',
            nodeAddStep   : '#node-add-step'
        },

        ui: {
            'nodes_page' : 'div#nodes-page',
        },

        events:{
            'click @ui.nodes_page' : 'breadcrumbClick'
        },

        breadcrumbClick: function(){
           App.navigate('nodes', {trigger: true})
        }
    });

    views.NodeAddStep = Backbone.Marionette.ItemView.extend({
        template: nodeAddStepTpl,

        ui: {
            'nodeAddBtn'     : 'button#node-add-btn',
            'nodeCancelBtn'  : 'button#node-cancel-btn',
            'nodeTypeSelect' : 'select.kube_type',
            'node_name'        : 'input#node_address',
            'spinner'          : '#address-spinner',
            'selectpicker'     : '.selectpicker',
        },

        events:{
            'click @ui.nodeCancelBtn'   : 'cancel',
            'click @ui.nodeAddBtn'      : 'complete',
            'change @ui.nodeTypeSelect' : 'changeKubeType',
        },

        changeKubeType: function(evt) {
            if (this.ui.nodeTypeSelect.value !== null) {
                this.model.set('kube_type', Number(evt.target.value));
            }
        },

        templateHelpers: {
            kubeTypes: backendData.kubeTypes
        },

        complete: function () {
            var that = this,
                preloader = $('#page-preloader'),
                val = this.ui.node_name.val(),
                pattern =  /^(?=.{1,255}$)[0-9A-Z](?:(?:[0-9A-Z]|-){0,61}[0-9A-Z])?(?:\.[0-9A-Z](?:(?:[0-9A-Z]|-){0,61}[0-9A-Z])?)*\.?$/i;

            App.getNodeCollection().done(function(nodeCollection){
                switch (true){
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
                        nodeCollection.create({
                            hostname: val,
                            status: 'pending',
                            kube_type: that.model.get('kube_type'),
                            install_log: ''
                        }, {
                            wait: true,
                            success: function(){
                                preloader.hide();
                                App.navigate('nodes', {trigger: true});
                                $.notify('Node "' + val + '" is added successfully', {
                                    autoHideDelay: 5000,
                                    clickToHide: true,
                                    globalPosition: 'bottom left',
                                    className: 'success',
                                });
                            },
                            error: function(){
                                preloader.hide();
                            }
                        });
                }
            });
        },

        cancel: function () {
            App.navigate('nodes', {trigger: true});
        },

        onRender: function(){
            this.model.set('kube_type', Number(this.ui.nodeTypeSelect.val()));
            this.ui.selectpicker.selectpicker();
        }
    });

    views.NodeDetailedLayout = Backbone.Marionette.LayoutView.extend({
        template: nodeDetailedLayoutTpl,

        regions: {
            nav: 'div#nav',
            breadcrumbs: 'div#breadcrumbs',
            sidebar: 'div#sidebar',
            tabContent: 'div#tab-content'
        },

        ui: {
            'nodes_page' : 'div#nodes-page',
            'redeploy'   : 'button#redeploy_node',
            'delete'     : 'button#delete_node',
            'tabItem'    : 'ul.nav-sidebar li'
        },

        events: {
            'click @ui.tabItem'    : 'changeTab',
            'click @ui.nodes_page' : 'breadcrumbClick',
            'click @ui.redeploy'   : 'redeployNode',
            'click @ui.delete'     : 'deleteNode'
        },

        initialize: function (options) {
            var that = this;
            App.getNodeCollection().done(function(nodeCollection){
                that.tab = options.tab;
                that.nodeId = options.nodeId;
                that.model = nodeCollection.get(options.nodeId);
            });
        },

        // commented out by bliss
        //childEvents: {
        //    render: function() {
        //      console.log('A child view has been rendered.');
        //    }
        //},

        changeTab: function (evt) {
            evt.preventDefault();
            var tgt = $(evt.target);
            if (tgt.hasClass('nodeGeneralTab')) App.navigate('nodes/' + this.nodeId + '/general', {trigger: true});
            else if (tgt.hasClass('nodeStatsTab')) App.navigate('nodes/' + this.nodeId + '/stats', {trigger: true});
            else if (tgt.hasClass('nodeLogsTab')) App.navigate('nodes/' + this.nodeId + '/logs', {trigger: true});
            else if (tgt.hasClass('nodeMonitoringTab')) App.navigate('nodes/' + this.nodeId + '/monitoring', {trigger: true});
            else if (tgt.hasClass('nodeTimelinesTab')) App.navigate('nodes/' + this.nodeId + '/timelines', {trigger: true});
            else if (tgt.hasClass('nodeConfigurationTab')) App.navigate('nodes/' + this.nodeId + '/configuration', {trigger: true});
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
                preloader = $('#page-preloader');

            App.getNodeCollection().done(function(nodeCollection){
                var model = nodeCollection.get(that.nodeId),
                    name = model.get('hostname');
                utils.modalDialogDelete({
                    title: "Delete " + name + "?",
                    body: "Are you sure want to delete node '" + name + "'?",
                    small: true,
                    show: true,
                    footer: {
                        buttonOk: function(){
                            preloader.show();
                            model.destroy({
                                wait: true,
                                complete: function(){ preloader.hide(); },
                            });
                        },
                        buttonCancel: true
                    }
                });
            });
        },

        breadcrumbClick: function(){
           App.navigate('nodes', {trigger: true})
        },

        templateHelpers: function(){
            return {
                tab: this.tab,
                hostname: this.model ? this.model.get('hostname') : 'hostname'
            }
        }
    });

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

        modelEvents: {
            'change': 'render'
        },

        nodeLogsTab: function(){
            App.navigate('nodes/' + this.model.id + '/logs', {trigger: true});
        },

        logSpoller: function(){
            this.ui.logSpollerButton.parent().children('.spoiler-body').collapse('toggle');
        },

        initialize: function () {
            this.listenTo(this.model, 'update_install_log', this.render);
            this.listenTo(this.model.collection, 'reset', this.render);
        }
    });

    views.NodeStatsTabView = Backbone.Marionette.ItemView.extend({
        template: nodeStatsTabTpl,
    });

    views.NodeLogsTabView = Backbone.Marionette.ItemView.extend({
        template: nodeLogsTabTpl,

        ui: {
            textarea: '.node-logs'
        },

        modelEvents: {
            'change': 'render'
        },

        initialize: function() {
            var that = this;
            _.bindAll(this, 'getLogs');
            App.getNodeCollection().done(function(nodeCollection){
                that.listenTo(nodeCollection, 'reset', that.render);
                that.getLogs();
            });
        },

        getLogs: function() {
            var that = this;
            this.model.getLogs(/*size=*/100).always(function(){
                // callbacks are called with model as a context
                if (!this.destroyed) {
                    this.set('timeout', setTimeout(that.getLogs, 10000));
                    that.render();
                }
            });
        },

        onBeforeRender: function () {
            var el = this.ui.textarea;
            if (typeof el !== 'object' || (el.scrollTop() + el.innerHeight()) === el[0].scrollHeight)
                this.logScroll = null;  // stick to bottom
            else
                this.logScroll = el.scrollTop();  // stay at this position
        },

        onRender: function () {
            if (this.logScroll === null)  // stick to bottom
                this.ui.textarea.scrollTop(this.ui.textarea[0].scrollHeight);
            else  // stay at the same position
                this.ui.textarea.scrollTop(this.logScroll);

            if (this.niceScroll !== undefined)
                this.niceScroll.remove();
            this.niceScroll = this.ui.textarea.niceScroll({
                cursorcolor: "#69AEDF",
                cursorwidth: "12px",
                cursorborder: "none",
                cursorborderradius: "none",
                background: "#E7F4FF",
                autohidemode: false,
                railoffset: 'bottom'
            });
        },

        onBeforeDestroy: function () {
            this.destroyed = true;
            clearTimeout(this.model.get('timeout'));
            if (this.niceScroll !== undefined)
                this.niceScroll.remove();
        }
    });

    views.NodeMonitoringTabViewItem = Backbone.Marionette.ItemView.extend({
        template: nodeItemGraphTpl,

        ui: {
            chart: '.graph-item'
        },

        initialize: function(options) {
            this.node = options.node;
            this.listenTo(this.node.collection, 'reset', this.render);
        },

        makeGraph: function(){
            var that = this;
            App.getNodeCollection().done(function(nodeCollection){
                var lines = that.model.get('lines'),
                    running = that.node.get('status') === 'running',
                    points = [],
                    options = {
                        title: that.model.get('title'),
                        axes: {
                            xaxis: {
                                label: 'time',
                                renderer: $.jqplot.DateAxisRenderer,
                            },
                            yaxis: {label: that.model.get('ylabel'), min: 0}
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
                        series: that.model.get('series'),
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
                if (that.model.has('seriesColors')) {
                    options.seriesColors = that.model.get('seriesColors');
                }

                for (var i=0; i<lines; i++) {
                    if (points.length < i+1) {
                        points.push([])
                    }
                }

                // If there is only one point, jqplot will display ugly plot with
                // weird grid and no line.
                // Remove this point to force jqplot to show noDataIndicator.
                if (that.model.get('points').length == 1)
                    that.model.get('points').splice(0);

                that.model.get('points').forEach(function(record){
                    for (var i=0; i<lines; i++) {
                        points[i].push([
                            utils.localizeDatetimeForUser(record[0]),
                            record[i+1]
                        ]);
                    }
                });
                that.ui.chart.jqplot(points, options);
            });
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

    views.NodeMonitoringTabView = Backbone.Marionette.CompositeView.extend({
        template: nodeMonitoringTabTpl,
        childView: views.NodeMonitoringTabViewItem,
        childViewContainer: '.graphs',
        childViewOptions: function() { return {node: this.model}; },

        modelEvents: {
            'change': 'render'
        },
    });

    views.NodeTimelinesTabView = Backbone.Marionette.ItemView.extend({
        template: nodeTimelinesTabTpl
    });

    views.NodeConfigurationTabView = Backbone.Marionette.ItemView.extend({
        template: nodeConfigurationTabTpl
    });

    views.NodesLayout = Backbone.Marionette.LayoutView.extend({
        template: nodeLayoutTpl,

        regions: {
            nav: 'div#nav',
            breadcrumbs: 'div#breadcrumbs',
            main: 'div#main',
            pager: 'div#pager'
        },

        initialize: function(){
            var that = this;
            this.listenTo(this.main, 'show', function(view){
                that.listenTo(view, 'collection:name:filter', that.filterNodeByName);
            });
        },

        filterNodeByName: function(value){
            this.trigger('collection:name:filter', value);
        }
    });

    return views;
});

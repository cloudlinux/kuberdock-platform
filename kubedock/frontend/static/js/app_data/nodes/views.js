define(['app_data/app', 'app_data/controller', 'marionette', 'app_data/utils',

        /* node tabs */
        'app_data/nodes/templates/node_tabs/layout.tpl',
        'app_data/nodes/templates/node_tabs/general.tpl',
        'app_data/nodes/templates/node_tabs/logs.tpl',
        'app_data/nodes/templates/node_tabs/monitoring/list.tpl',
        'app_data/nodes/templates/node_tabs/monitoring/item.tpl',
        'app_data/nodes/templates/node_tabs/timelines.tpl',

        /* nodelist */
        'app_data/nodes/templates/node_list/empty.tpl',
        'app_data/nodes/templates/node_list/item.tpl',
        'app_data/nodes/templates/node_list/list.tpl',

        'app_data/nodes/templates/add_node.tpl',
        'app_data/nodes/templates/layout.tpl',

        'jqplot', 'jqplot-axis-renderer',
        'bootstrap-select', 'tooltip'],
       function(App, Controller, Marionette, utils,

                nodeDetailedLayoutTpl,
                nodeGeneralTabTpl,
                nodeLogsTabTpl,
                nodeMonitoringTabTpl,
                nodeItemGraphTpl,
                nodeTimelinesTabTpl,

                nodeEmptyTpl,
                nodeItemTpl,
                nodeListTpl,

                nodeAddStepTpl,
                nodeLayoutTpl){

    var views = {};

    views.NodeEmpty = Backbone.Marionette.ItemView.extend({
        template: nodeEmptyTpl,
        tagName: 'tr'
    });

    views.NodeItem = Backbone.Marionette.ItemView.extend({
        template: nodeItemTpl,
        tagName: 'tr',

        ui: {
            'deleteNode' : '.deleteNode',
            'tooltip'    : '[data-toggle="tooltip"]'
        },

        events: {
            'click @ui.deleteNode' : 'deleteNode'
        },

        modelEvents: { 'change': 'render' },
        templateHelpers: function(){
            var model = this.model,
                kubeType = App.kubeTypeCollection.get(model.get('kube_type'));
            return {
                'kubeType': kubeType ? kubeType.get('name') : '',
            };
        },

        onDomRefresh: function(){ this.ui.tooltip.tooltip(); },

        deleteNode: function() {
            var that = this,
                name = that.model.get('hostname');

            utils.modalDialogDelete({
                title: 'Delete ' + name + '?',
                body: "Are you sure you want to delete node '" + name + "'?",
                small: true,
                show: true,
                footer: {
                    buttonOk: function() {
                        utils.preloader.show();
                        that.model.save({command: 'delete'}, {patch: true})
                            .always(utils.preloader.hide)
                            .fail(utils.notifyWindow);
                    },
                    buttonCancel: true
                }
            });
        }
    });

    views.NodesListView = Backbone.Marionette.CompositeView.extend({
        template           : nodeListTpl,
        childView          : views.NodeItem,
        emptyView          : views.NodeEmpty,
        childViewContainer : 'tbody',
        className          : 'container',

        ui: {
            th : 'table th'
        },

        events: {
            'click @ui.th' : 'toggleSort'
        },

        initialize: function(){
            this.collection.order = [
                {key: 'hostname', order: 1},
                {key: 'ip', order: 1},
                {key: 'kube_type', order: 1},
                {key: 'status', order: 1}
            ];
            this.collection.fullCollection.sort();
            this.collection.on('update reset', function(){
                this.fullCollection.sort();
            });
        },

        templateHelpers: function(){
            return {
                sortingType: this.collection.orderAsDict()
            }
        },

        search: function(data){
            this.collection.searchString = data;
            this.collection.refilter();
        },

        toggleSort: function(e) { //TODO move filter to model
            var targetClass = e.target.className;
            if (!targetClass) return;
            this.collection.toggleSort(targetClass);
            this.render();
        }
    });

    views.NodeAddStep = Backbone.Marionette.ItemView.extend({
        template: nodeAddStepTpl,

        ui: {
            'nodeAddBtn'     : 'button#node-add-btn',
            'nodeTypeSelect' : 'select.kube_type',
            'node_name'      : 'input#node_address',
            'selectpicker'   : '.selectpicker',
            'add_field'      : '.add',
            'remove_field'   : '.remove',
            'block_device'   : '.block-device'
        },

        events:{
            'click @ui.add_field'       : 'addField',
            'click @ui.remove_field'    : 'removeField',
            'click @ui.nodeAddBtn'      : 'complete',
            'focus @ui.node_name'       : 'removeError',
            'change @ui.nodeTypeSelect' : 'changeKubeType',
            'change @ui.block_device'   : 'changeLsDevices'
        },

        initialize: function(options){
            this.setupInfo = options.setupInfo;
            if (!this.setupInfo.AWS && this.setupInfo.ZFS){
                this.model.set('lsdevices', ['']);
            }
        },

        changeKubeType: function(evt) {
            if (this.ui.nodeTypeSelect.value !== null) {
                this.model.set('kube_type', Number(evt.target.value));
            }
        },

        changeLsDevices: function(evt){
            var target = $(evt.target),
                index = target.parent().index() - 1;
            this.model.get('lsdevices')[index] = target.val().trim();
        },

        templateHelpers: function(){
            return {
                kubeTypes: App.kubeTypeCollection.filter(function(kube){
                    return kube.id !== -1;  // "Internal service" kube-type
                }),
                setupInfo: this.setupInfo
            };
        },

        removeError: function(evt){ $(evt.target).removeClass('error'); },

        addField: function(){
            this.model.get('lsdevices').push('');
            this.render();
        },

        removeField: function(evt){
            var target = $(evt.target),
                index = target.parents('.relative').index() - 1;
            this.model.get('lsdevices').splice(index, 1);
            this.render();
        },

        complete: function () {
            var data = [],
                lsdevices,
                that = this,
                val = this.ui.node_name.val(),
                pattern =  /^(?=.{1,255}$)[0-9A-Z](?:(?:[0-9A-Z]|-){0,61}[0-9A-Z])?(?:\.[0-9A-Z](?:(?:[0-9A-Z]|-){0,61}[0-9A-Z])?)*\.?$/i;  // eslint-disable-line max-len

            val = val.replace(/\s+/g, '');
            this.ui.node_name.val(val);

            if (this.setupInfo.ZFS && !this.setupInfo.AWS) {
                lsdevices = _.without(this.model.get('lsdevices'), '');
                if (!lsdevices.length){
                    utils.notifyWindow('Block devices name can\'t be empty.');
                    that.ui.block_device.addClass('error');
                    return false;
                }
            }

            App.getNodeCollection().done(function(nodeCollection){
                switch (true){
                    case !val:
                        that.ui.node_name.addClass('error');
                        utils.notifyWindow('Enter valid hostname');
                        break;
                    case val && !pattern.test(val):
                        that.ui.node_name.addClass('error');
                        utils.notifyWindow(
                            'Hostname can\'t contain some special symbols like ' +
                            '"#", "%", "/" or start with "."');
                        break;
                    default:
                        utils.preloader.show();
                        if (that.setupInfo.ZFS && !that.setupInfo.AWS) {
                            data = {
                                hostname: val,
                                status: 'pending',
                                kube_type: that.model.get('kube_type'),
                                lsdevices: that.model.get('lsdevices'),
                                install_log: ''
                            };
                        } else {
                            data = {
                                hostname: val,
                                status: 'pending',
                                kube_type: that.model.get('kube_type'),
                                install_log: ''
                            };
                        }
                        nodeCollection.create(data, {
                            wait: true,
                            complete: utils.preloader.hide,
                            success:  function(){
                                App.navigate('nodes', {trigger: true});
                                utils.notifyWindow(
                                    'Node "' + val + '" is added successfully',
                                    'success'
                                );
                            },
                            error: function(collection, response){
                                that.ui.node_name.addClass('error');
                                utils.notifyWindow(response);
                            },
                        });
                }
            });
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
            tabContent: 'div#tab-content'
        },

        ui: {
            // 'redeploy'   : 'button#redeploy_node',
            'delete'     : 'button#delete_node',
            'tabItem'    : 'ul.nav-sidebar li'
        },

        events: {
            'click @ui.tabItem'    : 'changeTab',
            // 'click @ui.redeploy'   : 'redeployNode',
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

        onBeforeShow: function(){
            utils.preloader.show();
        },

        onShow: function(){
            utils.preloader.hide();
        },

        changeTab: function (evt) {
            evt.preventDefault();
            var tgt = $(evt.target);
            if (tgt.not('li')) tgt = tgt.parent('li');
            if (tgt.hasClass('nodeGeneralTab'))
                App.navigate('nodes/' + this.nodeId + '/general', {trigger: true});
            else if (tgt.hasClass('nodeLogsTab'))
                App.navigate('nodes/' + this.nodeId + '/logs', {trigger: true});
            else if (tgt.hasClass('nodeMonitoringTab'))
                App.navigate('nodes/' + this.nodeId + '/monitoring', {trigger: true});
            else if (tgt.hasClass('nodeTimelinesTab'))
                App.navigate('nodes/' + this.nodeId + '/timelines', {trigger: true});
        },

        // redeployNode: function() {
        //     var that = this,
        //         name = that.model.get('hostname');
        //
        //     utils.modalDialog({
        //         title: "Re-install " + name + "?",
        //         body: "Are you sure you want to re-install node '" + name + "'?",
        //         small: true,
        //         show: true,
        //         footer: {
        //             buttonOk: function(){
        //                 $.ajax({
        //                     url: '/api/nodes/redeploy/' + that.model.id,
        //                 });
        //             },
        //             buttonCancel: true
        //         }
        //     });
        // },

        deleteNode: function() {
            var that = this;

            App.getNodeCollection().done(function(nodeCollection){
                var model = nodeCollection.get(that.nodeId),
                    name = model.get('hostname');
                utils.modalDialogDelete({
                    title: 'Delete ' + name + '?',
                    body: "Are you sure you want to delete node '" + name + "'?",
                    small: true,
                    show: true,
                    footer: {
                        buttonOk: function(){
                            utils.preloader.show();
                            model.save({command: 'delete'}, {patch: true})
                                .always(utils.preloader.hide)
                                .fail(utils.notifyWindow);
                        },
                        buttonCancel: true
                    }
                });
            });
        },

        templateHelpers: function(){
            return {
                tab: this.tab,
                hostname: this.model ? this.model.get('hostname') : 'hostname'
            };
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
                if (!that.destroyed) {
                    this.set('timeout', setTimeout(that.getLogs, 10000));
                    that.render();
                }
            });
        },

        onBeforeRender: function () {
            var el = this.ui.textarea;
            if (typeof el !== 'object' ||
                    (el.scrollTop() + el.innerHeight()) === el[0].scrollHeight)
                this.logScroll = null;  // stick to bottom
            else
                this.logScroll = el.scrollTop();  // stay at this position
        },

        onRender: function () {
            if (this.logScroll === null)  // stick to bottom
                this.ui.textarea.scrollTop(this.ui.textarea[0].scrollHeight);
            else  // stay at the same position
                this.ui.textarea.scrollTop(this.logScroll);
        },

        onBeforeDestroy: function () {
            this.destroyed = true;
            clearTimeout(this.model.get('timeout'));
        }
    });

    views.NodeMonitoringTabViewItem = Backbone.Marionette.ItemView.extend({
        template: nodeItemGraphTpl,

        ui: {
            chart: '.graph-item'
        },

        initialize: function(options) {
            this.node = options.node;
            this.error = options.error;
            this.listenTo(this.node.collection, 'reset', this.render);
        },

        makeGraph: function(){
            var lines = this.model.get('lines'),
                points = [],
                error;

            if (this.error)
                error = this.error;
            else if (this.node.get('status') === 'running')
                error = 'Collecting data... plot will be dispayed in a few minutes.';
            else
                error = "Couldn't connect to the node (maybe it's rebooting)...";

            var options = {
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
                    indicator: error,
                    axes: {
                        xaxis: {
                            min: App.currentUser.localizeDatetime(+new Date() - 1000 * 60 * 20),
                            max: App.currentUser.localizeDatetime(),
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

            for (var i = 0; i < lines; i++) {
                if (points.length < i + 1) {
                    points.push([]);
                }
            }

            // If there is only one point, jqplot will display ugly plot with
            // weird grid and no line.
            // Remove this point to force jqplot to show noDataIndicator.
            if (this.model.get('points').length === 1)
                this.model.get('points').splice(0);

            this.model.get('points').forEach(function(record){
                for (var i = 0; i < lines; i++) {
                    points[i].push([
                        App.currentUser.localizeDatetime(record[0]),
                        record[i + 1]
                    ]);
                }
            });
            this.ui.chart.jqplot(points, options);
        },

        onDomRefresh: function(){
            try {
                this.makeGraph();
            } catch (e){
                console.log('Cannot display graph' + e);
            }
        },
    });

    views.NodeMonitoringTabView = Backbone.Marionette.CompositeView.extend({
        template: nodeMonitoringTabTpl,
        childView: views.NodeMonitoringTabViewItem,
        childViewContainer: '.graphs',
        childViewOptions: function(){
            return {node: this.model, error: this.error};
        },
        onBeforeRender: function(){ utils.preloader.show(); },
        onShow: function(){ utils.preloader.hide(); },
        modelEvents: {
            'change': 'render'
        },

        initialize: function(options){
            this.error = options.error;
            if (this.error)
                this.collection.setEmpty();
        },
    });

    views.NodeTimelinesTabView = Backbone.Marionette.ItemView.extend({
        template: nodeTimelinesTabTpl
    });

    views.NodesLayout = Backbone.Marionette.LayoutView.extend({
        template: nodeLayoutTpl,

        regions: {
            nav: 'div#nav',
            breadcrumbs: 'div#breadcrumbs',
            main: 'div#main',
            pager: 'div#pager'
        },

        onBeforeShow: function(){ utils.preloader.show(); },
        onShow: function(){ utils.preloader.hide(); },
    });

    return views;
});

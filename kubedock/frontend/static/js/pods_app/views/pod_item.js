define(['pods_app/app',
        'tpl!pods_app/templates/layout_pod_item.tpl',
        'tpl!pods_app/templates/page_header_title.tpl',
        'tpl!pods_app/templates/page_info_panel.tpl',
        'tpl!pods_app/templates/page_container_item.tpl',
        'tpl!pods_app/templates/pod_item_controls.tpl',
        'tpl!pods_app/templates/pod_item_graph.tpl',
        'moment-timezone', 'pods_app/utils',
        'bootstrap', 'bootstrap-editable', 'jqplot', 'jqplot-axis-renderer', 'numeral'
        ],
       function(Pods,
                layoutPodItemTpl,
                pageHeaderTitleTpl,
                pageInfoPanelTpl,
                pageContainerItemTpl,
                podItemControlsTpl,
                podItemGraphTpl,
                moment, utils){

    Pods.module('Views.Item', function(Item, App, Backbone, Marionette, $, _){

        function localizeDatetime(dt, tz){
            if (typeof tz === 'string') {
                // accept timezones in form 'Europe/London (+0000)'
                tz = tz.split(' (', 1)[0];
            }
            try {
                return moment(dt).tz(tz).format('HH:mm:ss YYYY-MM-DD');
            } catch (e){
                console.log(e);
            }
            return moment(dt).format('HH:mm:ss YYYY-MM-DD');
        }

        Item.PodItemLayout = Backbone.Marionette.LayoutView.extend({
            template : layoutPodItemTpl,

            regions: {
                masthead : '#masthead-title',
                controls : '#item-controls',
                info     : '#item-info',
                contents : '#layout-contents'
            },

            ui: {
                podsList : '.podsList'
            },

            events: {
                'click @ui.podsList' : 'showPodsList',
            },

            initialize: function(){
                var that = this;
                this.listenTo(this.controls, 'show', function(view){
                    that.listenTo(view, 'display:pod:stats', that.showPodStats);
                    that.listenTo(view, 'display:pod:list', that.showPodList);
                });
            },
            showPodStats: function(data){
                this.trigger('display:pod:stats', data);
            },

            showPodList: function(data){
                this.trigger('display:pod:list', data);
            },

            showPodsList: function(){
                Pods.navigate('pods', {trigger: true});
            }
        });

        Item.PageHeader = Backbone.Marionette.ItemView.extend({
            template: pageHeaderTitleTpl
        });

        // View for showing a single container item as a container in containers list
        Item.InfoPanelItem = Backbone.Marionette.ItemView.extend({
            template    : pageContainerItemTpl,
            tagName     : 'tr',
            className   : 'container-item',
            /*className   : function(){
                return this.model.is_checked ? 'container-item checked' : 'container-item';
            },*/

            templateHelpers: function(){
                var kubes = this.model.get('kubes'),
                    startedAt = this.model.get('startedAt'),
                    modelIndex = this.model.collection.indexOf(this.model);

                return {
                    kubes: kubes ? kubes : 0,
                    startedAt: typeof(startedAt) == 'undefined' ? 'Stopped' :
                            localizeDatetime(startedAt, userProfile.timezone),
                    updateIsAvailable: this.model.updateIsAvailable,
                }
            },

            ui: {
                'start'            : '.start-btn',
                'stop'             : '.stop-btn',
                'delete'           : '.terminate-btn',
                'updateContainer'  : '.container-update',
                'checkForUpdate'   : '.check-for-update',
                'containerPageBtn' : '.container-page-btn',
                /*'checkbox'         : 'input[type="checkbox"]'*/
            },

            events: {
                /*'click @ui.start'              : 'startItem',
                'click @ui.stop'               : 'stopItem',
                'click @ui.delete'             : 'deleteItem',*/
                'click @ui.updateContainer'    : 'updateItem',
                'click @ui.checkForUpdate'     : 'checkForUpdate',
                'click @ui.containerPageBtn'   : 'containerPage',
                /*'click @ui.checkbox'           : 'checkItem'*/
            },

            /*startItem: function(){
                App.WorkFlow.commandPod('start', this.model.get('parentID'));
            },
            stopItem: function(){
                App.WorkFlow.commandPod('stop', this.model.get('parentID'));
            },*/
            updateItem: function(){
                App.WorkFlow.updateContainer(this.model);
            },
            checkForUpdate: function(){
                App.WorkFlow.checkContainerForUpdate(this.model).done(this.render);
            },

            /*deleteItem: function(evt){
                var that = this,
                    name = that.model.get('name');
                utils.modalDialogDelete({
                    title: "Delete container?",
                    body: "Are you sure want to delete container '" + name + "'?",
                    small: true,
                    show: true,
                    footer: {
                        buttonOk: function(){
                            that.command(evt, 'delete');
                        },
                        buttonCancel: true
                    }
                });
            },*/

            /*checkItem: function(){
                if (this.model.is_checked){
                    this.$el.removeClass('checked');
                    this.model.is_checked = false;
                } else {
                    this.model.is_checked = true;
                    this.$el.addClass('checked');
                }
                this.render();
            },*/

            containerPage: function(evt){
                evt.stopPropagation();
                this.checked = false;
                App.navigate('poditem/' + this.model.get('parentID') + '/' + this.model.get('name') , {trigger: true});
            },
        });

        Item.InfoPanel = Backbone.Marionette.CompositeView.extend({
            template  : pageInfoPanelTpl,
            childView: Item.InfoPanelItem,
            childViewContainer: "tbody",

            ui: {
                /*count             : '.count',
                defaultTableHead  : '.main-table-head',
                containersControl : '.containersControl',
                checkAllItems     : 'table thead .custom',*/
            },

            events: {
                /*'click .stop-checked'     : 'stopItems',
                'click .start-checked'    : 'startItems',
                'click @ui.checkAllItems' : 'checkAllItems',*/
            },

            /*childEvents: {
                render: function() {
                    var col = this.collection,
                        count = 0;
                    if (col.length != 0){
                        _.each(col.models, function(model){
                            if (model.is_checked) count++
                        });
                    }
                    if ( count != 0 ) {
                        this.ui.count.text(count + ' Item');
                        this.ui.containersControl.show();
                        this.ui.defaultTableHead.addClass('min-opacity');
                    } else {
                        this.ui.containersControl.hide();
                        this.ui.defaultTableHead.removeClass('min-opacity');
                    }
                    if (count >= 2) this.ui.count.text(count + ' Items');
                }
            },

            checkAllItems: function(){
                var col = this.collection;

                _.each(col.models, function(model){
                    model.is_checked = true
                });
                this.render();
            },*/

            /*command: function(cmd){
                var preloader = $('#page-preloader');
                    preloader.show();
                var model;
                var containers = [];
                containerCollection.forEach(function(i){
                    if (i.get('checked') === true){
                        model = App.WorkFlow.getCollection().fullCollection.get(i.get('parentID'));
                        _.each(model.get('containers'), function(itm){
                            if(itm.name == i.get('name'))
                                containers.push(itm.containerID);
                        });
                    }
                });
                if(model)
                model.save({'command': cmd, 'containers_action': containers}, {
                    success: function(){
                        preloader.hide();
                    },
                    error: function(model, response, options, data){
                        preloader.hide();
                        utils.notifyWindow(response);
                    }
                });
            },*/

            /*startItems: function(evt){
                this.command('start');
            },

            stopItems: function(evt){
                this.command('stop');
            },*/
        });

        Item.ControlsPanel = Backbone.Marionette.ItemView.extend({
            template: podItemControlsTpl,
            tagName: 'div',
            className: 'pod-controls',

            ui: {
                close : 'span.close',
				message: '.message-wrapper'
            },
            onShow: function(){
                if (postDescription){
                    this.ui.close.parents('.message-wrapper').slideDown();

                }
            },

            events: {
                'click .stats-btn'     : 'statsItem',
                'click .list-btn'      : 'listItem',
                'click .start-btn'     : 'startItem',
                'click .stop-btn'      : 'stopItem',
                'click .terminate-btn' : 'terminateItem',
                'click @ui.close'      : 'closeMessage'
            },

            initialize: function(options){
                this.graphs = options.graphs;
                this.listenTo(App.WorkFlow.getCollection(),
                              'pods:collection:fetched', this.render);
            },

            templateHelpers: function(){
                var publicIP = this.model.has('labels')
                        ? this.model.get('labels')['kuberdock-public-ip']
                        : '',
                    publicName = this.model.has('public_aws')
                        ? this.model.get('public_aws')
                        : '',
                    graphs = this.graphs,
                    kubeType = this.getKubeById(),
                    kubes = _.reduce(this.model.get('containers'), function(memo, c) {
                        return memo + c.kubes
                    }, 0),
                    kubesPrice = this.getFormattedPrice(kubes * kubeType.kube_price),
                    package = this.getUserPackage();
                    var public_address = "%PUBLIC_ADDRESS%";
                    var r = new RegExp("(" + public_address + ")", "gi");
                    var public_ip = "Public address"
                    if (this.model.get('public_ip')){
                        public_ip = this.model.get('public_ip');
                    }
                    postDescription = postDescription.replace(r, public_ip);

                return {
                    postDescription : postDescription,
                    publicIP        : publicIP,
                    publicName      : publicName,
                    graphs          : graphs,
                    kubeType        : kubeType,
                    kubes           : kubes,
                    kubesPrice      : kubesPrice,
                    podName         : this.model.get('name'),
                    package         : package,
                };
            },

            getItem: function(){
                return App.WorkFlow.getCollection().fullCollection.get(this.model.id);
            },

            statsItem: function(evt){
                evt.stopPropagation();
                var item = this.getItem();
                this.trigger('display:pod:stats', item);
            },

            closeMessage: function(){
                this.ui.close.parents('.message-wrapper').slideUp();
                postDescription = '';

            },

            onBeforeDestroy: function(){
                this.closeMessage();
            },

            listItem: function(evt){
                evt.stopPropagation();
                var item = this.getItem();
                this.trigger('display:pod:list', item);
            },

            startItem: function(evt){
                var item = this.getItem(),
                    that = this,
                    preloader = $('#page-preloader');
                    preloader.show();
                evt.stopPropagation();
                item.save({command: 'start'}, {
                    wait: true,
                    success: function(model, response, options){
                        preloader.hide();
                        that.render();
                    },
                    error: function(model, response, options, data){
                        preloader.hide();
                        that.render();
                        utils.notifyWindow(response);
                    }
                });
            },

            stopItem: function(evt){
                var item = this.getItem(),
                    that = this,
                    preloader = $('#page-preloader');
                    preloader.show();
                evt.stopPropagation();
                item.save({command: 'stop'}, {
                    wait: true,
                    success: function(model, response, options){
                        preloader.hide();
                        that.render();
                    },
                    error: function(model, response, options, data){
                        preloader.hide();
                        utils.notifyWindow(response);
                    }
                });
            },

            terminateItem: function(evt){
                var that = this,
                    item = that.getItem(),
                    name = item.get('name'),
                    preloader = $('#page-preloader');
                utils.modalDialogDelete({
                    title: "Delete " + name + "?",
                    body: "Are you sure you want to delete pod '" + name + "'?",
                    small: true,
                    show: true,
                    footer: {
                        buttonOk: function(){
                            preloader.show();
                            item.destroy({
                                wait: true,
                                success: function(){
                                    var col = App.WorkFlow.getCollection();
                                    preloader.hide();
                                    col.remove(item);
                                    Pods.navigate('pods', {trigger: true});
                                },
                                error: function(model, response, options, data){
                                    preloader.hide();
                                    utils.notifyWindow(response);
                                }
                            });
                        },
                        buttonCancel: true
                    }
                });
            },

            getKubeById: function() {
                var kubeId = this.model.get('kube_type'),
                    packageKube = _.find(packageKubes, function(p) {
                        return p.package_id == userPackage && p.kube_id == kubeId;
                    }),
                    kube = _.findWhere(kubeTypes, {id: kubeId});

                return _.extend(packageKube || { kube_price: 0 }, kube);
            },

            getUserPackage: function() {
                return _.find(packages, function(e) {
                    return e.id == userPackage
                });
            },

            getFormattedPrice: function(price, format) {
                var package = this.getUserPackage();
                format = typeof format !== 'undefined' ? format : '0.00';

                return package.prefix + numeral(price).format(format) + package.suffix;
            }
        });

        Item.PodGraphItem = Backbone.Marionette.ItemView.extend({
            template: podItemGraphTpl,

            initialize: function(options){ this.pod = options.pod; },

            ui: {
                chart: '.graph-item'
            },

            onShow: function(){
                var lines = this.model.get('lines'),
                    running = this.pod.get('status') === 'running',
                    options = {
                    title: this.model.get('title'),
                    axes: {
                        xaxis: {label: 'time', renderer: $.jqplot.DateAxisRenderer},
                        yaxis: {label: this.model.get('ylabel'), min: 0}
                    },
                    seriesDefaults: {
                        showMarker: false,
                        rendererOptions: {
                            smooth: true
                        }
                    },
                    grid: {
                        background: '#ffffff',
                        drawBorder: false,
                        shadow: false
                    },
                    noDataIndicator: {
                        show: true,
                        indicator: !running ? 'Pod is not running...' :
                            'Collecting data... plot will be dispayed in a few minutes.',
                        axes: {
                            xaxis: {
                                min: new Date(+new Date() - 1000*60*20),
                                max: new Date(),
                                tickOptions: {formatString:'%H:%M'},
                                tickInterval: '5 minutes',
                            },
                            yaxis: {min: 0, max: 150, tickInterval: 50}
                        }
                    },
                };

                var points = [];
                for (var i=0; i<lines; i++) {
                    if (points.length < i+1) {
                        points.push([]);
                    }
                }

                this.model.get('points').forEach(function(record){
                    for (var i=0; i<lines; i++) {
                        points[i].push([record[0], record[i+1]]);
                    }
                });

                try {
                    this.ui.chart.jqplot(points, options);
                }
                catch(e){
                    console.log('Cannot display graph');
                }
            }
        });

        Item.PodGraph = Backbone.Marionette.CollectionView.extend({
            childView: Item.PodGraphItem,
            childViewOptions: function() {
                return {pod: this.model};
            },

            initialize: function(options){
                this.listenTo(App.WorkFlow.getCollection(),
                              'pods:collection:fetched', this.render);
            },
        });

    });

    return Pods.Views.Item;
});

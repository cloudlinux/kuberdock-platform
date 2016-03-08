define(['app_data/app',
        'tpl!app_data/pods/templates/layout_pod_item.tpl',
        'tpl!app_data/pods/templates/page_header_title.tpl',
        'tpl!app_data/pods/templates/page_info_panel.tpl',
        'tpl!app_data/pods/templates/page_container_item.tpl',
        'tpl!app_data/pods/templates/pod_item_controls.tpl',
        'tpl!app_data/pods/templates/pod_item_upgrade_resources.tpl',
        'tpl!app_data/pods/templates/pod_item_upgrade_container_resources.tpl',
        'tpl!app_data/pods/templates/pod_item_graph.tpl',
        'moment-timezone', 'app_data/utils',
        'bootstrap', 'bootstrap-editable', 'jqplot', 'jqplot-axis-renderer', 'numeral', 'bbcode'],
       function(App,
                layoutPodItemTpl,
                pageHeaderTitleTpl,
                pageInfoPanelTpl,
                pageContainerItemTpl,
                podItemControlsTpl,
                upgradeResourcesTpl,
                upgradeContainerResourcesTpl,
                podItemGraphTpl,
                moment, utils){

    var podItem = {};

    podItem.PodItemLayout = Backbone.Marionette.LayoutView.extend({
        template : layoutPodItemTpl,

        regions: {
            nav      : '#item-navbar',
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

        onBeforeShow: utils.preloader.show,
        onShow: utils.preloader.hide,

        showPodsList: function(){
            App.navigate('pods', {trigger: true});
        }
    });

    podItem.PageHeader = Backbone.Marionette.ItemView.extend({
        template: pageHeaderTitleTpl
    });

    // View for showing a single container item as a container in containers list
    podItem.InfoPanelItem = Backbone.Marionette.ItemView.extend({
        template    : pageContainerItemTpl,
        tagName     : 'tr',
        className   : 'container-item',
        /*className   : function(){
            return this.model.is_checked ? 'container-item checked' : 'container-item';
        },*/

        templateHelpers: function(){
            var kubes = this.model.get('kubes'),
                startedAt = this.model.get('startedAt'),
                imagename = this.model.get('image'),
                imagetag = null;

            if (/[^/:]+:[^/:]+$/.test(imagename)) {
                var pos = imagename.lastIndexOf(':');
                imagetag = imagename.substr(pos + 1);
                imagename = imagename.substr(0, pos);
            }

            return {
                kubes: kubes ? kubes : 0,
                startedAt: startedAt ? App.currentUser.localizeDatetime(startedAt) : 'Not deployed yet',
                updateIsAvailable: this.model.updateIsAvailable,
                imagename: imagename,
                imagetag: imagetag
            };
        },

        ui: {
            'start'            : '.start-btn',
            'stop'             : '.stop-btn',
            'delete'           : '.terminate-btn',
            'updateContainer'  : '.container-update',
            'checkForUpdate'   : '.check-for-update',
            'containerPageBtn' : '.container-page-btn',
        },

        events: {
            'click @ui.updateContainer'    : 'updateItem',
            'click @ui.checkForUpdate'     : 'checkForUpdate',
            'click @ui.containerPageBtn'   : 'containerPage',
        },

        modelEvents: {
            'change': 'render'
        },

        updateItem: function(){
            App.updateContainer(this.model);
        },

        checkForUpdate: function(){
            App.checkContainerForUpdate(this.model).done(this.render);
        },

        containerPage: function(evt){
            evt.stopPropagation();
            this.checked = false;
                App.navigate('pods/poditem/' + this.model.getPod().id + '/' +
                             this.model.get('name') , {trigger: true});
        },
    });

    podItem.InfoPanel = Backbone.Marionette.CompositeView.extend({
        template  : pageInfoPanelTpl,
        childView: podItem.InfoPanelItem,
        childViewContainer: "tbody",
    });

    podItem.ControlsPanel = Backbone.Marionette.ItemView.extend({
        template: podItemControlsTpl,
        tagName: 'div',
        className: 'pod-controls',

        ui: {
            close : 'span.close',
            message: '.message-wrapper'
        },
        onShow: function(){
            if (this.model.postDescription)
                this.ui.close.parents('.message-wrapper').slideDown();
        },

        events: {
            'click .start-btn'        : 'startItem',
            'click .pay-and-start-btn': 'payStartItem',
            'click .restart-btn'      : 'restartItem',
            'click .stop-btn'         : 'stopItem',
            'click .terminate-btn'    : 'terminateItem',
            'click @ui.close'         : 'closeMessage'
        },

        modelEvents: {
            'change': 'render',
        },

        initialize: function(options){
            this.graphs = !!options.graphs;
            this.upgrade = !!options.upgrade;

            // if got postDescription, save it
            if (backendData.postDescription){
                var r = /(%PUBLIC_ADDRESS%)/gi,
                    publicIP = this.model.get('public_ip') || "...";
                App.storage['postDescription.' + this.model.id] =
                    backendData.postDescription.replace(r, publicIP);
                delete backendData.postDescription;
            }
            // if have saved postDescription, put it in model
            var postDescription = App.storage['postDescription.' + this.model.id];
            if (postDescription)
                this.model.postDescription = postDescription;
        },

        templateHelpers: function(){
            var publicName = this.model.has('public_aws')
                    ? this.model.get('public_aws')
                    : '',
                kubes = this.model.getKubes(),
                pkg = App.userPackage,
                kubeId = this.model.get('kube_type'),
                kubeType = App.kubeTypeCollection.get(kubeId),
                hasPorts = this.model.get('containers').any(function(c) {
                    return c.get('ports') && c.get('ports').length;
                });

            this.model.recalcInfo(pkg);

            return {
                hasPorts        : hasPorts,
                postDescription : this.encodeBBCode(this.model.postDescription),
                publicIP        : this.model.get('public_ip'),
                publicName      : publicName,
                graphs          : this.graphs,
                upgrade         : this.upgrade,
                kubeType        : kubeType,
                kubes           : kubes,
                totalPrice      : this.model.totalPrice,
                limits          : this.model.limits,
                podName         : this.model.get('name'),
                period          : pkg.get('period'),
            };
        },

        onDomRefresh: function(){
            if (this.model.postDescription)
                this.ui.close.parents('.message-wrapper').show();
        },

        closeMessage: function(){
            this.ui.close.parents('.message-wrapper').slideUp();
            delete this.model.postDescription;
            delete App.storage['postDescription.' + this.model.id];
        },

        startItem: function(evt){
            evt.stopPropagation();
            App.commandPod('start', this.model).always(this.render);
        },

        payStartItem: function(evt){
            evt.stopPropagation();
            var that = this;
            App.getSystemSettingsCollection().done(function(collection){
                var billingUrl = utils.getBillingUrl(collection);
                if (billingUrl === null) { // no billing
                    App.commandPod('start', that.model).always(that.render);
                }
                else if (billingUrl !== undefined) { // we got url, undefined means no URL for some reason
                    var podObj = encodeURIComponent(JSON.stringify(that.model.attributes)),
                        userObj = encodeURIComponent(JSON.stringify(App.currentUser.attributes));
                    window.location = billingUrl
                        + (billingUrl.indexOf('?') === -1 ? '?' : '&')
                        + 'pod=' + podObj + '&user=' + userObj;
                }
            });
        },

        restartItem: function(evt){
            var that = this,
                name = this.model.get('name');
            utils.modalDialog({
                title: 'Confirm restarting of application ' + _.escape(name),
                body: 'You can wipe out all the data and redeploy the '
                    + 'application or you can just restart and save data '
                    + 'in Persistent storages of your application.',
                small: true,
                show: true,
                footer: {
                    buttonOk: function(){
                        that.model.set('commandOptions', {});
                        App.commandPod('redeploy', that.model)
                            .done(function(){
                                utils.notifyWindow('Pod will be restarted soon', 'success');
                            })
                            .always(that.render);
                    },
                    buttonCancel: function(){
                        utils.modalDialog({
                            title: 'Confirm restarting of application ' + _.escape(name),
                            body: 'Are you sure you want to delete all data? You will '
                                + 'not be able to recover this data if you continue.',
                            small: true,
                            show: true,
                            footer: {
                                buttonOk: function(){
                                    App.commandPod('redeploy', that.model, {wipeOut: true})
                                        .done(function(){
                                            utils.notifyWindow('Pod will be restarted soon', 'success');
                                        })
                                        .always(that.render);
                                },
                                buttonOkText: 'Continue',
                                buttonOkClass: 'btn-danger',
                                buttonCancel: true
                            }
                        });
                    },
                    buttonOkText: 'Just Restart',
                    buttonCancelText: 'Wipe Out',
                    buttonCancelClass: 'btn-danger',
                }
            });
        },

        stopItem: function(evt){
            evt.stopPropagation();
            App.commandPod('stop', this.model).always(this.render);
        },

        terminateItem: function(evt){
            var item = this.model,
                name = item.get('name');
            utils.modalDialogDelete({
                title: "Delete " + _.escape(name) + "?",
                body: "Are you sure you want to delete pod '" + _.escape(name) + "'?",
                small: true,
                show: true,
                footer: {
                    buttonOk: function(){
                        utils.preloader.show();
                        item.destroy({wait: true})
                            .always(utils.preloader.hide)
                            .fail(utils.notifyWindow)
                            .done(function(){
                                App.getPodCollection().done(function(col){
                                    col.remove(item);
                                });
                            });
                    },
                    buttonCancel: true
                }
            });
        },

        encodeBBCode: function(val) {
            if (val !== undefined) {
                var parser = new BBCodeParser(BBCodeParser.defaultTags());
                return parser.parseString(val);
            }
        }
    });

    podItem.PodGraphItem = Backbone.Marionette.ItemView.extend({
        template: podItemGraphTpl,

        initialize: function(options){ this.pod = options.pod; },

        ui: {
            chart: '.graph-item'
        },

        onShow: function(){
            var lines = this.model.get('lines'),
                running = this.pod.get('status') === 'running',
                series = this.model.get('series'),
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
                series: series,
                grid: {
                    background: '#ffffff',
                    drawBorder: false,
                    shadow: false
                },
                legend: {
                    show: true,
                    placement: 'insideGrid'
                },
                noDataIndicator: {
                    show: true,
                    indicator: !running ? 'Pod is not running...' :
                        'Collecting data... plot will be dispayed in a few minutes.',
                    axes: {
                        xaxis: {
                            min: App.currentUser.localizeDatetime(+new Date() - 1000*60*20),
                            max: App.currentUser.localizeDatetime(),
                            tickOptions: {formatString:'%H:%M'},
                            tickInterval: '5 minutes',
                        },
                        yaxis: {min: 0, max: 150, tickInterval: 50}
                    }
                },
            };

            var points = [];
            for (var i=0; i<lines;i++)
                points.push([]);

            // If there is only one point, jqplot will display ugly plot with
            // weird grid and no line.
            // Remove this point to force jqplot to show noDataIndicator.
            if (this.model.get('points').length == 1)
                this.model.get('points').splice(0);

            this.model.get('points').forEach(function(record){
                var time = App.currentUser.localizeDatetime(record[0]);
                for (var i=0; i<lines; i++)
                    points[i].push([time, record[i+1]]);
            });
            this.ui.chart.jqplot(points, options);
        }
    });

    podItem.PodGraph = Backbone.Marionette.CollectionView.extend({
        childView: podItem.PodGraphItem,
        childViewOptions: function() {
            return {pod: this.model};
        },

        modelEvents: {
            'change': 'render'
        },
    });

    podItem.UpgradeContainerResources = Backbone.Marionette.ItemView.extend({
        template: upgradeContainerResourcesTpl,
        tagName: 'tr',

        ui: {
            price: '.upgrade-price',
            kubes: '.upgrade-kubes',
            moreKubes: '.upgrade-kubes-more',
            lessKubes: '.upgrade-kubes-less',
        },

        events: {
            'click @ui.moreKubes': 'addKube',
            'click @ui.lessKubes': 'removeKube',
            'change @ui.kubes': 'changeKubes',
        },

        modelEvents: {
            'change': 'render',
        },

        initialize: function(options){
            this.pkg = options.pkg;
            this.modelOrig = options.modelOrig;
        },

        templateHelpers: function(){
            var image = /^(.+?)(?::([^/:]+))?$/.exec(this.model.get('image')),
                imagename = image[1],
                imagetag = image[2],
                kube = this.model.getPod().getKubeType(),
                kubesChange = this.model.get('kubes') - this.modelOrig.get('kubes');

            return {
                imagename: imagename,
                imagetag: imagetag,
                upgradePrice: this.pkg.getFormattedPrice(this.pkg.priceFor(kube.id) * kubesChange),
                pod: this.model.getPod(),
                limits: this.model.limits,
            };
        },

        addKube: function(){ this.ui.kubes.val(+this.ui.kubes.val() + 1).change(); },
        removeKube: function(){ this.ui.kubes.val(+this.ui.kubes.val() - 1).change(); },
        changeKubes: function(){
            var kubes = Math.max(1, Math.min(10, +this.ui.kubes.val()));
            this.ui.kubes.val(kubes);
            this.model.set('kubes', kubes);
        },
    });

    podItem.UpgradeResources = Backbone.Marionette.CompositeView.extend({
        template: upgradeResourcesTpl,
        childView: podItem.UpgradeContainerResources,
        childViewContainer: 'tbody',
        childViewOptions: function(model){
            return {
                modelOrig: this.modelOrig.get('containers').get(model.id),
                pkg: this.pkg,
            };
        },

        ui: {
            cancel: '.cancel-upgrade',
            order: '.apply-upgrade'
        },

        events: {
            'click @ui.cancel': 'cancel',
            'click @ui.order': 'order',
        },

        modelEvents: {
            'change:containers[*].kubes': 'render',
        },

        initialize: function(options){
            this.pkg = App.userPackage;
            this.modelOrig = options.modelOrig;
            this.containerName = options.containerName;
        },

        filter: function (child) {
            return this.containerName == null || child.get('name') === this.containerName;
        },

        templateHelpers: function(){
            this.model.recalcInfo(this.pkg);
            return {
                period: this.pkg.get('period'),
                totalPrice: this.model.totalPrice,
                upgradePrice: this.pkg.getFormattedPrice(
                    this.model.rawTotalPrice - this.modelOrig.rawTotalPrice),
            };
        },

        cancel: function(){
            App.navigate('pods/' + this.model.id, {trigger: true});
        },

        order: function(){
            var that = this;
            App.getPodCollection().done(function(col){
                var modelOrigBackup = that.modelOrig.clone();
                col.add(that.model, {merge: true});
                App.commandPod('redeploy', that.model)
                    .fail(function(){ col.add(modelOrigBackup, {merge: true}); })
                    .done(function(){
                        utils.notifyWindow('Pod will be upgraded.', 'success');
                        App.navigate('pods/' + that.model.id, {trigger: true});
                    });
            });
        },
    });

    return podItem;
});

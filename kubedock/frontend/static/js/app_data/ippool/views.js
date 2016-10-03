define(['app_data/app', 'app_data/controller', 'app_data/utils',
        'app_data/ippool/templates/subnets/empty.tpl',
        'app_data/ippool/templates/subnets/item.tpl',
        'app_data/ippool/templates/subnets/list.tpl',

        'app_data/ippool/templates/subnet_ips/empty.tpl',
        'app_data/ippool/templates/subnet_ips/item.tpl',
        'app_data/ippool/templates/subnet_ips/list.tpl',

        'app_data/ippool/templates/ippool_create_subnetwork.tpl',
        'app_data/ippool/templates/ippool_layout.tpl',
        'bootstrap-select', 'jquery-mask-plugin'],
       function(App, Controller, utils,

                subnetsListItemTplEmptyTpl,
                subnetsListItemTpl,
                subnetsListTpl,

                subnetIpsEmptyTpl,
                subnetIpsListItemTpl,
                subnetIpsListTpl,

                ippoolCreateSubnetworkTpl,
                ippoolLayoutTpl){
    var views = {};

    views.SubnetsListItemEmptyView = Marionette.ItemView.extend({
        template: subnetsListItemTplEmptyTpl,
        tagName: 'tr',
    });

    views.SubnetsListItemView = Marionette.ItemView.extend({
        template: subnetsListItemTpl,
        tagName: 'tr',

        ui: {
            deleteNetwork : '#deleteNetwork',
            tooltip       : '[data-toggle="tooltip"]'
        },

        events: {
            'click @ui.deleteNetwork' : 'deleteNetwork',
        },

        initialize: function(){
            this.isFloating = this.model.collection.ipPoolMode === 'floating';
            this.isAWS = this.model.collection.ipPoolMode === 'aws';
        },

        templateHelpers: function(){
            var forbidDeletionMsg,
                allocation = this.model.get('allocation'),
                busyIPs = _.where(allocation, {2: 'busy'});

            if (!busyIPs.length){
                forbidDeletionMsg = null;
            } else {
                var pods = _.pluck(busyIPs, 1);
                forbidDeletionMsg = 'Сannot be deleted, because ' +
                    (pods.length === 1
                        ? 'pod "' + pods[0] + '" uses this subnet'
                        : 'pods: "' + pods.join('", "') + '" use this subnet');
            }

            return {
                forbidDeletionMsg: forbidDeletionMsg,
                isFloating: this.isFloating
            };
        },

        onDomRefresh: function(){ this.ui.tooltip.tooltip(); },
        deleteNetwork: function(evt){
            var that = this,
                target = $(evt.target);

            if (!target.hasClass('disabled')){
                var network = this.model.get('network');
                utils.modalDialogDelete({
                    title: 'Delete subnet',
                    body: "Are you sure you want to delete subnet '" +
                        network + "'?",
                    small: true,
                    show: true,
                    footer: {
                        buttonOk: function(){
                            utils.preloader.show();
                            that.model.destroy({wait: true})
                                .always(utils.preloader.hide)
                                .fail(utils.notifyWindow)
                                .success(function(){
                                    utils.notifyWindow('Subnet "' + network +
                                                       '" deleted', 'success');
                                });

                        },
                        buttonCancel: true
                    }
                });
            }
        },
    });

    views.SubnetIpsListItemView = Marionette.ItemView.extend({
        template: subnetIpsListItemTpl,
        tagName  : 'tr',

        initialize: function(options){
            this.isAWS = options.isAWS;
        },

        ui: {
            block_ip    : '.block_ip',
            unblock_ip  : '.unblock_ip',
            tooltip     : '[data-toggle="tooltip"]'
        },

        events: {
            'click @ui.block_ip'      : 'blockIP',
            'click @ui.unblock_ip'    : 'unblockIP'
        },

        onDomRefresh: function(){ this.ui.tooltip.tooltip(); },

        commandIP: function(cmd, ip){
            var data = {},
                subnet = this._parent.model;
            data[cmd + '_ip'] = ip;
            return subnet.save(data, {wait: true, context: this})
                .always(function(){ subnet.set(cmd + '_ip', null); })
                .success(function(response){
                    this.model.collection.blocks = response.data.blocks;
                    this.model.collection.fetch(
                        {to: this.model.collection.state.currentPage});
                })
                .fail(utils.notifyWindow);
        },

        blockIP: function(){
            this.commandIP('block', this.model.get('ip'));
            App.resourceRemoveCache('ippoolCollection');
        },
        unblockIP: function(){
            this.commandIP('unblock', this.model.get('ip'));
            App.resourceRemoveCache('ippoolCollection');
        },
        templateHelpers: function(){
            return { isAWS: this.isAWS };
        }
    });

    views.IppoolCreateSubnetworkView = Marionette.ItemView.extend({
        template: ippoolCreateSubnetworkTpl,
        tagName: 'div',

        ui: {
            'network'    : 'input#network',
            'autoblock'  : '[name="autoblock"]',
            'add_button' : '#network-add-btn',
            'input'      : 'input',
            'hostname'   : '.hostname'
        },

        events: {
            'click @ui.add_button' : 'onSave',
            'focus @ui.input'      : 'removeError'
        },

        initialize: function(options){
            this.ipPoolMode = options.ipPoolMode === 'floating';
            this.nodelist = options.nodelist;
        },

        templateHelpers: function(){
            return {
                isFloating : this.ipPoolMode,
                nodelist : this.nodelist
            };
        },

        onRender: function(){
            this.ui.hostname.selectpicker({
                noneSelectedText: 'Hostname list is empty'
            });
            var options = {
                onChange: function(cep, event, currentField, options){
                    if (cep){
                        var ipArray = cep.split(".");
                        for (var i in ipArray){
                            if (ipArray[i].indexOf('/') > 0){
                                if (parseInt(ipArray[i].split('/')[1], 10) > 32){
                                    ipArray[i] = ipArray[i].split('/')[0] + '/' + 32;
                                }
                            } else if (ipArray[i] !== "" && parseInt(ipArray[i], 10) > 255){
                                ipArray[i] = '255';
                            }
                        }
                        var resultingValue = ipArray.join(".");
                        $(currentField).val(resultingValue);
                    }
                },
                translation: {
                    'Z': {
                        pattern: /[0-9]/, optional: true
                    }
                }
            };
            this.ui.network.mask("0ZZ.0ZZ.0ZZ.0ZZ/0Z", options);
        },

        onSave: function(evt){
            var data,
                ok = true,
                that = this,
                pattern = /^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}(?:-\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})?(?:\s*,\s*(?:\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}(?:-\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})?))*$/;

            if (!this.ipPoolMode && !this.nodelist.length){
                utils.notifyWindow('Set node hostname to assign IP pool');
                return;
            }
            App.getIPPoolCollection().done(function(ipCollection){
                // temp validation
                var network = that.ui.network.val();
                if (network.length === 0 || network.split('.').length < 4){
                    utils.notifyWindow('Wrong IP-address');
                    that.ui.network.addClass('error');
                    ok = false;
                } else if (network.indexOf('/') < 0 || network.slice(-1) === '/'){
                    utils.notifyWindow('Wrong mask');
                    that.ui.network.addClass('error');
                    ok = false;
                } else if (parseInt(network.split('/')[1], 10) > 32){
                    utils.notifyWindow('Wrong network');
                    that.ui.network.addClass('error');
                    ok = false;
                } else if ( that.ui.autoblock.val() !== ''
                            && !pattern.test(that.ui.autoblock.val()) ){
                    utils.notifyWindow('Exclude IP\'s are expected to be in '
                        + 'the form of 10.0.0.1,10.0.0.2 or' +
                        ' 10.0.1.1-10.0.2.30 or both comma-separated');
                    that.ui.autoblock.addClass('error');
                    ok = false;
                }
                if (this.ipPoolMode){
                    data = {
                        'network': network,
                        'autoblock': that.ui.autoblock.val()
                    };
                } else {
                    data = {
                        'network': network,
                        'autoblock': that.ui.autoblock.val(),
                        'node' : that.ui.hostname.val()
                    };
                }
                if (ok) {
                    utils.preloader.show();
                    ipCollection.create(data, {
                        wait: true,
                        complete: utils.preloader.hide,
                        success: function(){
                            App.navigate('ippool', {trigger: true});
                            utils.notifyWindow('Subnet "' + network
                                                + '" added', 'success');
                        },
                        error: function(collection, response){
                            utils.notifyWindow(response);
                        },
                    });
                }
            });
            return ok;
        },

        removeError: function(e){
            var target = $(e.target);
            if (target.hasClass('error')) target.removeClass('error');
        }
    });

    views.SubnetsListView = Marionette.CompositeView.extend({
        template           : subnetsListTpl,
        childView          : views.SubnetsListItemView,
        emptyView          : views.SubnetsListItemEmptyView,
        childViewContainer : "tbody",

        initialize: function(){
            this.isFloating = this.collection.ipPoolMode === 'floating';
        },

        collectionEvents: { "remove": "render" },

        templateHelpers: function(){
            var totalFreeIps;
            totalFreeIps = this.collection.fullCollection.reduce(
                function(sum, model){ return sum + model.get('free_host_count'); }, 0);

            return {
                isFloating   : this.isFloating,
                totalFreeIps : totalFreeIps
            };
        }
    });

    views.SubnetIpsListView = Marionette.CompositeView.extend({
        template: subnetIpsListTpl,
        childView: views.SubnetIpsListItemView,
        childViewContainer: 'tbody',
        emptyView: Marionette.ItemView.extend(
            {tagName: 'tr', template: subnetIpsEmptyTpl}),

        initialize: function(){
            this.isAWS = this.options.ipPoolMode === 'aws';
            if (!this.collection.length){
                // if there is no free IPs, show all by default
                this.collection.showExcluded = !this.collection.showExcluded;
                this.collection.refilter();
            }
        },
        ui:{
            visibility: '.visibility',
        },
        events: {
            'click @ui.visibility' : 'toggleVisibility'
        },
        childViewOptions: function(){ return {isAWS: this.isAWS}; },
        templateHelpers: function(){
            return {
                isAWS: this.isAWS,
                showExcluded: this.collection.showExcluded,
            };
        },
        toggleVisibility: function(){
            this.collection.showExcluded = !this.collection.showExcluded;
            this.collection.refilter();
            this.render();
        },
    });

    views.IppoolLayoutView = Marionette.LayoutView.extend({
        template: ippoolLayoutTpl,
        regions: {
            nav        : '#nav',
            breadcrumb : '#breadcrumb',
            main       : '#main',
            pager      : '#pager'
        },
        onBeforeShow: function(){ utils.preloader.show(); },
        onShow: function(){ utils.preloader.hide(); }
    });

    return views;
});

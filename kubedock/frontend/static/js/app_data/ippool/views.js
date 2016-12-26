import App from 'app_data/app';
import * as utils from 'app_data/utils';

/* Subnets */
import subnetsListItemTplEmptyTpl from 'app_data/ippool/templates/subnets/empty.tpl';
import subnetsListItemTpl from 'app_data/ippool/templates/subnets/item.tpl';
import subnetsListTpl from 'app_data/ippool/templates/subnets/list.tpl';

/* Subnet ips */
import subnetIpsEmptyTpl from 'app_data/ippool/templates/subnet_ips/empty.tpl';
import subnetIpsListItemTpl from 'app_data/ippool/templates/subnet_ips/item.tpl';
import subnetIpsListTpl from 'app_data/ippool/templates/subnet_ips/list.tpl';

/* Add subnet */
import ippoolCreateSubnetworkTpl from 'app_data/ippool/templates/ippool_create_subnetwork.tpl';

import ippoolLayoutTpl from 'app_data/ippool/templates/ippool_layout.tpl';

import 'bootstrap-select';

export const SubnetsListItemEmptyView = Marionette.ItemView.extend({
    template: subnetsListItemTplEmptyTpl,
    tagName: 'tr',
});

export const SubnetsListItemView = Marionette.ItemView.extend({
    template: subnetsListItemTpl,
    tagName: 'tr',

    ui: {
        deleteNetwork : '#deleteNetwork',
        tooltip       : '[data-toggle="tooltip"]'
    },

    events: {
        'click @ui.deleteNetwork' : 'deleteNetwork',
    },

    templateHelpers: function(){
        let forbidDeletionMsg,
            allocation = this.model.get('allocation'),
            busyIPs = _.where(allocation, {2: 'busy'});

        if (!busyIPs.length){
            forbidDeletionMsg = null;
        } else {
            let pods = _.pluck(busyIPs, 1);
            forbidDeletionMsg = 'Сannot be deleted, because ' +
                (pods.length === 1
                    ? 'pod "' + pods[0] + '" uses this subnet'
                    : 'pods: "' + pods.join('", "') + '" use this subnet');
        }

        return {
            forbidDeletionMsg: forbidDeletionMsg,
            isFloating: !App.setupInfo.FIXED_IP_POOLS
        };
    },

    onDomRefresh: function(){ this.ui.tooltip.tooltip(); },

    deleteNetwork: function(evt){
        let that = this,
            target = $(evt.target);

        if (!target.hasClass('disabled')){
            let network = this.model.get('network');
            utils.modalDialogDelete({
                title: 'Delete subnet',
                body: `Are you sure you want to delete subnet "${network}"?`,
                small: true,
                show: true,
                footer: {
                    buttonOk: function(){
                        utils.preloader.show();
                        that.model.destroy({wait: true})
                            .always(utils.preloader.hide)
                            .fail(utils.notifyWindow)
                            .success(() => {
                                utils.notifyWindow(`Subnet "${network}" deleted`,
                                                   'success');
                            });

                    },
                    buttonCancel: true
                }
            });
        }
    },
});

export const SubnetIpsListItemView = Marionette.ItemView.extend({
    template : subnetIpsListItemTpl,
    tagName : 'tr',

    ui: {
        block_ip   : '.block_ip',
        unblock_ip : '.unblock_ip',
        tooltip    : '[data-toggle="tooltip"]'
    },

    events: {
        'click @ui.block_ip'   : 'blockIP',
        'click @ui.unblock_ip' : 'unblockIP'
    },

    onDomRefresh: function(){ this.ui.tooltip.tooltip(); },

    commandIP: function(cmd, ip){
        let data = {},
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
        return {isAWS: App.setupInfo.AWS};
    }
});

export const IppoolCreateSubnetworkView = Marionette.ItemView.extend({
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
        'focus @ui.input'      : 'removeError',
        'keypress @ui.input'   : 'addSubnetByEnterKey'
    },

    initialize: function(options){
        this.nodelist = options.nodelist;
    },

    addSubnetByEnterKey: function(evt){
        if (evt.which === utils.KEY_CODES.enter){
            evt.stopPropagation();
            this.onSave();
        }
    },

    templateHelpers: function(){
        return {
            isFloating : !App.setupInfo.FIXED_IP_POOLS,
            nodelist : this.nodelist
        };
    },

    onRender: function(){
        this.ui.hostname.selectpicker({
            noneSelectedText: 'Hostname list is empty'
        });
    },

    validate: function(data){
        let that = this,
            network = data.network,
            patternIP = /^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$/, // eslint-disable-line max-len
            patternAutoblock = /^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}(?:-\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})?(?:\s*,\s*(?:\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}(?:-\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})?))*$/; // eslint-disable-line max-len

        if (!this.ipPoolMode && !this.nodelist){
            utils.notifyWindow('Set node hostname to assign IP pool');
            return false;
        }
        let [spliter, mask] = network.split('/');

        if (!network){
            utils.notifyInline('Empty subnet', that.ui.network);
            return false;
        } else if (!patternIP.test(spliter)) {
            utils.notifyInline('Wrong IP-address', that.ui.network);
            return false;
        } else if (network.indexOf('/') === -1 || mask === '') {
            utils.notifyInline('Subnet mask must be set', that.ui.network);
            return false;
        } else if (parseInt(mask, 10) > 32 || parseInt(mask, 10) < 1){
            utils.notifyInline('Wrong subnet mask', that.ui.network);
            return false;
        } else if ( data.autoblock && !patternAutoblock.test(data.autoblock)) {
            utils.notifyInline('Exclude IP\'s are expected to be in ' +
                               'the form of 10.0.0.1,10.0.0.2 or' +
                               ' 10.0.1.1-10.0.2.30 or both comma-separated',
                               that.ui.autoblock);
            return false;
        } else {
            return true;
        }
    },

    correctSubnet: function(network){
        let [ip, mask] = network.split('/'),
            patternIpMask = /^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\/[1-3]?[0-9]$/; // eslint-disable-line max-len

        if (!patternIpMask.test(network)) return network;
        ip = ip.split('.').map(i => parseInt(i, 10)).join('.');
        return ip + '/' + mask;
    },

    removeError: function(evt){ utils.removeError($(evt.target)); },

    onSave: function(evt){
        let data,
            that = this,
            network = this.correctSubnet(that.ui.network.val());

        that.ui.network.val(network);

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

        App.getIPPoolCollection().done(function(ipCollection){
            if (_.without(ipCollection.where({network}), that.model).length) {
                utils.notifyInline('Subnet already exists.', that.ui.network);
                return false;
            }
            if (that.validate(data)) {
                utils.preloader.show();
                ipCollection.create(data, {
                    wait: true,
                    complete: utils.preloader.hide,
                    success: function(){
                        App.navigate('ippool', {trigger: true});
                        utils.notifyWindow('Subnet "' + network +
                                           '" added', 'success');
                    },
                    error: function(collection, response){
                        utils.notifyWindow(response);
                    },
                });
            }
        });
    }
});

export const SubnetsListView = Marionette.CompositeView.extend({
    template : subnetsListTpl,
    childView : SubnetsListItemView,
    emptyView : SubnetsListItemEmptyView,
    childViewContainer : "tbody",

    collectionEvents: { "remove": "render" },

    templateHelpers: function(){
        let totalFreeIps;
        totalFreeIps = this.collection.fullCollection.reduce(
            function(sum, model){ return sum + model.get('free_host_count'); }, 0);

        return {
            isFloating: !App.setupInfo.FIXED_IP_POOLS,
            totalFreeIps : totalFreeIps
        };
    }
});

export const SubnetIpsListView = Marionette.CompositeView.extend({
    template: subnetIpsListTpl,
    childView: SubnetIpsListItemView,
    childViewContainer: 'tbody',
    emptyView: Marionette.ItemView.extend(
        {tagName: 'tr', template: subnetIpsEmptyTpl}),

    initialize: function(){
        if (!this.collection.length){
            // if there is no free IPs, show all by default
            this.collection.showExcluded = !this.collection.showExcluded;
            this.collection.refilter();
        }
    },
    ui:{
        visibility : '.visibility',
    },
    events: {
        'click @ui.visibility' : 'toggleVisibility'
    },
    templateHelpers: function(){
        return {
            isAWS: App.setupInfo.AWS,
            showExcluded: this.collection.showExcluded,
        };
    },
    toggleVisibility: function(){
        this.collection.showExcluded = !this.collection.showExcluded;
        this.collection.refilter();
        this.render();
    },
});

export const IppoolLayoutView = Marionette.LayoutView.extend({
    template: ippoolLayoutTpl,
    regions: {
        breadcrumb : '#breadcrumb',
        main : '#main',
        pager : '#pager'
    },
    onBeforeShow: function(){ utils.preloader.show(); },
    onShow: function(){ utils.preloader.hide(); }
});

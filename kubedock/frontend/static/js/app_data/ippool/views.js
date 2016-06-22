define(['app_data/app', 'app_data/controller', 'marionette', 'app_data/utils',

        'tpl!app_data/ippool/templates/subnets/empty.tpl',
        'tpl!app_data/ippool/templates/subnets/list_item.tpl',
        'tpl!app_data/ippool/templates/subnets/list.tpl',

        'tpl!app_data/ippool/templates/subnet_ips/list_item.tpl',
        'tpl!app_data/ippool/templates/subnet_ips/list.tpl',

        'tpl!app_data/ippool/templates/ippool_create_subnetwork.tpl',
        'tpl!app_data/ippool/templates/ippool_layout.tpl',
        'bootstrap', 'jquery-ui', 'selectpicker', 'bootstrap3-typeahead', 'mask'],
       function(App, Controller, Marionette, utils,

                subnetsListItemTplEmptyTpl,
                subnetsListItemTpl,
                subnetsListTpl,

                subnetIpsListItemTpl,
                subnetIpsListTpl,

                ippoolCreateSubnetworkTpl,
                ippoolLayoutTpl){
    var views = {};

    views.SubnetsListItemEmptyView = Backbone.Marionette.ItemView.extend({
        template: subnetsListItemTplEmptyTpl,
        tagName: 'tr',
    });

    views.SubnetsListItemView = Backbone.Marionette.ItemView.extend({
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
        },

        templateHelpers: function(){
            var forbidDeletionMsg,
                allocation = this.model.get('allocation'),
                hasBusyIp = _.any(allocation.map(function(i){return i[2];}), function(i){return i === 'busy' ;});

            if (!hasBusyIp){
                forbidDeletionMsg = null;
            } else {
                forbidDeletionMsg = 'Сannot be deleted, because '
                    + (allocation.length === 1
                            ? 'pod "' + _.pluck(allocation, '1') + '" use this subnet'
                            : 'pods: "' + _.pluck(allocation, '1').join('", "') + '" use this subnet');
            }

            return {
                forbidDeletionMsg : forbidDeletionMsg,
                isFloating : this.isFloating
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
                                .success(utils.notifyWindow('Subnet "' + network
                                                      + '" deleted', 'success'))
                                .always(utils.preloader.hide)
                                .fail(utils.notifyWindow);
                        },
                        buttonCancel: true
                    }
                });
            }
        },
    });

    views.SubnetIpsListItemView = Backbone.Marionette.ItemView.extend({
        template: subnetIpsListItemTpl,
        tagName  : 'tr',

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
                .fail(utils.notifyWindow);
        },

        blockIP: function(){ this.commandIP('block', this.model.get('ip')); },
        unblockIP: function(){ this.commandIP('unblock', this.model.get('ip')); }
    });

    views.IppoolCreateSubnetworkView = Backbone.Marionette.ItemView.extend({
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
                    if(cep){
                        var ipArray = cep.split(".");
                        for (i in ipArray){
                            if(ipArray[i].indexOf('/') > 0){
                                if(parseInt(ipArray[i].split('/')[1]) > 32){
                                    ipArray[i] = ipArray[i].split('/')[0] + '/' + 32;
                                }
                            } else if(ipArray[i] !== "" && parseInt(ipArray[i]) > 255){
                                ipArray[i] =  '255';
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
                pattern = /^\d+(?:-\d+)?(?:\s*,\s*(?:\d+(?:-\d+)?))*$/;

            if (this.ipPoolMode && this.nodelist.length === 0) return;
            App.getIPPoolCollection().done(function(ipCollection){
                // temp validation
                var network = that.ui.network.val();
                if(network.length === 0 || network.split('.').length < 4){
                    utils.notifyWindow('Wrong IP-address');
                    that.ui.network.addClass('error');
                    ok = false;
                } else if(network.indexOf('/') < 0){
                    utils.notifyWindow('Wrong mask');
                    that.ui.network.addClass('error');
                    ok = false;
                } else if(parseInt(network.split('/')[1]) > 32){
                    utils.notifyWindow('Wrong network');
                    that.ui.network.addClass('erorr');
                    ok = false;
                } else if ( that.ui.autoblock.val() !== '' && !pattern.test(that.ui.autoblock.val()) ){
                    utils.notifyWindow('Exclude IP\'s are expected to be in the form of 5,6,7 or 6-134 or both comma-separated');
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

    views.SubnetsListView = Backbone.Marionette.CompositeView.extend({
        template           : subnetsListTpl,
        childView          : views.SubnetsListItemView,
        emptyView          : views.SubnetsListItemEmptyView,
        childViewContainer : "tbody",

        initialize: function(){
            this.isFloating = this.collection.ipPoolMode === 'floating';
        },

        templateHelpers: function(){
            return {
                isFloating : this.isFloating
            };
        }
    });

    views.SubnetIpsListView = Backbone.Marionette.CompositeView.extend({
        template: subnetIpsListTpl,
        childView: views.SubnetIpsListItemView,
        childViewContainer: "tbody",
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

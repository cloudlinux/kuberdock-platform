define(['app_data/app', 'app_data/controller', 'marionette', 'app_data/utils',
        'tpl!app_data/ippool/templates/network_empty.tpl',
        'tpl!app_data/ippool/templates/network_item.tpl',
        'tpl!app_data/ippool/templates/network_item_more.tpl',
        'tpl!app_data/ippool/templates/breadcrumbs.tpl',
        'tpl!app_data/ippool/templates/ippool_left.tpl',
        'tpl!app_data/ippool/templates/ippool_right.tpl',
        'tpl!app_data/ippool/templates/ippool_aside.tpl',
        'tpl!app_data/ippool/templates/network_create.tpl',
        'tpl!app_data/ippool/templates/networks_layout.tpl',
        'bootstrap', 'jquery-ui', 'selectpicker', 'bootstrap3-typeahead', 'mask'],
       function(App, Controller, Marionette, utils,
                networkEmptyTpl,
                networkItemTpl,
                networkItemMoreTpl,
                breadcrumbsTpl,
                ippoolLeftTpl,
                ippoolRightTpl,
                ippoolAsideTpl,
                networkCreateTpl,
                networksLayoutTpl){

    var views = {};

    views.NetworkEmpty = Backbone.Marionette.ItemView.extend({
        template: networkEmptyTpl,
        tagName: 'tr',
    });

    views.NetworkItem = Backbone.Marionette.ItemView.extend({
        template: networkItemTpl,
        tagName: 'tr',
        className: function(){
            return this.model.checked ? 'checked' : ''
        },

        ui: {
            deleteNetwork : '#deleteNetwork',
            tooltip       : '[data-toggle="tooltip"]'
        },

        events: {
            'click @ui.deleteNetwork' : 'deleteNetwork_btn',
        },

        initialize: function(){
            $(this.el).attr('data-id', this.model.get('network'));
        },

        templateHelpers: function(){
            var forbidDeletionMsg,
                allocation = this.model.get('allocation'),
                hasBusyIp = _.any(allocation.map(function(i){return i[2];}), function(i){return i === 'busy' ;});

            if (!hasBusyIp){
                forbidDeletionMsg = null;
            } else {
                forbidDeletionMsg = 'Сannot be deleted, because '
                    + (allocation.length == 1
                            ? 'pod "' + _.pluck(allocation, '1') + '" use this subnet'
                            : 'pods: "' + _.pluck(allocation, '1').join('", "') + '" use this subnet');
            }

            return {
                forbidDeletionMsg: forbidDeletionMsg
            };
        },

        onDomRefresh: function(){ this.ui.tooltip.tooltip(); },

        deleteNetwork_btn: function(evt){
            evt.stopPropagation();
            var that = this,
                target = $(evt.target);

            if (!target.hasClass('disabled')){
                utils.modalDialogDelete({
                    title: 'Delete subnet',
                    body: "Are you sure you want to delete subnet '" +
                        this.model.get('network') + "'?",
                    small: true,
                    show: true,
                    footer: {
                        buttonOk: function(){
                            utils.preloader.show();
                            that.model.destroy({wait: true})
                                .always(utils.preloader.hide)
                                .fail(utils.notifyWindow);
                        },
                        buttonCancel: true
                    }
                });
            }
        },
    });

    views.NetworkItemMore = Backbone.Marionette.ItemView.extend({
        template: networkItemMoreTpl,

        ui: {
            block_ip      : '.block_ip',
            unblock_ip    : '.unblock_ip',
            /*unbind_ip     : '.unbind_ip'*/
        },

        events: {
            'click @ui.block_ip'      : 'blockIP',
            'click @ui.unblock_ip'    : 'unblockIP',
            /*'click @ui.unbind_ip'     : 'unbindIP'*/
        },

        templateHelpers: function(){
            var allocation = this.model.get('allocation');

            if (allocation){
                allocation.sort(function(a, b){
                    var aa = a[0].split("."),
                        bb = b[0].split(".");

                    for (var i=0, n=Math.max(aa.length, bb.length); i<n; i++) {
                        if (aa[i] !== bb[i]) return aa[i] - bb[i];
                    }
                    return 0;
                });
            }

            return{
                allocation : allocation
            }
        },

        commandIP: function(cmd, ip){
            var data = {};
            data[cmd + '_ip'] = ip;
            return this.model.save(data, {wait: true, context: this})
                .always(function(){ this.model.set(cmd + '_ip', null); })
                .done(this.render)
                .fail(utils.notifyWindow);
        },

        blockIP: function(btn){
            var ip = $(btn.currentTarget).data('ip');
            this.commandIP('block', ip);
        },

        unblockIP: function(btn){
            var ip = $(btn.currentTarget).data('ip');
            this.commandIP('unblock', ip);
        },

/*        unbindIP: function(btn){
            var ip = $(btn.currentTarget).data('ip'),
                that = this;

            utils.modalDialog({
                title: 'Unbind IP-address',
                body: "Are you sure you want to unbind IP '" + ip + "' address?",
                small: true,
                show: true,
                footer: {
                    buttonOk: _.bind(this.commandIP, this, 'unbind', ip),
                    buttonCancel: true
                }
            });
        }*/
    });

    views.BreadcrumbView = Backbone.Marionette.ItemView.extend({
        template: breadcrumbsTpl,

        events: {
            'click button#create_network' : 'createNetwork'
        },

        createNetwork: function(){
            App.navigate('ippool/create', {trigger: true});
        }
    });

    views.LeftView = Backbone.Marionette.CompositeView.extend({
        template           : ippoolLeftTpl,
        childView          : views.NetworkItem,
        emptyView          : views.NetworkEmpty,
        childViewContainer : "tbody.networks-list"
    });

    views.RightView = Backbone.Marionette.CompositeView.extend({
        template: ippoolRightTpl,
        childView: views.NetworkItemMore,
        childViewContainer: "div.right"
    });

    views.AsideView = Backbone.Marionette.ItemView.extend({
        template: ippoolAsideTpl,
    });

    views.NetworkCreateView = Backbone.Marionette.ItemView.extend({
        template: networkCreateTpl,
        tagName: 'div',

        ui: {
            'network'    : 'input#network',
            'autoblock'  : '[name="autoblock"]',
            'add_button' : '#network-add-btn',
            'back'       : '.back',
            'input'      : 'input'
        },

        events: {
            'click @ui.add_button' : 'onSave',
            'click @ui.back'       : 'back',
            'focus @ui.input'      : 'removeError'
        },

        onRender: function(){
            var options = {
                onChange: function(cep, event, currentField, options){
                    if(cep){
                        var ipArray = cep.split(".");
                        for (i in ipArray){
                            if(ipArray[i].indexOf('/') > 0){
                                if(parseInt(ipArray[i].split('/')[1]) > 32){
                                    ipArray[i] = ipArray[i].split('/')[0] + '/' + 32;
                                }
                            } else if(ipArray[i] != "" && parseInt(ipArray[i]) > 255){
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

        onSave: function(){
            var that = this,
                ok = true,
                pattern = /^\d+(?:-\d+)?(?:\s*,\s*(?:\d+(?:-\d+)?))*$/;

            App.getIPPoolCollection().done(function(ipCollection){
                // temp validation
                var network = that.ui.network.val();
                if(network.length == 0 || network.split('.').length < 4){
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
                if (ok) {
                    utils.preloader.show();
                    ipCollection.create({
                        'network': network,
                        'autoblock': that.ui.autoblock.val()
                    }, {
                        wait: true,
                        complete: utils.preloader.hide,
                        success: function(){
                            App.navigate('ippool', {trigger: true});
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
            if (target.hasClass('error')){
                target.removeClass('error');
            }
        },

        back: function(){
            App.navigate('ippool', {trigger: true});
        }
    });

    views.NetworksLayout = Marionette.LayoutView.extend({
        template: networksLayoutTpl,

        regions: {
            nav   : 'div#nav',
            main  : 'div#main',
            aside : 'div#aside',
            left  : 'div#left',
            right : 'div#right'
        },

        ui: {
            'tr' : '.ip_pool_table tbody tr',
        },

        events: {
            'click @ui.tr' : 'onCheckItem'
        },

        onBeforeShow: function(){
            utils.preloader.show();
        },

        onShow: function(){
            utils.preloader.hide();
        },

        onCheckItem: function (e) {
            e.stopPropagation();
            var target = $(e.currentTarget),
                id = target.attr('data-id');
            this.trigger('ippool:network:picked', id);
        }
    });

    return views;
});

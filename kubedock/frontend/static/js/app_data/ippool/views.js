define(['app_data/app', 'app_data/controller', 'marionette', 'utils',
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
        },

        events: {
            'click @ui.deleteNetwork' : 'deleteNetwork_btn',
        },

        initialize: function(){
            $(this.el).attr('data-id', this.model.get('network'));
        },

        deleteNetwork_btn: function(evt){
            evt.stopPropagation()
            var that = this,
                preloader = $('#page-preloader');
            utils.modalDialogDelete({
                    title: 'Delete network',
                    body: "Are you sure want to delete network '" +
                        this.model.get('network') + "'?",
                small: true,
                show: true,
                footer: {
                    buttonOk: function(){
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
    });

    views.NetworkItemMore = Backbone.Marionette.ItemView.extend({
        template: networkItemMoreTpl,

        ui: {
            block_ip      : '.block_ip',
            unblock_ip    : '.unblock_ip',
            unbind_ip     : '.unbind_ip'
        },

        events: {
            'click @ui.block_ip'      : 'blockIP',
            'click @ui.unblock_ip'    : 'unblockIP',
            'click @ui.unbind_ip'     : 'unbindIP'
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
            return this.model.save(data, {
                wait: true,
                context: this,
                success: this.render,
                error: function(data, response){ console.error(response); },
                complete: function(){ this.model.set(cmd + '_ip', null); },
            });
        },

        blockIP: function(btn){
            var ip = $(btn.currentTarget).data('ip');
            this.commandIP('block', ip);
        },

        unblockIP: function(btn){
            var ip = $(btn.currentTarget).data('ip');
            this.commandIP('unblock', ip);
        },

        unbindIP: function(btn){
            var ip = $(btn.currentTarget).data('ip'),
                that = this;

            utils.modalDialog({
                title: 'Unbind IP-address',
                body: "Are you sure want to unbind IP '" + ip + "' address?",
                small: true,
                show: true,
                footer: {
                    buttonOk: _.bind(this.commandIP, this, 'unbind', ip),
                    buttonCancel: true
                }
            });
        }
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
        childViewContainer : "tbody.networks-list",

        initialize: function(){
            if (this.collection.length != 0) {
                this.collection.models[0].checked = true;
            }
        }
    });

    views.RightView = Backbone.Marionette.CompositeView.extend({
        template: ippoolRightTpl,
        childView: views.NetworkItemMore,
        childViewContainer: "div.right"

        //onBeforeRender: function(){
        //    App.Data.networks.fetch()
        //},

        //initialize: function(){
        //    App.Data.networksClone = new Backbone.Collection(
        //        App.Data.networks.filter(function(item){ return item.checked; })
        //    );
        //    this.collection = App.Data.networksClone;
        //}
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
        },

        events: {
            'click @ui.add_button' : 'onSave',
            'click @ui.back'       : 'back'
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
                ok = true;
            App.getIPPoolCollection().done(function(ipCollection){
                // temp validation
                var preloader = $('#page-preloader');
                    network = that.ui.network.val();
                if(network.length == 0 || network.split('.').length < 4){
                    that.ui.network.notify('Wrong IP-address');
                    ok = false;
                } else if(network.indexOf('/') < 0){
                    that.ui.network.notify('Wrong mask');
                    ok = false;
                } else if(parseInt(network.split('/')[1]) > 32){
                    that.ui.network.notify('Wrong network');
                    ok = false;
                }
                if (ok) {
                    preloader.show();
                    ipCollection.create({
                        'network': network,
                        'autoblock': that.ui.autoblock.val()
                    }, {
                        wait: true,
                        success: function(){
                            preloader.hide();
                            App.navigate('ippool', {trigger: true})
                        },
                        error:  function(){
                            preloader.hide();
                        }
                    });
                }
            });
            return ok;
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

        onCheckItem: function (e) {
            e.stopPropagation();
            var target = $(e.currentTarget),
                id = target.attr('data-id');
            this.trigger('ippool:network:picked', id);
            //    models = App.Data.networks.models,
            //    collection = App.Data.networksClone;
            //
            //this.$('.networks-list tr').removeClass('checked');
            //target.addClass('checked');
            //
            //collection.reset();
            //
            //_.each(models, function(model,index){
            //    if (model.get('network') == id) {
            //        collection.add(model);
            //        model.checked = true;
            //    }
            //    else {
            //        model.checked = false;
            //    }
            //});
        },
    });

    return views;
});

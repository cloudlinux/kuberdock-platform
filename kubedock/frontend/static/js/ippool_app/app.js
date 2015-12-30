define(['marionette', 'utils'], function (Marionette, utils) {

    var IPPoolApp = new Marionette.Application({
        regions: {
            contents: '#contents'
        }
    });

    IPPoolApp.module('Data', function(Data, App, Backbone, Marionette, $, _){

        Data.NetworkModel = utils.BaseModel.extend({
            urlRoot: '/api/ippool/'
        });
        Data.NetworksCollection = utils.BaseCollection.extend({
            url: '/api/ippool/',
            model: Data.NetworkModel
        });

    });

    IPPoolApp.module('Views', function(Views, App, Backbone, Marionette, $, _){

        Views.NetworkEmpty = Backbone.Marionette.ItemView.extend({
            template: '#network-empty-template',
            tagName: 'tr',
        });

        Views.NetworkItem = Backbone.Marionette.ItemView.extend({
            template: '#network-item-template',
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
                    body: "Are you sure you want to delete network '" +
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

        Views.NetworkItemMore = Backbone.Marionette.ItemView.extend({
            template: '#network-item-more-template',

            ui: {
                block_ip   : '.block_ip',
                unblock_ip : '.unblock_ip',
                unbind_ip  : '.unbind_ip'
            },

            events: {
                'click @ui.block_ip'   : 'blockIP',
                'click @ui.unblock_ip' : 'unblockIP',
                'click @ui.unbind_ip'  : 'unbindIP'
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
                    body: "Are you sure you want to unbind IP '" + ip + "' address?",
                    small: true,
                    show: true,
                    footer: {
                        buttonOk: _.bind(this.commandIP, this, 'unbind', ip),
                        buttonCancel: true
                    }
                });
            }
        });

        Views.BreadcrumbView = Backbone.Marionette.ItemView.extend({
            template: '#breadcrumb',

            events: {
                'click button#create_network' : 'createNetwork'
            },

            createNetwork: function(){
                App.router.navigate('/create/', {trigger: true});
            }
        });

        Views.LeftView = Backbone.Marionette.CompositeView.extend({
            template           : '#ippool-left-template',
            childView          : Views.NetworkItem,
            emptyView          : Views.NetworkEmpty,
            childViewContainer : "tbody.networks-list",

            initialize: function(){
                if (this.collection.length != 0) {
                    this.collection.models[0].checked = true;
                }
            }
        });

        Views.RightView = Backbone.Marionette.CompositeView.extend({
            template: '#ippool-right-template',
            childView: Views.NetworkItemMore,
            childViewContainer: "div.right",

            onBeforeRender: function(){
                App.Data.networks.fetch()
            },

            initialize: function(){
                App.Data.networksClone = new Backbone.Collection(
                    App.Data.networks.filter(function(item){ return item.checked; })
                );
                this.collection = App.Data.networksClone;
            }
        });

        Views.AsideView = Backbone.Marionette.ItemView.extend({
            template: '#ippool-aside-template',
        });

        Views.NetworkCreateView = Backbone.Marionette.ItemView.extend({
            template: '#network-create-template',
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
                // temp validation
                var that = this,
                    preloader = $('#page-preloader');
                    network = this.ui.network.val();
                if(network.length == 0 || network.split('.').length < 4){
                    this.ui.network.notify('Wrong IP-address');
                    return false;
                } else if(network.indexOf('/') < 0){
                    this.ui.network.notify('Wrong mask');
                    return false;
                } else if(parseInt(network.split('/')[1]) > 32){
                    this.ui.network.notify('Wrong network');
                    return false;
                }

                preloader.show();
                App.Data.networks.create({
                    'network': network,
                    'autoblock': this.ui.autoblock.val()
                }, {
                    wait: true,
                    success: function(){
                        preloader.hide();
                        App.router.navigate('/', {trigger: true})
                    },
                    error:  function(){
                        preloader.hide();
                    }
                });
            },

            back: function(){
                App.router.navigate('/', {trigger: true});
            }

        });

        Views.NetworksLayout = Marionette.LayoutView.extend({
            template: '#networks-layout-template',

            regions: {
                main: 'div#main',
                aside: 'div#aside',
                left: 'div#left',
                right: 'div#right'
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
                    id = target.attr('data-id'),
                    models = App.Data.networks.models,
                    collection = App.Data.networksClone;

                this.$('.networks-list tr').removeClass('checked');
                target.addClass('checked');

                collection.reset();

                _.each(models, function(model,index){
                    if (model.get('network') == id) {
                        collection.add(model);
                        model.checked = true;
                    }
                    else {
                        model.checked = false;
                    }
                });
            },
        });
    });


    IPPoolApp.module('IPPoolCRUD', function(IPPoolCRUD, App, Backbone, Marionette, $, _){

        IPPoolCRUD.Controller = Marionette.Controller.extend({
            showNetworks: function(){
                var layout_view = new App.Views.NetworksLayout();
                var breadcrumb = new App.Views.BreadcrumbView();
                var aside = new App.Views.AsideView();
                var left = new App.Views.LeftView({
                    collection: App.Data.networks
                });
                var right = new App.Views.RightView({
                    collection : App.Data.networksClone
                });

                this.listenTo(layout_view, 'show', function(){
                    layout_view.main.show(breadcrumb);
                    layout_view.aside.show(aside);
                    layout_view.left.show(left);
                    layout_view.right.show(right);
                });
                App.contents.show(layout_view);
            },

            showCreateNetwork: function(){
                var layout_view = new App.Views.NetworksLayout();
                var network_create_view = new App.Views.NetworkCreateView();

                this.listenTo(layout_view, 'show', function(){
                    layout_view.main.show(network_create_view);
                });

                App.contents.show(layout_view);
            }
        });

        IPPoolCRUD.addInitializer(function(){
            var controller = new IPPoolCRUD.Controller();
            App.Data.networks = new App.Data.NetworksCollection(networksCollection);
            App.router = new Marionette.AppRouter({
                controller: controller,
                appRoutes: {
                    '': 'showNetworks',
                    'create/': 'showCreateNetwork'
                }
            });
        });

    });

    IPPoolApp.on('start', function(){
        if (Backbone.history) {
            Backbone.history.start({root: '/ippool', pushState: true});
        }
    });

    return IPPoolApp;
});

define([
    'app_data/app', 'app_data/controller', 'app_data/utils',

    'app_data/domains/templates/list/empty.tpl',
    'app_data/domains/templates/list/item.tpl',
    'app_data/domains/templates/list/list.tpl',

    'app_data/domains/templates/add_domain.tpl',
    'app_data/domains/templates/domains_layout.tpl',
], function(
    App, Controller, utils,

    domainsListItemEmptyTpl,
    domainsListItemTpl,
    domainsListTpl,

    domainsAddDomainTpl,
    domainsLayoutTpl
){
    var views = {};

    views.DomainsListItemEmptyView = Marionette.ItemView.extend({
        template: domainsListItemEmptyTpl,
        tagName: 'tr',
    });

    views.DomainsListItemView = Marionette.ItemView.extend({
        template: domainsListItemTpl,
        tagName: 'tr',

        ui: {
            deleteDomain: '.delete-domain',
            tooltip     : '[data-toggle="tooltip"]',
        },

        events: {
            'click @ui.deleteDomain': 'deleteDomain',
        },

        onDomRefresh: function(){ this.ui.tooltip.tooltip(); },
        deleteDomain: function(evt){
            var that = this,
                domain = this.model.get('name');

            utils.modalDialogDelete({
                title: 'Remove domain',
                body: "Are you sure you want to remove domain '" +
                    domain + "'?",
                small: true,
                show: true,
                footer: {
                    buttonOk: function(){
                        utils.preloader.show();
                        that.model.destroy({wait: true})
                            .done(function(){
                                utils.notifyWindow(
                                    'Domain "' + domain + '" removed',
                                    'success');
                            })
                            .always(utils.preloader.hide)
                            .fail(utils.notifyWindow);
                    },
                    buttonCancel: true,
                },
            });
        },
    });

    views.DomainsListView = Marionette.CompositeView.extend({
        template: domainsListTpl,
        childView: views.DomainsListItemView,
        emptyView: views.DomainsListItemEmptyView,
        childViewContainer: 'tbody',
    });

    views.DomainsAddDomainView = Marionette.ItemView.extend({
        template: domainsAddDomainTpl,
        tagName: 'div',

        ui: {
            'domain'    : 'input#domain',
            'add_button': '#domain-add-btn',
        },

        events: {
            'click @ui.add_button': 'onSave',
            'focus @ui.domain'    : 'removeError',
            'keypress @ui.domain' : 'onInputKeypress',
        },

        onInputKeypress: function(evt){
            if (evt.which === utils.KEY_CODES.enter){
                evt.stopPropagation();
                this.onSave();
            }
        },

        removeError: function(e){ utils.removeError($(e.target)); },

        onSave: function(){
            var domain = this.ui.domain.val().trim(),
                data = {name: domain},
                validDomain = /^(?:[a-zA-Z0-9][a-zA-Z0-9-]{0,61}[a-zA-Z0-9]\.)+(?:[a-zA-Z]{2,})$/;

            if (!validDomain.test(domain)){
                utils.scrollTo(this.ui.domain);
                utils.notifyInline('Wrong domain name', this.ui.domain);
                return;
            }

            App.getDomainsCollection().done(function(domainCollection){
                utils.preloader.show();
                domainCollection.create(data, {
                    wait: true,
                    complete: utils.preloader.hide,
                    success: function(){
                        App.navigate('domains', {trigger: true});
                        utils.notifyWindow(
                            'Domain "' + domain + '" added', 'success');
                    },
                    error: function(collection, response){
                        utils.notifyWindow(response);
                    },
                });
            });
        },
    });

    views.DomainsLayoutView = Marionette.LayoutView.extend({
        template: domainsLayoutTpl,
        regions: {
            breadcrumb: '#breadcrumb',
            main      : '#main',
            pager     : '#pager',
        },
        onBeforeShow: function(){ utils.preloader.show(); },
        onShow: function(){ utils.preloader.hide(); },
    });

    return views;
});

import App from 'app_data/app';
import * as utils from 'app_data/utils';

import domainsListItemEmptyTpl from 'app_data/domains/templates/list/empty.tpl';
import domainsListItemTpl from 'app_data/domains/templates/list/item.tpl';
import domainsListTpl from 'app_data/domains/templates/list/list.tpl';

import domainsAddDomainTpl from 'app_data/domains/templates/add_domain.tpl';
import domainsLayoutTpl from 'app_data/domains/templates/domains_layout.tpl';

export const DomainsListItemEmptyView = Marionette.ItemView.extend({
    template: domainsListItemEmptyTpl,
    tagName: 'tr',
});

export const DomainsListItemView = Marionette.ItemView.extend({
    template: domainsListItemTpl,
    tagName: 'tr',

    ui: {
        deleteDomain : '.delete-domain',
        tooltip : '[data-toggle="tooltip"]',
    },

    events: {
        'click @ui.deleteDomain': 'deleteDomain',
    },

    onDomRefresh(){ this.ui.tooltip.tooltip(); },
    deleteDomain(evt){
        let that = this,
            domain = this.model.get('name');

        utils.modalDialogDelete({
            title: 'Remove domain',
            body: "Are you sure you want to remove domain '" +
                domain + "'?",
            small: true,
            show: true,
            footer: {
                buttonOk(){
                    utils.preloader.show();
                    that.model.destroy({wait: true})
                        .done(function(){
                            utils.notifyWindow(`Domain "${domain}" removed`,
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

export const DomainsListView = Marionette.CompositeView.extend({
    template: domainsListTpl,
    childView: DomainsListItemView,
    emptyView: DomainsListItemEmptyView,
    childViewContainer: 'tbody',
});

export const DomainsAddDomainView = Marionette.ItemView.extend({
    template: domainsAddDomainTpl,
    tagName: 'div',

    ui: {
        'key'         : 'textarea#key',
        'domain'      : 'input#domain',
        'add_button'  : '#domain-add-btn',
        'certificate' : 'textarea#certificate'
    },

    events: {
        'click @ui.add_button'  : 'onSave',
        'focus @ui.domain'      : 'removeError',
        'focus @ui.key'         : 'removeError',
        'focus @ui.certificate' : 'removeError',
        'keypress @ui.domain'   : 'onInputKeypress',
    },

    onInputKeypress(evt){
        if (evt.which === utils.KEY_CODES.enter){
            evt.stopPropagation();
            this.onSave();
        }
    },

    templateHelpers(){
        return {
            isNew: this.model.isNew(),
        };
    },

    removeError(e){ utils.removeError($(e.target)); },

    onSave(){
        var isNew = this.model.isNew(),
            key = this.ui.key.val().trim(),
            domain = this.ui.domain.val().trim(),
            cert = this.ui.certificate.val().trim(),
            data = {
                name: domain,
                certificate: cert ? {cert, key} : null,
            },
            validDomain = /^(?:[a-zA-Z0-9][a-zA-Z0-9-]{0,61}[a-zA-Z0-9]\.)+(?:[a-zA-Z]{2,})$/;

        if (!validDomain.test(domain)){
            utils.scrollTo(this.ui.domain);
            utils.notifyInline('Wrong domain name', this.ui.domain);
            return;
        }

        if (!!cert !== !!key) {
            if (!cert){
                utils.notifyInline(`Certificate can't be empty`, this.ui.certificate);
            }
            if (!key){
                utils.notifyInline(`Key can't be empty`, this.ui.key);
            }
            return;
        }

        utils.preloader.show();
        this.model.save(data)
            .always(utils.preloader.hide)
            .then(function(){
                App.navigate('domains', {trigger: true});
                utils.notifyWindow(
                    `Domain "${domain}" ${isNew ? 'added' : 'updated'}`, 'success');
            }, utils.notifyWindow);

        App.getDomainsCollection().done((domainCollection) => {
            domainCollection.add(this.model, {merge: true});
        });
    },
});

export const DomainsLayoutView = Marionette.LayoutView.extend({
    template: domainsLayoutTpl,
    regions: {
        breadcrumb: '#breadcrumb',
        main      : '#main',
        pager     : '#pager',
    },
    onBeforeShow: utils.preloader.show,
    onShow: utils.preloader.hide
});

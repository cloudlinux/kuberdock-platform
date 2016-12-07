import App from 'isv/app';
// import * as Model from 'isv/model';
import * as utils from 'app_data/utils';
import detailsTpl from './templates/details.tpl';
import confTpl from './templates/conf.tpl';
import confContainerTpl from './templates/conf_container.tpl';
import editDomainTpl from './templates/edit_domain.tpl'

// import 'bootstrap-editable';
// import 'jqplot';
// import 'jqplot-axis-renderer';
// import 'bootstrap-select';
import 'tooltip';

export const Details = Marionette.ItemView.extend({
    template: detailsTpl,
    onBeforeShow: utils.preloader2.show,
    onShow: utils.preloader2.hide,
    modelEvents: {
        change: 'render',
    },

    ui: {
        tooltip: '[data-toggle="tooltip"]',
        resetAdminPassword: '.reset-admin-password',
        copyAdminPassword: '.copy-password',
    },

    events: {
        'click @ui.resetAdminPassword': 'resetAdminPassword',
        'click @ui.copyAdminPassword': 'copyAdminPassword',
    },

    onDomRefresh(){ this.ui.tooltip.tooltip(); },

    templateHelpers(){
        return {
            prettyStatus: this.model.getPrettyStatus(),
            appLastUpdate: utils.localizeDatetime({
                dt: this.model.get('appLastUpdate'),
                formatString: 'YYYY-MM-DD HH:mm:ss (z)',
            }),
        };
    },
    resetAdminPassword(){
        this.model.resetPassword().then(({exitStatus = 1, result = ''} = {}) => {
            if (exitStatus !== 0)
                return utils.notifyWindow(
                    `Failed to reset password: ${exitStatus}${result ? ', ' + result : ''}`);
            this.adminPassword = result;
            this.ui.copyAdminPassword.removeClass('hidden');
            utils.notifyWindow('Admin password was reset successfully. ' +
                               'You can copy it to clipboard now.', 'success');
        });
    },
    copyAdminPassword(){
        utils.copyLink(this.adminPassword, 'Admin password copied to clipboard.');
    },
});

export const ContainerConfig = Marionette.ItemView.extend({
    template: confContainerTpl,
    onBeforeShow: utils.preloader2.show,
    onShow: utils.preloader2.hide,
    modelEvents: {
        change: 'render',
    },
    ui: {
        copySshLink: '.copy-ssh-link',
        tooltip : '[data-toggle="tooltip"]',
        copySshPassword: '.copy-ssh-password',
        resetSshPassword: '.reset-ssh-password',
    },
    events: {
        'click @ui.copySshLink': 'copySshLink',
        'click @ui.copySshPassword': 'copySshPassword',
    },
    triggers: {
        'click @ui.resetSshPassword': 'pod:resetSshPassword',
    },
    onDomRefresh(){ this.ui.tooltip.tooltip(); },
    copySshLink(){
        let sshPassword = this.model.get('link');
        if (sshPassword) {
            utils.copyLink(sshPassword, 'SSH link copied to clipboard');
        } else {
            utils.notifyWindow(
                'SSH access credentials are outdated. Please, click Get SSH' +
                ' access to generate new link and password', 'error');
        }
    },
    copySshPassword(){
        let sshPassword = this.model.get('auth');
        if (sshPassword) {
            utils.copyLink(sshPassword, 'SSH password copied to clipboard');
        } else {
            utils.notifyWindow(
                'SSH access credentials are outdated. Please, click Get SSH' +
                ' access to generate new link and password', 'error');
        }
    }
});

export const Conf = Marionette.LayoutView.extend({
    template: confTpl,
    onBeforeShow: utils.preloader2.show,
    modelEvents: {
        change: 'render',
    },
    ui: {
        containerTab  : '.container-tab',
        tooltip : '[data-toggle="tooltip"]'
    },
    regions: {
        currentContainer: '.container-info',
    },
    events: {
        'click @ui.containerTab': 'selectContainer',
    },
    childEvents: {
        'pod:resetSshPassword': 'resetSshPassword',
    },

    initialize(){
        this.model.set('current_tab_num', 0);
        this.containerName = this.model.get('containers').at(0).get('name');
    },
    templateHelpers(){
        return {
            activeSshTab: this.containerName,
        };
    },
    onShow(){
        this.updateContainerInfo();
        utils.preloader2.hide();
    },
    onDomRefresh(){ this.ui.tooltip.tooltip(); },
    selectContainer(event){
        this.containerName = $(event.currentTarget).attr('data-name');
        this.render();
    },
    onRender() {
        this.updateContainerInfo();
    },
    updateContainerInfo(){
        let directAccess = this.model.get('direct_access'),
            link = directAccess ? directAccess.links[this.containerName] : null,
            containerInfo = new Backbone.Model({
                name: this.containerName,
                link: link,
                auth: directAccess ? directAccess.auth : '',
            });
        this.currentContainer.show(
            new ContainerConfig({model: containerInfo})
        );
    },
    resetSshPassword(){
        this.model.resetSshAccess().then(()=>{
            this.updateContainerInfo();
        });
    }
});

export const EditDomain = Marionette.ItemView.extend({
    template: editDomainTpl,
    onBeforeShow: utils.preloader2.show,
    onShow: utils.preloader2.hide,
    modelEvents: {
        change: 'render',
    },
    ui: {
        saveButton: '.save-button',
        domainName: '#domain-name',
    },
    events: {
        'click @ui.saveButton': 'save',
    },
    save() {
        this.model.setCustomDomain(this.ui.domainName.val()).then(() => {
            App.navigate('app/conf', {trigger: true});
        });
    }
});

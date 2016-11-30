import * as utils from 'app_data/utils';
import backupListTpl from './templates/backup_list.tpl';
import backupItemTpl from './templates/backup_item.tpl';
import 'tooltip';

const BackupItem = Marionette.ItemView.extend({
    template: backupItemTpl,
    tagName: 'tr',
    ui: {
        exportBtn: '.export',
        restoreBtn: '.restore',
        tooltip: '[data-toggle="tooltip"]',
    },
    events: {
        'click @ui.exportBtn': 'onExport',
        'click @ui.restoreBtn': 'onRestore'
    },
    modelEvents: { 'change': 'render' },
    onDomRefresh(){ this.ui.tooltip.tooltip(); },
    onExport(){
        alert('add export command');
    },
    onRestore(){
        utils.modalDialog({
            title: 'Do you want to restore ?',
            body: `Are you sure you want to restore application to this backup
                   (${this.model.get('timestamp')})<br/>All data will be reverted to that backup`,
            small: true,
            show: true,
            footer: {
                buttonOk() {
                    alert('add restore command');
                },
                buttonCancel: true
            }
        });
    }
});

export const Backup = Marionette.CompositeView.extend({
    template: backupListTpl,
    childView: BackupItem,
    childViewContainer: 'tbody'
});

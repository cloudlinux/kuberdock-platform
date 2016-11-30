import backupListTpl from './templates/backup_list.tpl';
import backupItemTpl from './templates/backup_item.tpl';

const BackupItem = Marionette.ItemView.extend({
    template: backupItemTpl,
    tagName: 'tr'
});

export const Backup = Marionette.CompositeView.extend({
    template: backupListTpl,
    tagName: 'table',
    className: 'table',
    childView: BackupItem,
    childViewContainer: 'tbody'
});
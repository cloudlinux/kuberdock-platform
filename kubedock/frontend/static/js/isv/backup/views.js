/*
 * KuberDock - is a platform that allows users to run applications using Docker
 * container images and create SaaS / PaaS based on these applications.
 * Copyright (C) 2017 Cloud Linux INC
 *
 * This file is part of KuberDock.
 *
 * KuberDock is free software; you can redistribute it and/or
 * modify it under the terms of the GNU General Public License
 * as published by the Free Software Foundation; either version 2
 * of the License, or (at your option) any later version.
 *
 * KuberDock is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with KuberDock; if not, see <http://www.gnu.org/licenses/>.
 */

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

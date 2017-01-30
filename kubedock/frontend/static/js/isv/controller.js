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

import App from 'isv/app';
// import Model from 'isv/model';
import * as utils from 'app_data/utils';

import {Details as AppDetailsView,
        Conf as AppConfView,
        EditDomain as AppEditDomainView
        } from 'isv/application/views';
import {Backup as AppBackupView} from 'isv/backup/views';
import {Topbar, Sidebar} from 'isv/misc/views';
import {AppUpdate} from 'isv/model';

const controller = {
    doLogin(){
        utils.notifyWindow('Session expired. Reload this page.');
        App.rootLayout.topbar.reset();
        App.rootLayout.contents.reset();
    },

    showApplicationView(view, tab){
        App.rootLayout.contents.show(view);
        if (!App.rootLayout.topbar.hasView())
            App.rootLayout.topbar.show(new Topbar({model: view.model}));
        App.rootLayout.sidebar.show(new Sidebar({tab}));
    },

    appDetails(){
        utils.preloader2.show();
        App.getPodCollection().then(podCollection => {
            const pod = podCollection.at(0);
            if (!pod){
                utils.notifyWindow('Application not found');
                // TODO: redirect to "order app" page
                return;
            }
            new AppUpdate({}, {container: pod}).fetch().done(appUpdate => {
                let detailsView = new AppDetailsView({
                    model: pod,
                    updateData: appUpdate.data
                });
                this.showApplicationView(detailsView, 'details');
                utils.preloader2.hide();
            });
        });
    },

    appConf(){
        utils.preloader2.show();
        App.getPodCollection().done(podCollection => {
            const pod = podCollection.at(0);
            if (!pod){
                utils.notifyWindow('Application not found');
                return;
            }
            let confView = new AppConfView({model: pod});
            this.showApplicationView(confView, 'conf');
            utils.preloader2.hide();
        });
    },

    appConfDomain(){
        utils.preloader2.show();
        App.getPodCollection().done(podCollection => {
            const pod = podCollection.at(0);
            if (!pod){
                utils.notifyWindow('Application not found');
                return;
            }
            let confDomainView = new AppEditDomainView({model: pod});
            this.showApplicationView(confDomainView, 'conf');
            utils.preloader2.hide();
        });
    },

    appBackups(){
        utils.preloader2.show();
        $.when(App.getPodCollection(), App.getBackupCollection())
            .then((podCollection, backupCollection) => {
                const pod = podCollection.at(0);
                if (!pod) {
                    utils.notifyWindow('Application not found');
                    // TODO: redirect to "order app" page
                    return;
                }
                let backupView = new AppBackupView({
                    collection: backupCollection,
                    model: pod
                });
                this.showApplicationView(backupView, 'backups');
                utils.preloader2.hide();
            });
    },
};

export default Marionette.Object.extend(controller);

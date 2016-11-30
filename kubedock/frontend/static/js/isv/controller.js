import App from 'isv/app';
// import Model from 'isv/model';
import * as utils from 'app_data/utils';

import {Details as AppDetailsView,
        Conf as AppConfView,
        } from 'isv/application/views';
import {Backup as AppBackupView} from 'isv/backup/views';
import {Topbar, Sidebar} from 'isv/misc/views';

const controller = {
    doLogin(options){
        console.log('not authorized');
        // TODO: redirect to WHMCS -> login -> redirect back with SSO?
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
            let detailsView = new AppDetailsView({model: pod});
            this.showApplicationView(detailsView, 'details');
            utils.preloader2.hide();
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

    appBackups(){
        utils.preloader2.show();
        $.when(App.getPodCollection(), App.getBackupCollection())
                .then((podCollection, backupCollection) => {
            const pod = podCollection.at(0);
            if (!pod){
                utils.notifyWindow('Application not found');
                // TODO: redirect to "order app" page
                return;
            }
            let backupView = new AppBackupView({collection: backupCollection, model: pod});
            this.showApplicationView(backupView, 'backups');
            utils.preloader2.hide();
        });
    },
};

export default Marionette.Object.extend(controller);

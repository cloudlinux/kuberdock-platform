// import App from 'isv/app';
// import * as Model from 'isv/model';
import * as utils from 'app_data/utils';
import sidebarTpl from './templates/sidebar.tpl';
import topbarTpl from './templates/topbar.tpl';

// import 'tooltip';

export const Sidebar = Marionette.ItemView.extend({
    template: sidebarTpl,
    onBeforeShow(){ utils.preloader2.show(); },
    onShow(){ utils.preloader2.hide(); },
    initialize(options){
        this.tab = options.tab;
    },
    templateHelpers(){
        return {
            tab : this.tab
        };
    }
});


export const Topbar = Marionette.ItemView.extend({
    template: topbarTpl,
    onBeforeShow(){ utils.preloader2.show(); },
    onShow(){ utils.preloader2.hide(); },

    ui: {
        'goToAppButton': '.go-to-app',
        'restartButton': '.restart-btn',
        'startButton': '.start-btn',
        'stopButton': '.stop-btn',
    },
    events: {
        'click @ui.goToAppButton': 'goToApp',
        'click @ui.restartButton': 'restart',
        'click @ui.startButton': 'start',
        'click @ui.stopButton': 'stop',
    },
    modelEvents: {
        'change:status': 'render',
    },

    templateHelpers() {
        return {
            ableTo: _.bind(this.model.ableTo, this.model),
        };
    },

    goToApp() {
        window.open(`http://${this.model.get('domain')}/`, '_blank').focus();
    },
    restart(){
        this.model.command('redeploy');
    },
    start(){
        this.model.command('start');
    },
    stop(){
        this.model.command('stop');
    },
});

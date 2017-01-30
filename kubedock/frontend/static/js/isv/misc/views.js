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
        'change:ready': 'render',
    },

    templateHelpers() {
        return {
            ableTo: _.bind(this.model.ableTo, this.model),
        };
    },

    goToApp() {
        let domain = this.model.get('custom_domain') || this.model.get('domain');
        window.open(`http://${domain}/`, '_blank').focus();
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

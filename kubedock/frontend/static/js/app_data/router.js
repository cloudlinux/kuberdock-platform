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

define(['marionette'], function(Marionette){
    "use strict";
    var router = Marionette.AppRouter.extend({
        appRoutes: {
            ''                                : 'index',
            'index'                           : 'index',
            'pods'                            : 'showPods',
            'pods/new'                        : 'podWizardStepImage',
            'pods/:id'                        : 'showPodContainers',
            'pods/:id/stats'                  : 'showPodStats',
            'pods/:id/upgrade'                : 'showPodUpgrade',
            // 'pods/:id/container/:name/upgrade': 'showPodUpgrade',
            'pods/:id/container/:name(/:tab)' : 'showPodContainer',
            'pods/:id/edit'                   : 'editEntirePod',
            'pods/:id/container/:name/edit/env': 'editContainerEnv',
            'pods/:id/container/:name/edit/general': 'editContainerGeneral',
            'pods/:id/switch-package'         : 'changeAppPackage',

            'nodes'                           : 'showNodes',
            'nodes/add'                       : 'showAddNode',
            'nodes/:id/:tab'                  : 'showDetailedNode',
            'users'                           : 'showUsers',
            // 'users/online'                    : 'showOnlineUsers',
            'users/create'                    : 'showCreateUser',
            'users/edit/:id'                  : 'showEditUser',
            'users/activity'                  : 'showAllUsersActivity',
            // 'users/online/:id'                : 'showUserActivity',
            'users/profile/:id/general'       : 'showProfileUser',
            'users/profile/:id/logHistory'    : 'showProfileUserLogHistory',
            'predefined-apps'                 : 'listPredefinedApps',
            'predefined-apps/newapp'          : 'showPredefinedAppUploadForm',
            'predefined-apps/:id/edit'        : 'showPredefinedAppUploadForm',
            'settings'                        : 'showSettings',
            'settings/general'                : 'showGeneralSettings',
            'settings/usage'                  : 'showLicense',
            'settings/domain'                 : 'showDomainSettings',
            'settings/billing'                : 'showBillingSettings',
            'settings/profile'                : 'editProfileSettings',
            'ippool'                          : 'showNetworks',
            'ippool/create'                   : 'showCreateNetwork',
            'ippool/:id'                      : 'showSubnetIps',
            'persistent-volumes'              : 'showPersistentVolumes',
            'publicIPs'                       : 'showIPs',
            'domains'                         : 'showDomains',
            'domains/add'                     : 'showAddDomain',
            // 'domains/:id/edit'                : 'showAddDomain',
            '*nothingSimilar'                 : 'pageNotFound'


        }
    });
    return router;
});

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
            'pods/:id/container/:name/upgrade': 'showPodUpgrade',
            'pods/:id/container/:name(/:tab)' : 'showPodContainer',
            'pods/:id/edit'                   : 'editEntirePod',
            'pods/:id/container/:name/edit/env': 'editContainerEnv',
            'pods/:id/container/:name/edit/general': 'editContainerGeneral',

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
            'settings'                        : 'showSettings',
            'settings/general'                : 'showGeneralSettings',
            'settings/license'                : 'showLicense',
            'settings/profile'                : 'editProfileSettings',
            'ippool'                          : 'showNetworks',
            'ippool/create'                   : 'showCreateNetwork',
            'persistent-volumes'              : 'showPersistentVolumes',
            'persistent_volumes'              : 'showPersistentVolumes',
            'publicIPs'                       : 'showIPs',
            '*nothingSimilar'                 : 'pageNotFound'
        }
    });
    return router;
});

define(['marionette'], function(Marionette){
    "use strict";
    var router = Marionette.AppRouter.extend({
        appRoutes: {
            'pods'                            : 'showPods',
            'pods/:id'                        : 'showPodItem',
            'newpod'                          : 'createPod',
            'pods/poditem/:id/:name'          : 'showPodContainer',
            'nodes'                           : 'showNodes',
            'nodes/add'                       : 'showAddNode',
            'nodes/:id/:tab'                  : 'showDetailedNode',
            'users'                           : 'showUsers',
            'users/online'                    : 'showOnlineUsers',
            'users/create'                    : 'showCreateUser',
            'users/edit/:id'                  : 'showEditUser',
            'users/activity'                  : 'showAllUsersActivity',
            'users/online/:id'                : 'showUserActivity',
            'users/profile/:id/general'       : 'showProfileUser',
            'users/profile/:id/logHistory'    : 'showProfileUserLogHistory',
            'predefined-apps'                 : 'listPredefinedApps',
            'settings'                        : backendData.administrator
                                                    ? 'showGeneralSettings'
                                                    : 'editProfileSettings',
            'settings/general'                : 'showGeneralSettings',
            'settings/profile'                : 'editProfileSettings',
            'settings/permissions'            : 'showPermissionSettings',
            'settings/notifications'          : 'showNotificationSettings',
            'settings/notifications/add'      : 'addNotificationSettings',
            'settings/notifications/edit/:id' : 'editNotificationSettings',
            'ippool'                          : 'showNetworks',
            'ippool/create'                   : 'showCreateNetwork',
            'persistent-volumes'              : 'showPersistentVolumes',
            'persistent_volumes'              : 'showPersistentVolumes',
            'publicIPs'                       : 'showIPs',
        }
    });
    return router;
});
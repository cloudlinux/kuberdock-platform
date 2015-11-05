define(['marionette'], function(Marionette){
    "use strict";
    var router = Marionette.AppRouter.extend({
        appRoutes: {
            ''            : 'showNodes',
            'add'         : 'showAddNode',
            ':id/:tab/'   : 'showDetailedNode'
        }
    });
    return router;
});
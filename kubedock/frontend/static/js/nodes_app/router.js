define(['marionette'], function(Marionette){
    "use strict";
    var router = Marionette.AppRouter.extend({
        appRoutes: {
            '': 'showNodes',
            'add': 'showAddNode',
            'detailed/:id/:tab/': 'showDetailedNode'
        }
    });
    return router;
});
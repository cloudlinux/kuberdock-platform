define(['marionette'], function(Marionette){
    "use strict";
    var router = Marionette.AppRouter.extend({
        appRoutes: {
            'list': 'listApps',
        }
    });
    return router;
});
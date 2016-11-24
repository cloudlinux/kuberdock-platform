

export default Marionette.AppRouter.extend({
    appRoutes: {
        ''                                : 'appDetails',
        'app'                             : 'appDetails',
        'app/details'                     : 'appDetails',
        'app/conf'                        : 'appConf',
        'app/backups'                     : 'appBackups',
    }
});

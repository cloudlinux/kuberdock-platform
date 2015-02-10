from flask.ext.assets import Environment, Bundle

app_css = Bundle(
    'css/bootstrap.css',
#   'css/bootstrap-theme.css',
    'css/bootstrap-editable.css',
    'css/jquery.jqplot.min.css',
    'css/app.css',
    'css/main.less',
    filters="cssmin,less", output="css/app.min.css")

vendor_js = Bundle(
    'js/lib/jquery.js',
    'js/lib/underscore.js',
    'js/lib/backbone.js',
    'js/lib/backbone.marionette.js',
    'js/lib/bootstrap.js',
    'js/lib/backbone.paginator.js',
    'js/lib/spin.min.js',
    'js/lib/jquery.spin.js',
    'js/lib/bootstrap-editable.min.js',
    'js/lib/jquery.jqplot.min.js',
    'js/lib/jqplot.dateAxisRenderer.min.js',
    filters="jsmin", output="js/lib.min.js")

#: application js bundle
app_js = Bundle(
    'js/app.js',
    'js/data/pods.js',
    'js/controllers/pods.js',
    'js/views/pods.js',
    'js/main.js',
    filters="jsmin", output="js/app.min.js")

users_app_js = Bundle(
    'js/users_app/users_app.js',
    filters="jsmin", output="js/users_app/users_app.min.js")


minions_app_js = Bundle(
    'js/minions_app/minions_app.js',
    filters="jsmin", output="js/minions_app/minions_app.min.js")


def init_app(app):
    webassets = Environment(app)
    webassets.register('app_css', app_css)
    webassets.register('vendor_js', vendor_js)
    webassets.register('app_js', app_js)
    webassets.register('users_app_js', users_app_js)
    webassets.register('minions_app_js', minions_app_js)
    webassets.manifest = 'cache' if not app.debug else False
    webassets.cache = not app.debug
    webassets.debug = app.debug


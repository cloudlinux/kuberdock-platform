from flask.ext.assets import Environment, Bundle

app_css = Bundle(
    'css/bootstrap.css',
    'css/bootstrap-editable.css',
    'css/jquery.jqplot.min.css',
    'css/bootstrap-select.min.css',
    'css/main.less',
    filters="cssmin", output="css/app.min.css")

less_css = Bundle(
    'css/main.less',
    filters="cssmin", output="css/less.min.css")

vendor_js = Bundle(
    'js/lib/jquery.js',
    'js/lib/underscore-min.js',
    'js/lib/backbone.js',
    'js/lib/backbone.marionette.js',
    'js/lib/bootstrap.js',
    'js/lib/backbone.paginator.js',
    'js/lib/bootstrap-editable.min.js',
    'js/lib/jquery.jqplot.min.js',
    'js/lib/jqplot.dateAxisRenderer.min.js',
    'js/lib/bootstrap-select.min.js',
    'js/lib/notify.min.js',
    'js/lib/moment.min.js',
    'js/lib/moment-timezone-with-data.min.js',
    filters="jsmin", output="js/lib.min.js")

less_js = Bundle(
    'js/lib/less.js',
    filters="jsmin", output="js/less.min.js"
)
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


nodes_app_js = Bundle(
    'js/nodes_app/nodes_app.js',
    filters="jsmin", output="js/nodes_app/nodes_app.min.js")


def init_app(app):
    webassets = Environment(app)
    webassets.register('app_css', app_css)
    webassets.register('less_css', less_css)
    webassets.register('vendor_js', vendor_js)
    webassets.register('app_js', app_js)
    webassets.register('less_js', less_js)
    webassets.register('users_app_js', users_app_js)
    webassets.register('nodes_app_js', nodes_app_js)
    webassets.manifest = 'cache' if not app.debug else False
    webassets.cache = not app.debug
    webassets.debug = app.debug


from flask.ext.assets import Environment, Bundle

app_css = Bundle(
    'css/bootstrap.css',
#   'css/bootstrap-theme.css',
    'css/bootstrap-editable.css',
    'css/app.css',
    filters="cssmin", output="css/app.min.css")

vendor_js = Bundle(
    'js/lib/jquery.js',
    'js/lib/underscore.js',
    'js/lib/backbone.js',
    'js/lib/backbone.marionette.js',
    'js/lib/bootstrap.js',
    'js/lib/backbone.paginator.js',
    'js/lib/backbone.wreqr.js',
    'js/lib/spin.min.js',
    'js/lib/jquery.spin.js',
    'js/lib/bootstrap-editable.min.js',
    filters="jsmin", output="js/lib.min.js")

#: application js bundle
app_js = Bundle(
    'js/app.js',
    'js/data/pods.js',
    'js/controllers/pods.js',
    'js/views/pods.js',
    'js/main.js',
    filters="jsmin", output="js/app.min.js")

def init_app(app):
    webassets = Environment(app)
    webassets.register('app_css', app_css)
    webassets.register('vendor_js', vendor_js)
    webassets.register('app_js', app_js)
    webassets.manifest = 'cache' if not app.debug else False
    webassets.cache = not app.debug
    webassets.debug = app.debug


/*eslint-env node */
var path = require('path');
var webpack = require('webpack');
var CompressionPlugin = require("compression-webpack-plugin");
var LessPluginCleanCSS = require('less-plugin-clean-css');
var ExtractTextPlugin = require('extract-text-webpack-plugin');
var conf = require('./config');


// sets a more convenient names of sources in sourceMaps and fixes ExtractTextPlugin bug:
// kd-js:// -- our js
// kd-css:// -- our less/css
// webpack:// -- everything else: libs, frameworks (in node_modules, js/lib, and css)
var prettySourceMapName = (info) => {
    var result = info.absoluteResourcePath.replace(__dirname, '');
    if (/^\/js\/(?:app_data|isv)\/.*?\.(js|tpl)/.test(result))
        return result.replace(/^\/js\/(app_data|isv)\//, 'kd-js:///$1/');
    if (/^(?:webpack:\/\/)?\/css\/.*?\.less/.test(result))
        return result.replace(/^(?:webpack:\/\/)?\/css\//, 'kd-css:///');
    return 'webpack:///' + result.replace(  // all libs and webpack buidins
        /^(?:webpack:\/\/)?(?:\/js\/lib|\/node_modules|webpack)\//, '');
};


var webpackConfig = {
    entry: {
        full: ['babel-polyfill', './js/app_data/entry.js'],
        isv: ['babel-polyfill', './js/isv/entry.js'],
    },
    output: {
        publicPath: '/static/',
        path: __dirname,
        filename: `${conf.BUILD_PREFIX}-[name].bundle.js`,
        chunkFilename: `${conf.BUILD_PREFIX}-[id].chunk.js`,
        devtoolModuleFilenameTemplate: prettySourceMapName,
        devtoolFallbackModuleFilenameTemplate: info => (
            `${prettySourceMapName(info)}?${info.hash}`),
    },
    resolve: {
        // roots for imports, apart from node_modules
        root: [path.resolve('./js'), path.resolve('./css')],
        alias: {  // shortcuts, precompiled & minified builds, and packages that are not in npm
            'marionette'          : 'backbone.marionette',
            'tooltip'             : 'bootstrap/js/tooltip.js',
            'bootstrap-editable'  : 'x-editable/dist/bootstrap3-editable/js/bootstrap-editable.min',
            'jqplot'              : 'lib/jquery.jqplot.min',
            'jqplot-axis-renderer': 'lib/jqplot.dateAxisRenderer.min',
            // prepackaged versions (due to large size or fucked-up internal imports)
            'js-yaml'             : 'js-yaml/dist/js-yaml.min',
            'sinon'               : 'sinon/pkg/sinon',
            'babel-polyfill'      : 'babel-polyfill/dist/polyfill.min.js',
        }
    },
    module: {
        noParse: [  // do not mess with prepackaged modules
            /\/node_modules\/sinon\//,
            /\/node_modules\/js-yaml\/dist\//,
            /\/node_modules\/babel-polyfill\/dist\//,
        ],
        loaders: [{
            // add bootstrap-select styles as dependency for bootstrap-select js
            test: require.resolve('bootstrap-select'),
            loader: 'imports',
            query: {css: 'bootstrap-select/dist/css/bootstrap-select.min.css'},
        }, {
            // add bootstrap-editable styles as dependency for bootstrap-editable js
            test: require.resolve('x-editable/dist/bootstrap3-editable/js/bootstrap-editable.min'),
            loader: 'imports',
            query: {css: 'x-editable/dist/bootstrap3-editable/css/bootstrap-editable.css'},
        }, {
            // add jqplot styles as dependency for jqplot js
            test: /jqplot.+js$/, loader: 'imports', query: {css: 'jquery.jqplot.min.css'},
        }, {

            // @import and url() in less/css
            test: /\.(?:png|gif|svg|ttf|woff2?|eot)$/, include: /node_modules/,
            // files less then 16kb will be converted to the dataURI
            // the others will be moved to /static/
            loader: 'url', query: {limit: 16384, name: `${conf.BUILD_PREFIX}-[name]-[hash].[ext]`},
        }, {
            // same, but only for our files: no emit required
            test: /\.(?:png|gif|svg|ttf|woff2?|eot)$/, exclude: /node_modules/,
            loader: 'url', query: {limit: 16384, name: '[path][name].[ext]', emitFile: false},
        }, {
            test: /\.js$/, include: /\/js\/(?:app_data|isv)\//, loader: 'babel',
            query: {cacheDirectory: !conf.PROD,  // do not use cache in prod
                    plugins: [
                        'transform-decorators',
                        ...(conf.TEST ? ['rewire'] : []),
                    ]},
        }, {
            test: /\.json$/, loader: 'json',
        }, {
            test: /\.tpl$/, exclude: /node_modules/, loader: 'ejs'
        }, {
            test: /\.less$/, loader: ExtractTextPlugin.extract('style',
                conf.PROD ? 'css!less' : 'css?sourceMap!less?sourceMap'),
        }, {
            test: /\.css$/, loader: ExtractTextPlugin.extract('style',
                conf.PROD ? 'css' : 'css?sourceMap'),
        }]
    },
    devtool: conf.PROD ? undefined : '#source-map',
    lessLoader: {
        lessPlugins: conf.PROD ? [new LessPluginCleanCSS({advanced: true})] : [],
    },
    stats: {  // console output config
        hash: false,
        chunks: false,
        version: false,
        reasons: false,
        modules: true,
        exclude: ['node_modules'],  // show only list of our own modules
        colors: require('supports-color'),
    },
    plugins: [
        // webpack will try to load all possible options for dynamic imports,
        // like `require('./locale/' + name);`, but we don't need ANY locales
        // for moment.js, so we'll just ignore those imports
        new webpack.IgnorePlugin(/^\.\/locale$/, /moment$/),

        // Put all stuff in one file. Do not split in separate chunks.
        // TODO: split libs/common/admin/user parts of code, so libs would be
        //       cached and user would load only common+user part of prepared.js
        new webpack.optimize.LimitChunkCountPlugin({maxChunks: 1}),

        // put css in a separate file (not in prepared.js)
        new ExtractTextPlugin(`${conf.BUILD_PREFIX}-[name].css`, {allChunks: true}),

        // make those modueles available in every other module: {globalName: 'module',..}
        new webpack.ProvidePlugin({
            $: 'jquery', jQuery: 'jquery', _: 'underscore',
            Backbone: 'backbone', Marionette: 'backbone.marionette'}),

        // define some global variables or macroses
        new webpack.DefinePlugin({
            PROD: JSON.stringify(conf.PROD),
            TEST: JSON.stringify(conf.TEST),
        }),
        new webpack.optimize.CommonsChunkPlugin(`${conf.BUILD_PREFIX}-init.js`),
    ],
};

if (conf.PROD){
    webpackConfig.plugins.push(  // prod-only plugins
        // minify
        new webpack.optimize.DedupePlugin(),
        new webpack.optimize.OccurrenceOrderPlugin(),
        new webpack.optimize.UglifyJsPlugin({
            compress: {
                warnings: false,
                keep_fargs: false,  // remove unused arguments
            },
            output: {
                comments: /license/i,  // preserve all comments with license
            },
        }),
        new CompressionPlugin()
    );
}

module.exports = webpackConfig;

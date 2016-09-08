/* eslint-env node */
/* eslint-disable no-console */
var process = require('process');
process.env.NODE_TLS_REJECT_UNAUTHORIZED = "0";  // allow requests to KD with self-signed cert

var express = require('express');
var logger = require('morgan');
var request = require('request');
var webpack = require('webpack');
var webpackDevMiddleware = require("webpack-dev-middleware");
var ProgressPlugin = require('webpack/lib/ProgressPlugin');
var conf = require('./config');
var webpackConfig = require('./webpack.config.js');


var compiler = webpack(webpackConfig);
compiler.apply(new ProgressPlugin(function(percentage, msg) {
    process.stdout.write(((percentage * 100)|0) + '% ' + msg + '\r');
}));

var app = express();

// recompile and serve prepared.js and prepared.css in memory, don't write it on disk
app.use(webpackDevMiddleware(compiler, {
    publicPath: webpackConfig.output.publicPath,
    stats: webpackConfig.stats,
    watchOptions: {poll: true},
}));
// serve static files directly from current directory
app.use('/static', express.static('.'));
// app.get('/', (req, res) => res.sendFile(__dirname + '/index.html'));
// log and proxy api calls to kuberdock server
app.use(logger(`proxy to KD (${conf.API_HOST}): :status :method :url (:response-time ms)`));
app.use('/', function(req, res) {
    var url = `https://${conf.API_HOST}${req.url}`;
    req.pipe(request(url)).on('response', function(res) {
        delete res.headers['content-security-policy-report-only'];
        var location = res.headers.location;
        if (location && location.startsWith(`https://${conf.API_HOST}`))
            res.headers.location = location.replace(
                `https://${conf.API_HOST}`,
                `http://localhost:${conf.LOCAL_PORT}`);
    }).pipe(res);
});

app.listen(conf.LOCAL_PORT, function () {
    console.log(`Dev server listening on port ${conf.LOCAL_PORT}...`);
});

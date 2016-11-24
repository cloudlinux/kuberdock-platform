/* eslint-env node */
/* eslint-disable no-console */
const process = require('process');
process.env.NODE_TLS_REJECT_UNAUTHORIZED = '0';  // allow requests to KD with self-signed cert

const chalk = require('chalk');
const express = require('express');
const logger = require('morgan');
const request = require('request');
const webpack = require('webpack');
const webpackDevMiddleware = require("webpack-dev-middleware");
const ProgressPlugin = require('webpack/lib/ProgressPlugin');
const conf = require('./config');
conf.BUILD_PREFIX = 'prepared';
const webpackConfig = require('./webpack.config.js');


if (!conf.API_HOST)
    throw chalk.bold.red`
        You need to specify API_HOST either in local-config.js
        or through environment variable, like
        API_HOST=1.2.3.4 npm run dev`;


let compiler = webpack(webpackConfig);
compiler.apply(new ProgressPlugin(function(percentage, msg) {
    process.stdout.write(((percentage * 100)|0) + '% ' + msg + '\r');
}));

let app = express();

app.use('/static', function(req, res, next) {
   req.url = req.url.replace(/^\/prepared-build\w+/, '/' + conf.BUILD_PREFIX);
   next();
});

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
app.use('/', function(req, res, next) {
    let url = `https://${conf.API_HOST}${req.url}`;
    let apiRequest = request(url).on('error', err => next(err));
    req.pipe(apiRequest).on('response', function(res) {
        delete res.headers['content-security-policy-report-only'];
        let location = res.headers.location;
        if (location && location.startsWith(`https://${conf.API_HOST}`))
            res.headers.location = location.replace(
                `https://${conf.API_HOST}`,
                `http://localhost:${conf.LOCAL_PORT}`);
    }).pipe(res);
});

app.use(function(err, req, res, next) {
    console.error(chalk.bold.red(err.stack));
    res.status(500).type('.txt').send(`Dev server exception: \n${err.stack}`);
});

app.listen(conf.LOCAL_PORT, function () {
    console.log(`Dev server listening on port ${conf.LOCAL_PORT}...`);
});

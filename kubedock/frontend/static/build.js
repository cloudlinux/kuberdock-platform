/*
 * KuberDock - is a platform that allows users to run applications using Docker
 * container images and create SaaS / PaaS based on these applications.
 * Copyright (C) 2017 Cloud Linux INC
 *
 * This file is part of KuberDock.
 *
 * KuberDock is free software; you can redistribute it and/or
 * modify it under the terms of the GNU General Public License
 * as published by the Free Software Foundation; either version 2
 * of the License, or (at your option) any later version.
 *
 * KuberDock is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with KuberDock; if not, see <http://www.gnu.org/licenses/>.
 */

/* eslint-env node */
/* eslint-disable no-console */
const process = require('process');
const webpack = require("webpack");
const fs = require('fs');
const path = require('path');
const conf = require('./config');
const webpackConfig = require('./webpack.config.js');

const filesToPatch = ['../templates/index.html', '../templates/tests/index.html'];

const errHandler = function(err){
    if (!err) return;
    console.error(err.stack || err);
    if (err.details) console.error(err.details);
    process.on("exit", function(){ process.exit(1); });
};

webpack(webpackConfig, function(err, stats){
    console.log(stats.toString(webpackConfig.stats));

    let jsonStats = stats.toJson(webpackConfig.stats);
    if (err || jsonStats.errors.length || jsonStats.warnings.length)
        return errHandler(err || 'failed to build');

    for (let fileToPatch of filesToPatch){
        let fullPath = path.join(webpackConfig.output.path, fileToPatch);
        fs.readFile(fullPath, 'utf8', function(err, data){
            if (err)
                return errHandler(err);
            let patched = data.replace(/\bprepared\b/g, conf.BUILD_PREFIX);
            fs.writeFile(fullPath, patched, 'utf8', errHandler);
        });
    }
});

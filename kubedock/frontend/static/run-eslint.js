/* eslint-env node, es6 */
/* eslint no-console: off */

var ERRORS_TRESHOLD = 322;

var CLIEngine = require('eslint').CLIEngine;
var process = require('process');

var cli = new CLIEngine({configFile: '.eslintrc'});
var formatter = cli.getFormatter();

var report = cli.executeOnFiles(["./js/app_data/"]),
    errorCount = report.errorCount + report.warningCount;

console.log(formatter(report.results));
console.log(`
####################### Linter results ############################
Found errors   : ${errorCount}
Errors treshold: ${ERRORS_TRESHOLD}
`);
process.exit(errorCount > ERRORS_TRESHOLD);

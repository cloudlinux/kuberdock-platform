<% if (isPending) { %>
    <div class="container" id="add-image">
        <div class="col-md-3 sidebar">
            <ul class="nav nav-sidebar">
                <li role="presentation" class="success">Choose image</li>
                <li role="presentation" class="success">Set up image</li>
                <li role="presentation" class="active">Environment variables</li>
                <li role="presentation">Final</li>
            </ul>
        </div>
        <div id="details_content" class="col-sm-9 set-up-image clearfix no-padding">
            <div id="tab-content" class="environment clearfix">
                <div class="col-sm-12 no-padding fields">
                    <div class="col-sm-4 no-padding">
                        <label>Name</label>
                    </div>
                    <div class="col-sm-4 no-padding">
                        <label>Value</label>
                    </div>
                </div>
                <% _.each(env, function(e){ %>
                <div class="col-sm-12 no-padding fields">
                    <div class="col-sm-4 no-padding">
                        <input class="name change-input" type="text" value="<%- e.name ? e.name : '' %>" placeholder="eg. Variable_name">
                    </div>
                    <div class="col-sm-4 no-padding">
                        <input class="value change-input" type="text" value="<%- e.value ? e.value : '' %>" placeholder="eg. Some_value_0-9">
                    </div>
                    <div class="col-xs-1 no-padding">
                        <div class="remove-env"></div>
                    </div>
                </div>
                 <% }) %>
                <div class="col-sm-12 no-padding">
                    <button type="button" class="add-env">Add field</button>
                </div>
                <div class="col-sm-12 no-padding reset">
                    <button type="button" class="reset-button">Reset values</button>
                </div>
            <div>
        </div>
    </div>
    <div class="buttons pull-right">
        <button class="go-to-ports">Back</button>
        <button class="next-step">Next</button>
    </div>
<% } else { %>
    <div class="container">
        <div class="row title">
            <div class="col-md-4">
                <h4><%- image %></h4>
            </div>
            <div class="col-md-7">
                <ul class="nav nav-pills">
                    <li role="presentation"><span class="go-to-ports btn btn-info">Ports</span></li>
                    <li role="presentation"><span class="go-to-volumes btn btn-info">Volumes</span></li>
                    <li role="presentation"><span class="active btn btn-info">Envvars</span></li>
                    <li role="presentation"><span class="go-to-resources btn btn-info">Limits</span></li>
                    <li role="presentation"><span class="go-to-other btn btn-info">Other</span></li>
                    <li role="presentation"><span class="go-to-stats btn btn-info">Stats</span></li>
                    <li role="presentation"><span class="go-to-logs btn btn-info">Logs</span></li>
                </ul>
            </div>
        </div>
        <div>
            <table id="data-table" class="table">
                <thead><tr><th class="text-center">Key</th><th class="text-center">Value</th></tr></thead>
                <tbody>
                <% _.each(env, function(e){ %>
                    <tr>
                        <td class="text-center"><span class="ieditable name"><%- e.name ? e.name : 'not set' %></span></td>
                        <td class="text-center"><span class="ieditable value"><%- e.value ? e.value : 'not set' %></span></td>
                    </tr>
                <% }) %>
                </tbody>
            </table>
        </div>
        <div>
            <button type="button" class="add-env">Add</button>
        </div>
        <div class="view-controls text-right">
            <a class="btn btn-default" href="/#pods/<%- parentID %>">Back</a>
        </div>
    </div>
<% } %>
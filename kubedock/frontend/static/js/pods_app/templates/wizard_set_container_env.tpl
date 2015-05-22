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
<div id="container-page">
    <div class="breadcrumbs-wrapper">
        <div class="container breadcrumbs" id="breadcrumbs">
            <ul class="breadcrumb">
                <li>
                    <a href="/#pods">Pods</a>
                </li>
                <li>
                    <a href="/#pods/<%- parentID %>"><%- podName %></a>
                </li>
                <li class="active"><%- image %> (<%- name %>)</li>
            </ul>
        </div>
    </div>
    <div class="container">
        <div class="row">
            <div class="col-sm-3 col-md-2 sidebar">
                <ul class="nav nav-sidebar">
                    <li role="presentation" class="stats go-to-logs">Logs</li>
                    <li role="presentation" class="go-to-stats">Monitoring</li>
                    <!-- <li role="presentation" class="go-to-volumes">Timelines</li> -->
                    <li role="presentation" class="configuration active">Configuration
                        <ul class="nav sub-nav">
                            <li role="presentation" class="go-to-ports">General</li>
                            <li role="presentation" class="active">Variables</li>
                            <!-- <li role="presentation" class="go-to-resources">Limits</li> -->
                        </ul>
                    </li>
                </ul>
            </div>
            <div id="details_content" class="col-sm-10 no-padding configuration-general-tab">
                <div class="status-line <%- state_repr %>">Status: <%- state_repr %>
                    <% if (state_repr == "running"){ %>
                        <span id="stopContainer">Stop</span>
                    <% } else  if (state_repr == "stopped"){ %>
                        <span id="startContainer">Start</span>
                    <% } %>
                    <!-- <span>Terminate</span> -->
                    <!-- <span>Redeploy</span> -->
                </div>
                <div id="tab-content">
                    <div class="col-xs-10">
                        <div class="info col-xs-6">
                            <div>Image tag: <%- image %></div>
                            <div>Kube type: <%- kube_type.name %></div>
                            <div>Restart policy: <%- restart_policy %></div>
                            <div>Kube QTY: <%- kubes %></div>
                        </div>
                        <div class="col-xs-6 servers">
                            <div>CPU: <%- kube_type.cpu * kubes %> <%- kube_type.cpu_units %></div>
                            <div>RAM: <%- kube_type.memory * kubes %> <%- kube_type.memory_units %></div>
                            <div>HDD: <%- kube_type.disk_space * kubes %> <%- kube_type.disk_space_units %></div>
                        </div>
                    </div>
                    <div class="col-xs-12 no-padding">
                        <table id="data-table" class="table">
                            <thead>
                              <tr>
                                <th class="text-center">Name</th>
                                <th class="text-center">Value</th>
                              </tr>
                            </thead>
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
                </div>
            </div>
        </div>
    </div>
</div>
<% } %>
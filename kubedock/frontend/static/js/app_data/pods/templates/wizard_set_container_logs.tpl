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
            <div class="col-sm-12 col-md-2 sidebar">
                <ul class="nav nav-sidebar">
                    <li role="presentation" class="stats active">Logs</li>
                    <li role="presentation" class="monitoring go-to-stats">Monitoring</li>
                    <!-- <li role="presentation" class="go-to-volumes ">Timelines</li> -->
                    <li role="presentation" class="configuration go-to-ports">General</li>
                    <li role="presentation" class="variables go-to-envs">Variables</li>
                    <!-- <li role="presentation" class="go-to-resources">Limits</li> -->
<!--                     <li role="presentation" class="configuration">
                        <span class="go-to-ports">Configuration</span>
                        <ul class="nav sub-nav">
                        </ul>
                    </li> -->
                </ul>
            </div>
            <div id="details_content" class="col-md-10 col-sm-12 logs-tab no-padding">
                <div id="tab-content" class="col-md-12">
                    <div class="status-line">
                        <span class="icon <%- state %>">Status: <%- state %></span>
                        <% if (state == "running"){ %>
                            <span id="stopContainer" class="icon hover">Stop</span>
                            <% if (!updateIsAvailable) { %>
                                <span class="icon hover check-for-update" title="Check <%- image %> for updates">Check for updates</span>
                            <% } else { %>
                                <span class="icon hover container-update" title="Update <%- image %> container">Update</span>
                            <% } %>
                            <a class="icon hover upgrade-btn" href="#pods/<%- parentID %>/<%- name %>/upgrade"
                                    title="Change the amount of resources for <%- image %>">
                                Upgrade resources
                            </a>
                        <% } else  if (state == "stopped"){ %>
                            <span id="startContainer" class="icon hover">Start</span>
                        <% } %>
                        <% if (sourceUrl !== undefined) { %>
                            <a class="hover icon hidden-sm hidden-xs pull-right image-link" href="<%- /^https?:\/\//.test(sourceUrl) ? sourceUrl : 'http://' + sourceUrl %>" target="blank">Learn more about this image</a>
                        <% } %>
                    </div>
                    <div class="control-icons col-md-10 col-md-offset-2 col-sm-12">
                        <div class="col-md-6 col-md-offset-0 col-sm-10 col-sm-offset-2 col-xs-12 info">
                            <div>Image: <%- image %></div>
                            <div>Kube Type: <%- kube_type.name %></div>
                            <div>Restart policy: <%- restart_policy %></div>
                            <div class="editGroup">
                                Number of Kubes: <!-- <span class="editContainerKubes"> --><%- kubes %><!--</span>-->
                                <div class="editForm <%- editKubesQty === undefined ? 'hide' : '' %>">
                                    <input type="text" value="<%- kubeVal %>"/>
                                    <button class="cancel">Cancel</button>
                                    <button class="send">Apply</button>
                                </div>
                            </div>
                        </div>
                        <div class="col-md-6 col-md-offset-0 col-sm-10 col-sm-offset-2 col-xs-12 servers">
                            <div>CPU: <%= (kube_type.cpu * kubes).toFixed(2) %> <%- kube_type.cpu_units %></div>
                            <div>RAM: <%- kube_type.memory * kubes %> <%- kube_type.memory_units %></div>
                            <div>HDD: <%- kube_type.disk_space * kubes %> <%- kube_type.disk_space_units %> </div>
                        </div>
                    </div>
                    <div class="col-xs-12 no-padding ">

                    </div>
                    <div class="col-xs-12 no-padding container-logs-wrapper">
                        <a class="export-logs pull-right" title="Export container log to txt file" download="<%= parentID %>_<%= name %>_logs.txt" href="/api/logs/container/<%= parentID %>/<%= name %>?size=200&text=true">Export</a>
                        <div class="container-logs">
                            <% _.each(logs, function(serie){ %>
                                <p class="container-logs-started"><%- serie.start %>: Started</p>
                                <% _.each(serie.hits, function(line){ %>
                                    <p><%- line['@timestamp'] %>: <%- line.log %></p>
                                <% }) %>
                                <% if (serie.end) { %>
                                    <% if (serie.exit_code === -2) { %>
                                        <p class="container-logs-stopped"><%- serie.end %>: Pod was stopped</p>
                                    <% } else if (serie.exit_code === 0) { %>
                                        <p class="container-logs-succeeded"><%- serie.end %>: Exited successfully</p>
                                        <p class="container-logs-succeeded-reason"><%- serie.reason %></p>
                                    <% } else { %>
                                        <p class="container-logs-failed"><%- serie.end %>: Falied</p>
                                        <p class="container-logs-failed-reason"><%- serie.reason %></p>
                                    <% } %>
                                <% } %>
                            <% }) %>
                            <% if (logsError) { %>
                                <p><%- logsError %></p>
                            <% } %>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
</div>

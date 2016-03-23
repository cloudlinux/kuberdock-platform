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
    <div class="container container-stats">
        <div class="row">
            <div class="col-sm-12 col-md-2 sidebar">
                <ul class="nav nav-sidebar">
                    <li role="presentation" class="stats go-to-logs">Logs</li>
                    <li role="presentation" class="monitoring active">Monitoring</li>
                    <!-- <li role="presentation" class="go-to-volumes">Timelines</li> -->
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
            <div id="details_content" class="col-md-10 col-sm-12 monitoring-tab">
                <div id="tab-content">
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
                                    title="Change the amount of resources for <%- image %>">Upgrade resources
                            </a>
                        <% } else  if (state == "stopped"){ %>
                            <span id="startContainer" class="icon hover">Start</span>
                        <% } %>
                    </div>
                    <div class="control-icons col-md-10 col-md-offset-2 col-sm-12">
                        <div class="col-md-6 col-md-offset-0 col-sm-10 col-sm-offset-2 col-xs-12 info">
                            <div>Image: <%- image %></div>
                            <div>Kube Type: <%- kube_type.name %></div>
                            <div>Restart policy: <%- restart_policy %></div>
                            <div>Number of Kubes: <%- kubes %></div>
                        </div>
                        <div class="col-md-6 col-md-offset-0 col-sm-10 col-sm-offset-2 col-xs-12 servers">
                            <div>CPU: <%= (kube_type.cpu * kubes).toFixed(2) %> <%- kube_type.cpu_units %></div>
                            <div>RAM: <%- kube_type.memory * kubes %> <%- kube_type.memory_units %></div>
                            <div>HDD: <%- kube_type.disk_space * kubes %> <%- kube_type.disk_space_units %></div>
                        </div>
                    </div>
                    <!-- <div class="col-xs-12 page-top-menu border-top">
                        <span>Select replica:</span>
                        <label class="custom">
                            <input type="checkbox" checked="checked">
                            <span></span>Replica 1
                        </label>
                        <label class="custom">
                            <input type="checkbox">
                            <span></span>Replica 2
                        </label>
                        <label class="custom">
                            <input type="checkbox">
                            <span></span>Replica 3
                        </label>
                    </div> -->
                    <div id="monitoring-page" class="col-md-12 col-sm-12 col-xs-12 no-padding clearfix"></div>
                </div>
            </div>
        </div>
    </div>
</div>

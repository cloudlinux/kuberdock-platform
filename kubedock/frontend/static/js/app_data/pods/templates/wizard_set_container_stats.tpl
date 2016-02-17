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
            <div class="col-sm-3 col-md-2 sidebar">
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
                    </li>
                </ul> -->
            </div>
            <div id="details_content" class="col-xs-10 monitoring-tab no-padding">
                <div id="tab-content">
                    <div class="status-line <%- state %> curent-margin">Status: <%- state %>
                        <% if (state == "running"){ %>
                            <span id="stopContainer">Stop</span>
                            <!-- AC-1279 -->
                            <% if (!updateIsAvailable) { %>
                                <span class="check-for-update" title="Check <%- image %> for updates">Check for updates</span>
                            <% } else { %>
                                <span class="container-update" title="Update <%- image %> container">Update</span>
                            <% } %>
                        <% } else  if (state == "stopped"){ %>
                            <span id="startContainer">Start</span>
                        <% } %>
                        <!-- <span>Terminate</span> -->
                        <!-- <span>Redeploy</span> -->
                    </div>
                    <div class="col-xs-10">
                        <div class="info col-xs-6">
                            <div>Image: <%- image %></div>
                            <div>Kube Type: <%- kube_type.name %></div>
                            <div>Restart policy: <%- restart_policy %></div>
                            <div>Number of Kubes: <%- kubes %></div>
                        </div>
                        <div class="col-xs-6 servers">
                            <div>CPU: <%- (kube_type.cpu * kubes).toFixed(2) %> <%- kube_type.cpu_units %></div>
                            <div>RAM: <%- kube_type.memory * kubes %> <%- kube_type.memory_units %></div>
                            <div>HDD: <%- kube_type.disk_space * kubes %> <%- kube_type.disk_space_units %></div>
                        </div>
                    </div>
                    <div id="monitoring-page" class="col-sm-12 no-padding">
                        <!-- <div class="page-top-menu">
                            <span>Choose period:</span>
                            <span>Last 6 Hours</span>
                            <span class="active">24 Hours</span>
                            <span>1 week</span>
                            <span>1 month</span>
                            <span>1 year</span>
                        </div>
                        <div class="page-top-menu">
                            <span>Select replica:</span>
                            <span>
                                <label class="custom">
                                    <input type="checkbox">
                                    <span></span>
                                    Replica 1
                                </label>
                            </span>
                            <span>
                                <label class="custom">
                                    <input type="checkbox">
                                    <span></span>
                                    Replica 2
                                </label>
                            </span>
                        </div>
                        <p class="name first">CPU graph</p>
                        <div class="cpu-graph"></div>
                        <p class="name">Memory graph</p>
                        <div class="memory-graph"></div>
                        <p class="name">Bandwith IN/OUT graph</p>
                        <div class="bandwith-graph"></div> -->
                    </div>
                </div>
            </div>
        </div>
    </div>
</div>

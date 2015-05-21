<div id="container-page">
    <div class="breadcrumbs-wrapper">
        <div class="container breadcrumbs" id="breadcrumbs">
            <ul class="breadcrumb">
                <li>
                    <a href="/#pods">Pods</a>
                </li>
                <li>
                    <a href="/#pods/<%- parentID %>">My best Pod</a>
                </li>
                <li class="active">Container name</li>
            </ul>
        </div>
    </div>
    <div class="container container-stats">
        <div class="row">
            <div class="col-sm-3 col-md-2 sidebar">
                <ul class="nav nav-sidebar">
                    <li role="presentation" class="stats go-to-logs">Logs</li>
                    <li role="presentation" class="active">Monitoring</li>
                    <!-- <li role="presentation" class="go-to-volumes">Timelines</li> -->
                    <li role="presentation" class="configuration">
                        <span class="go-to-ports">Configuration</span>
                        <ul class="nav sub-nav">
                            <li role="presentation" class="go-to-ports">General</li>
                            <li role="presentation" class="go-to-other">Variables</li>
                            <!-- <li role="presentation" class="go-to-resources">Limits</li> -->
                        </ul>
                    </li>
                </ul>
            </div>
            <div id="details_content" class="col-xs-10 monitoring-tab no-padding">
                <div id="tab-content">
                    <div class="status-line <%- state_repr %> curent-margin">Status: <%- state_repr %>
                        <% if (state_repr == "running"){ %>
                            <span id="stopContainer">Stop</span>
                        <% } else  if (state_repr == "stopped"){ %>
                            <span id="startContainer">Start</span>
                        <% } %>
                        <!-- <span>Terminate</span> -->
                        <!-- <span>Redeploy</span> -->
                    </div>
                    <div class="col-xs-10">
                        <div class="info col-xs-6">
                            <div>Image tag: <%- image %></div>
                            <!-- <div>Deploy tags: some tags</div> -->
                        </div>
                        <div class="col-xs-6 servers">
                            <div>Kube type: ssd power</div>
                            <div>Restart police: never</div>
                            <div>Pod IP:  102.128.9.95</div>
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
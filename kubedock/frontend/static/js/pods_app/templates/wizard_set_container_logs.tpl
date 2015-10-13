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
                    <li role="presentation" class="stats active">Logs</li>
                    <li role="presentation" class="go-to-stats">Monitoring</li>
                    <!-- <li role="presentation" class="go-to-volumes ">Timelines</li> -->
                    <li role="presentation" class="go-to-ports configuration">General</li>
                    <li role="presentation" class="go-to-envs">Variables</li>
                    <!-- <li role="presentation" class="go-to-resources">Limits</li> -->
<!--                     <li role="presentation" class="configuration">
                        <span class="go-to-ports">Configuration</span>
                        <ul class="nav sub-nav">
                        </ul>
                    </li> -->
                </ul>
            </div>
            <div id="details_content" class="col-xs-10 logs-tab no-padding">
                <div id="tab-content">
                    <div class="status-line <%- state %> curent-margin">Status: <%- state %>
                        <% if (state == "running"){ %>
                            <span id="stopContainer">Stop</span>
                        <% } else  if (state == "stopped"){ %>
                            <span id="startContainer">Start</span>
                        <% } %>
                        <!-- <span>Terminate</span> -->
                        <!-- <span>Redeploy</span> -->
                        <a class="pull-right image-link" href="<%- /^https?:\/\//.test(sourceUrl) ? sourceUrl : 'http://' + sourceUrl %>" target="blank">Learn more about this image</a>
                    </div>
                    <div class="col-xs-10">
                        <div class="info col-xs-6">
                            <div>Image tag: <%- image %></div>
                            <div>Kube type: <%- kube_type.name %></div>
                            <div>Restart policy: <%- restart_policy %></div>
                            <div>Kubes: <%- kubes %></div>
                        </div>
                        <div class="col-xs-6 servers">
                            <div>CPU: <%- kube_type.cpu * kubes %> <%- kube_type.cpu_units %></div>
                            <div>RAM: <%- kube_type.memory * kubes %> <%- kube_type.memory_units %></div>
                            <div>HDD: <%- kube_type.disk_space * kubes %> <%- kube_type.disk_space_units %> </div>
                        </div>
                    </div>
                    <div class="col-xs-12 no-padding container-logs-wrapper">
                        <div class="container-logs">
                            <% _.each(logs, function(line){ %>
                            <p><%- line['@timestamp'] %>: <%- line['log'] %></p>
                            <% }) %>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
</div>
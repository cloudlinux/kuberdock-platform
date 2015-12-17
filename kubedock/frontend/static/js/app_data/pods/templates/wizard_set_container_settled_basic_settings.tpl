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
                <li role="presentation" class="monitoring go-to-stats">Monitoring</li>
                <!-- <li role="presentation" class="go-to-volumes">Timelines</li> -->
                <li role="presentation" class="configuration active">General</li>
                <li role="presentation" class="variables go-to-envs">Variables</li>
                <!-- <li role="presentation" class="go-to-resources">Limits</li> -->
<!--                     <li role="presentation" class="configuration active">Configuration
                    <ul class="nav sub-nav">
                    </ul>
                </li> -->
            </ul>
        </div>
        <div id="details_content" class="col-sm-10 no-padding configuration-general-tab">
            <div class="status-line <%- state %>">Status: <%- state %>
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
                <% if (sourceUrl !== undefined) { %>
                    <a class="pull-right image-link" href="<%- /^https?:\/\//.test(sourceUrl) ? sourceUrl : 'http://' + sourceUrl %>" target="blank">Learn more about this image</a>
                <% } %>
            </div>
            <div id="tab-content">
                <div class="col-xs-10">
                    <div class="info col-xs-6">
                        <div>Image: <%- image %></div>
                        <div>Kube type: <%- kube_type.name %></div>
                        <div>Restart policy: <%- restart_policy %></div>
                        <div>Kubes: <%- kubes %></div>
                    </div>
                    <div class="col-xs-6 servers">
                        <div>CPU: <%- kube_type.cpu * kubes %> <%- kube_type.cpu_units %></div>
                        <div>RAM: <%- kube_type.memory * kubes %> <%- kube_type.memory_units %></div>
                        <div>HDD: <%- kube_type.disk_space * kubes %> <%- kube_type.disk_space_units %></div>
                    </div>
                </div>
                <div class="col-xs-12 no-padding">
                    <label>Ports:</label>
                    <table id="ports-table" class="table">
                        <thead>
                            <tr>
                                <th>Container port</th>
                                <th>Protocol</th>
                                <th>Pod port</th>
                                <th>Public</th>
                            </tr>
                        </thead>
                        <tbody>
                        <% if (ports.length != 0) { %>
                            <% _.each(ports, function(p){ %>
                                <tr>
                                    <td class="containerPort"><%- p.containerPort ? p.containerPort : 'none'%></td>
                                    <td class="containerProtocol"><%- p.protocol ? p.protocol : 'none' %></td>
                                    <td class="hostPort"><%- p.hostPort ? p.hostPort : p.containerPort%></td>
                                    <td><%- p.isPublic ? 'yes' : 'no' %></td>
                                </tr>
                            <% }) %>
                        <% } else { %>
                            <tr>
                                <td colspan="4" class="text-center disabled-color-text">Ports are not specified</td>
                            </tr>
                        <% } %>
                        </tbody>
                    </table>
                    <div class="volumes">
                        <label>Volumes:</label>
                        <div class="row">
                            <div class="col-xs-12">
                                <table class="table" id="volumes-table">
                                    <thead>
                                        <tr>
                                            <th>Container path</th>
                                            <th>Persistent</th>
                                            <th>Name</th>
                                            <th>GB</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                    <% if (volumes.length != 0) { %>
                                        <% _.each(volumes, function(v){ %>
                                            <tr>
                                                <td><%- v.mountPath %></td>
                                            <% if(v.persistentDisk) { %>
                                                <td>yes</td>
                                                <td><%- v.persistentDisk.pdName %></td>
                                                <td><%- v.persistentDisk.pdSize %></td>
                                            <% } else { %>
                                                <td>no</td>
                                                <td></td>
                                                <td></td>
                                            </tr>
                                        <% }}) %>
                                    <% } else { %>
                                        <tr>
                                            <td colspan="4" class="text-center disabled-color-text">Volumes are not specified</td>
                                        </tr>
                                    <% } %>
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
</div>

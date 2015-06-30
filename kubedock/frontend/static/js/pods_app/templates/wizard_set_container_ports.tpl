<% if (isPending) { %>
<div id="add-image" class="container">
    <div class="col-md-3 sidebar">
        <ul class="nav nav-sidebar">
            <li role="presentation" class="success">Choose image</li>
            <li role="presentation" class="active">Set up image</li>
            <li role="presentation">Environment variables</li>
            <li role="presentation">Final</li>
        </ul>
    </div>
    <div id="details_content" class="col-sm-9 set-up-image no-padding">
        <div id="tab-content">
            <label>Adding: <%- image %></label>
            <!-- <label class="custom">
                <input type="checkbox"/>
                <span></span>
                On autoterminate
            </label> -->
            <div class="entrypoint">
                <label>Entrypoint:</label>
                <div class="row fields">
                    <div class="col-xs-6">
                        <input class="command" type="text" value="" placeholder="command to start">
                    </div>
                </div>
            </div>
            <div class="ports">
                <label>Ports:</label>
                <div class="row">
                    <div class="col-xs-10">
                        <table id="ports-table" class="table">
                            <thead><tr><th>Container port</th><th>Protocol</th><th>Pod port</th><th>Public</th></tr></thead>
                            <tbody>
                            <% if (ports.length != 0){ %>
                                <% _.each(ports, function(p){ %>
                                    <tr>
                                        <td class="containerPort">
                                            <span class="ieditable"><%- p.containerPort %></span>
                                        </td>
                                        <td><span class="iseditable"><%- p.protocol %></span></td>
                                        <td class="hostPort"><span class="ieditable"><%- p.hostPort %></span></td>
                                        <td class="public">
                                            <label class="custom">
                                                <% if (p.isPublic){ %>
                                                <input class="public" checked type="checkbox"/>
                                                <% } else { %>
                                                <input class="public" type="checkbox"/>
                                                <% } %>
                                                <span></span>
                                            </label>
                                            <span class="remove-port pull-right"></span>
                                        </td>
                                    </tr>
                                <% }) %>
                            <% } else { %>
                                 <tr>
                                    <td colspan="4" class="text-center">To add port click on a button below</td>
                                </tr>
                            <% } %>
                            </tbody>
                        </table>
                        <div>
                            <button type="button" class="add-port">Add port</button>
                        </div>
                        <div class="col-xs-12 no-padding"></div>
                    </div>
                </div>
            </div>
            <div class="volumes">
                <label>Volumes:</label>
                <div class="row">
                    <div class="col-xs-10">
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
                            <% if (volumeMounts.length != 0){ %>
                                <% _.each(volumeMounts, function(v){ %>
                                    <tr>
                                        <td>
                                            <span class="ieditable mountPath">
                                                <%- v.mountPath %>
                                            </span>
                                        </td>
                                        <% if (v.isPersistent){ %>
                                        <td>
                                            <label class="custom">
                                                <input class="persistent" checked type="checkbox"/>
                                                <span></span>
                                            </label>
                                            <% if (showPersistentAdd){ %>
                                                <div class="tooltip-wrapper">
                                                    <span>
                                                        <input type="text" class="pd-name" placeholder="persistent-drive-name">
                                                    </span>
                                                    <span>
                                                        <input type="text" class="pd-size" placeholder="persistent-drive-size">
                                                    </span>
                                                    <span>
                                                        <button class="add-drive" title="Add new drive">add</button>
                                                        <span class="add-drive-cancel"></span>
                                                   </span>
                                                </div>
                                            <% } %>
                                        </td>
                                        <td>
                                            <% if (hasPersistent){ %>
                                                <span class="iveditable mountPath"><%- v.persistentDisk.pdName %></span>
                                                <% if (!showPersistentAdd){ %>
                                                    <span class="add-drive" title="Add new drive"></span>
                                                <% } %>
                                            <% } else { %>
                                                <span>No drives found</span>
                                            <% } %>
                                        </td>
                                        <td>
                                            <span class="remove-volume pull-right"></span>
                                        </td>
                                        <% } else { %>
                                        <td>
                                            <label class="custom">
                                                <input class="persistent" type="checkbox"/>
                                                <span></span>
                                            </label>
                                        </td>
                                        <td></td>
                                        <td>
                                            <span class="remove-volume pull-right"></span>
                                        </td>
                                        <% } %>
                                    </tr>
                                <% }) %>
                            <% } else { %>
                                <tr>
                                    <td colspan="4" class="text-center">To add volume click on a button below</td>
                                </tr>
                            <% } %>
                            </tbody>
                        </table>
                        <div>
                            <button type="button" class="add-volume">Add volume</button>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
    <div class="col-xs-9 no-padding col-xs-offset-3">
        <span class="description pull-left">
            * Public IP will require additional payment
        </span>
        <span class="buttons pull-right">
            <a href="/#pods" class="">Cancel</a>
            <button class="next-step">Next</button>
        </span>
    </div>
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
                    <li role="presentation" class="configuration active">General</li>
                    <li role="presentation" class="go-to-envs">Variables</li>
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
                    <% } else  if (state == "stopped"){ %>
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
                        <table id="ports-table" class="table">
                            <thead><tr><th>Container port</th><th>Protocol</th><th>Pod port</th><th>Published</th></tr></thead>
                            <tbody>
                            <% if (ports.length != 0) { %>
                                <% _.each(ports, function(p){ %>
                                    <tr>
                                        <td class="containerPort"><%- p.containerPort ? p.containerPort : 'none'%></td>
                                        <td class="containerProtocol"><%- p.protocol ? p.protocol : 'none' %></td>
                                        <td class="hostPort"><%- p.hostPort ? p.hostPort : 'none'%></td>
                                        <td>
                                            yes
                                        </td>
                                    </tr>
                                <% }) %>
                            <% } else { %>
                                <tr>
                                    <td colspan="4" class="text-center">Ports not specified</td>
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
                                            </tr>
                                        </thead>
                                        <tbody>
                                        <% if (volumeMounts.length != 0) { %>
                                            <% _.each(volumeMounts, function(v){ %>
                                                <tr>
                                                    <td>
                                                        <span>
                                                            <%- v.mountPath %>
                                                        </span>
                                                    </td>
                                                    <% if (v.readOnly){ %>
                                                    <td>
                                                        no
                                                        <!-- <label class="custom">
                                                            <input checked type="checkbox"/>
                                                            <span></span>
                                                        </label> -->
                                                    </td>
                                                    <% } else { %>
                                                    <td>
                                                        yes
                                                        <!-- <label class="custom">
                                                            <input type="checkbox"/>
                                                            <span></span>
                                                        </label> -->
                                                    </td>
                                                    <% } %>
                                                </tr>
                                            <% }) %>
                                            <% } else { %>
                                                <tr>
                                                    <td colspan="2" class="text-center">Volumes not specified</td>
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
</div>
<% } %>

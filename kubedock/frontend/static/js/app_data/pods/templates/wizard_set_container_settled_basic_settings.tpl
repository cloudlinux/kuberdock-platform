<div class="container">
    <div class="row">
        <div class="col-sm-12 col-md-2 sidebar">
            <ul class="nav nav-sidebar">
                <li role="presentation" class="stats go-to-logs">Logs</li>
                <li role="presentation" class="monitoring go-to-stats">Monitoring</li>
                <li role="presentation" class="configuration active">General</li>
                <li role="presentation" class="variables go-to-envs">Variables</li>
            </ul>
        </div>
        <div id="details_content" class="col-md-10 col-sm-12 configuration-general-tab">
            <div id="tab-content">
                <div class="status-line">
                    <span class="icon <%- state %>"><span>Status: <%- state %></span></span>
                    <% if (state == "running"){ %>
                        <span id="stopContainer"><span>Stop</span></span>
                        <% if (!updateIsAvailable) { %>
                            <span class="check-for-update" title="Check <%- image %> for updates"><span>Check for updates</span></span>
                        <% } else { %>
                            <span class="container-update" title="Update <%- image %> container"><span>Update</span></span>
                        <% } %>
                        <a class="upgrade-btn" href="#pods/<%- parentID %>/<%- name %>/upgrade"
                                title="Change the amount of resources for <%- image %>"><span>Upgrade resources</span></a>
                    <% } else  if (state == "stopped"){ %>
                        <span id="startContainer"><span>Start</span></span>
                    <% } %>
                    <% if (sourceUrl !== undefined) { %>
                        <a class="hidden-sm hidden-xs pull-right image-link" href="<%- /^https?:\/\//.test(sourceUrl) ? sourceUrl : 'http://' + sourceUrl %>" target="blank"><span>Learn more about this image</span></a>
                    <% } %>
                </div>
                <div class="control-icons col-md-10 col-md-offset-2 col-sm-12">
                    <div class="col-md-6 col-md-offset-0 col-sm-10 col-sm-offset-2 col-xs-12 info">
                        <div>Image: <%- image %></div>
                        <div>Kube Type: <%- kube_type.get('name') %></div>
                        <div>Restart policy: <%- restart_policy %></div>
                        <div>Number of Kubes: <%- kubes %></div>
                    </div>
                    <div class="col-md-6 col-md-offset-0 col-sm-10 col-sm-offset-2 col-xs-12 servers">
                        <div>CPU: <%- limits.cpu %></div>
                        <div>RAM: <%- limits.ram %></div>
                        <div>HDD: <%- limits.hdd %></div>
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
                        <% if (ports && ports.length != 0) { %>
                            <% _.each(ports, function(p){ %>
                                <tr>
                                    <td class="containerPort"><%- p.containerPort || 'none'%></td>
                                    <td class="containerProtocol"><%- p.protocol || 'none' %></td>
                                    <td class="hostPort"><%- p.hostPort || p.containerPort || 'none' %></td>
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
                                    <% if (volumeMounts && volumeMounts.length != 0) { %>
                                        <% _.each(volumeMounts, function(vm){ %>
                                            <tr>
                                                <td><%- vm.mountPath %></td>
                                            <% var volume = _.findWhere(volumes, {name: vm.name}) %>
                                            <% if(volume.persistentDisk) { %>
                                                <td>yes</td>
                                                <td><%- volume.persistentDisk.pdName %></td>
                                                <td><%- volume.persistentDisk.pdSize || '' %></td>
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

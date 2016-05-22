<div id="container-page">
    <div class="container">
        <div class="row">
            <div class="col-sm-12 col-md-2 sidebar">
                <ul class="nav nav-sidebar">
                    <li role="presentation" class="stats go-to-logs">Logs</li>
                    <li role="presentation" class="go-to-stats monitoring">Monitoring</li>
                    <li role="presentation" class="configuration go-to-ports">General</li>
                    <li role="presentation" class="variables active">Variables</li>
                </ul>
            </div>
            <div id="details_content" class="col-md-10 col-sm-12 variables-tab">
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
                            <a class="upgrade-btn" href="#pods/<%- parentID %>/container/<%- name %>/upgrade"
                                    title="Change the amount of resources for <%- image %>"><span>Upgrade resources</span></a>
                        <% } else  if (state == "stopped"){ %>
                            <span id="startContainer"><span>Start</span></span>
                        <% } %>
                        <% if (sourceUrl !== undefined) { %>
                            <a class="hidden-sm hidden-xs pull-right image-link" href="<%- /^https?:\/\//.test(sourceUrl) ? sourceUrl : 'http://' + sourceUrl %>" target="blank"><span>Learn more about variables for this image</span></a>
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
                    <div class="col-md-12 col-sm-12 col-xs-12 no-padding clearfix">
                        <table id="data-table" class="table env-table" >
                            <thead>
                              <tr>
                                <th class="col-xs-4">Name</th>
                                <th class="col-xs-8">Value</th>
                              </tr>
                            </thead>
                            <tbody>
                            <% if (env.length != 0) { %>
                                <% _.each(env, function(e){ %>
                                  <tr>
                                    <td><span class="name"><%- e.name ? e.name : 'not set' %></span></td>
                                    <td><span class="value"><%- e.value ? e.value : 'not set' %></span></td>
                                  </tr>
                                <% }) %>
                            <% } else { %>
                                <tr>
                                    <td colspan="2" class="text-center disabled-color-text">Variables are not specified</td>
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

<div class="container">
    <div class="row">
        <div class="col-sm-12 col-md-2 sidebar">
            <ul class="nav nav-sidebar">
                <% if (before){ %>
                    <li role="presentation" class="stats go-to-logs"><span>Logs</span></li>
                    <li role="presentation" class="monitoring go-to-stats"><span>Monitoring</span></li>
                <% } %>
                <li role="presentation" class="configuration active"><span>General</span></li>
                <li role="presentation" class="variables go-to-envs"><span>Variables</span></li>
            </ul>
        </div>
        <div id="details_content" class="col-md-10 col-sm-12 configuration-general-tab">
            <div id="tab-content">
                <div class="status-line">
                    <span class="icon status <%- state %>"><span>Status: <%- state %></span></span>
                    <% if (state == "running"){ %>
                        <span id="stopContainer"><span>Stop</span></span>
                        <% if (!updateIsAvailable) { %>
                            <span class="check-for-update" title="Check <%- image %> for updates"><span>Check for updates</span></span>
                        <% } else { %>
                            <span class="container-update" title="Update <%- image %> container"><span>Update</span></span>
                        <% } %>
                        <a class="upgrade-btn" href="#pods/<%- podID %>/container/<%- id %>/upgrade"
                                title="Change the amount of resources for <%- image %>"><span>Upgrade resources</span></a>
                    <% } else  if (state == "stopped"){ %>
                        <span id="startContainer"><span>Start</span></span>
                    <% } %>
                    <a class="edit-container-general" href="#pods/<%- podID %>/container/<%- id %>/edit/general"><span>Edit</span></a>
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
                    <div class="ports-table-wrapper"></div>
                    <div class="volumes">
                        <div class="row">
                            <div class="col-xs-12"></div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
</div>

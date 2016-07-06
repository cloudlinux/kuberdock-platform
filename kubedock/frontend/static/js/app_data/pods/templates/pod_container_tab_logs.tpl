<div id="container-page">
    <div class="container">
        <div class="row">
            <div class="col-sm-12 col-md-2 sidebar">
                <ul class="nav nav-sidebar">
                    <li role="presentation" class="stats active"><span>Logs</span></li>
                    <li role="presentation" class="monitoring go-to-stats"><span>Monitoring</span></li>
                    <!-- <li role="presentation" class="go-to-volumes ">Timelines</li> -->
                    <li role="presentation" class="configuration go-to-ports"><span>General</span></li>
                    <li role="presentation" class="variables go-to-envs"><span>Variables</span></li>
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
                        <span class="icon status <%- state %>"><span>Status: <%- state %></span></span>
                        <% if (state == "running"){ %>
                            <span id="stopContainer"><span>Stop</span></span>
                            <% if (!updateIsAvailable) { %>
                                <span class="check-for-update" title="Check <%- image %> for updates"><span>Check for updates</span></span>
                            <% } else { %>
                                <span class="container-update" title="Update <%- image %> container"><span>Update</span></span>
                            <% } %>
                            <a class="upgrade-btn" href="#pods/<%- parentID %>/container/<%- id %>/upgrade"
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
                            <div>CPU: <%- limits.cpu %></div>
                            <div>RAM: <%- limits.ram %></div>
                            <div>HDD: <%- limits.hdd %></div>
                        </div>
                    </div>
                    <div class="col-xs-12 page-top-menu border-top">
<!--                         <span>Select replica:</span>
                        <label class="custom">
                            <input type="radio" name="replica" checked="checked">
                            <span></span>Replica 1
                        </label>
                        <label class="custom">
                            <input type="radio" name="replica">
                            <span></span>Replica 2
                        </label>
                        <label class="custom">
                            <input type="radio" name="replica">
                            <span></span>Replica 3
                        </label> -->
                        <a class="export-logs pull-right" title="Export container log to txt file" download="<%= parentID %>_<%= name %>_logs.txt" href="/api/logs/container/<%= parentID %>/<%= name %>?size=200&text=true">Export</a>
                    </div>
                    <div class="col-xs-12 no-padding container-logs-wrapper">
                        <div class="container-logs">
                            <% _.each(logs, function(serie){ %>
                                <p class="container-logs-started"><time><%- serie.start %>:</time> Started</p>
                                <% _.each(serie.hits, function(line){ %>
                                    <p><time><%- line['@timestamp'] %>:</time> <%- line.log %></p>
                                <% }) %>
                                <% if (serie.end) { %>
                                    <% if (serie.exit_code === -2) { %>
                                        <p class="container-logs-stopped"><time><%- serie.end %>:</time> Pod was stopped</p>
                                    <% } else if (serie.exit_code === 0) { %>
                                        <p class="container-logs-succeeded"><time><%- serie.end %>:</time> Exited successfully</p>
                                        <p class="container-logs-succeeded-reason"><%- serie.reason %></p>
                                    <% } else { %>
                                        <p class="container-logs-failed"><time><%- serie.end %>:</time> Falied</p>
                                        <p class="container-logs-failed-reason"><%- serie.reason %></p>
                                    <% } %>
                                <% } %>
                            <% }) %>
                            <% if (logsError) { %>
                                <p><%- logsError %></p>
                            <% } %>
                        </div>
                    </div>
                    <p class="logs-description col-xs-12  no-padding">All detailed logs of container and pod would be available in few minutes after start.</p>
                </div>
            </div>
        </div>
    </div>
</div>

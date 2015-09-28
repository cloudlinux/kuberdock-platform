<div class="col-md-3 sidebar">
    <ul class="nav nav-sidebar">
        <li role="presentation" class="success">Choose image</li>
        <li role="presentation" class="active">Set up image</li>
        <li role="presentation">Environment variables</li>
        <li role="presentation">Final setup</li>
    </ul>
</div>
<div id="details_content" class="col-sm-9 set-up-image no-padding">
    <div id="tab-content">
        <div class="image-name-wrapper"><%- image %></div>
        <div class="entrypoint">
            <label>Command:</label>
            <div class="row fields">
                <div class="col-xs-6">
                    <input class="command" type="text" value="" placeholder="command to start">
                </div>
            </div>
        </div>
        <div class="ports">
            <label>Ports:</label>
            <div class="row">
                <div class="col-xs-12">
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
                                <td colspan="4" class="text-center disabled-color-text">To add port click on a button below</td>
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
                <div class="col-xs-12">
                    <table class="table" id="volumes-table">
                        <thead>
                            <tr><th>Container path</th><th>Persistent</th><th>Name</th><th>GB</th></tr>
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
                                                    <button class="add-drive" title="Add new drive">Add</button>
                                                    <span class="add-drive-cancel"></span>
                                               </span>
                                            </div>
                                        <% } %>
                                    </td>
                                    <td>
                                        <% if (hasPersistent){ %>
                                            <span class="iveditable mountPath"><%- v.persistentDisk.pdName ? v.persistentDisk.pdName : 'none' %></span>
                                            <% if (!showPersistentAdd){ %>
                                                <span class="add-drive" title="Add new drive"></span>
                                            <% } %>
                                        <% } else { %>
                                            <span>No drives found</span>
                                        <% } %>
                                    </td>
                                    <td>
                                        <% if (hasPersistent){ %>
                                            <%= v.persistentDisk.pdSize ? v.persistentDisk.pdSize : 'none' %>
                                        <% } else { %>
                                            none
                                        <% } %>
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
                                <td colspan="4" class="text-center disabled-color-text">To add volume click on a button below</td>
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
    <span class="description pull-left">* Public IP will require additional payment</span>
    <span class="buttons pull-right">
        <button class="prev-step">Back</button>
        <button class="next-step">Next</button>
    </span>
</div>
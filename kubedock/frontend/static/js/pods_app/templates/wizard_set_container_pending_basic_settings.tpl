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
        <div class="image-name-wrapper">
            <%- image %>
            <% if (sourceUrl !== undefined) { %>
                <a class="pull-right image-link" href="<%- /^https?:\/\//.test(sourceUrl) ? sourceUrl : 'http://' + sourceUrl %>" target="blank">Learn more about this image</a>
            <% } %>
        </div>
        <div class="entrypoint">
            <label>Command:</label>
            <div class="row fields">
                <div class="col-xs-6">
                    <input class="command" type="text" value="" placeholder="Сommand to start">
                </div>
            </div>
        </div>
        <div class="ports">
            <label>Ports:</label>
            <div class="row">
                <div class="col-xs-12">
                    <table id="ports-table" class="table">
                        <thead>
                            <tr>
                                <th class="col-md-3">Container port</th>
                                <th class="col-md-3">Protocol</th>
                                <th class="col-md-2">Pod port</th>
                                <th class="col-md-2" title="Public IP will require additional payment">Public <sup>*</sup></th>
                                <th class="col-md-2">Actions</th>
                            </tr>
                        </thead>
                        <tbody>
                        <% if (ports.length != 0){ %>
                            <% _.each(ports, function(p){ %>
                                <tr>
                                    <td class="containerPort">
                                        <span class="ieditable"><%- p.containerPort %></span>
                                    </td>
                                    <td class="containerProtocol"><span class="iseditable"><%- p.protocol %></span></td>
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
                                    </td>
                                    <td class="actions">
                                        <span class="remove-port"></span>
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
                    <% var persistantLength = 0;
                        if (volumeEntries.length != 0){
                            _.each(volumeEntries, function(v){
                                if (v.isPersistent){
                                    persistantLength++;
                                }
                            })
                        }
                    %>
                    <table class="table" id="volumes-table">
                        <thead>
                            <tr>
                                <th class="col-md-4">Container path</th>
                                <th class="col-md-2">Persistent</th>
                                <% if (persistantLength !== 0) { %>
                                    <th class="col-md-2">Name</th>
                                    <th class="col-md-2">GB</th>
                                <% } else { %>
                                    <th class="col-md-2"></th>
                                    <th class="col-md-2"></th>
                                <% } %>
                                <th class="col-md-2">Actions</th>
                            </tr>
                        </thead>
                        <tbody>
                        <% if (volumeEntries.length !== 0){ %>
                            <% _.each(volumeEntries, function(v){ %>
                                <tr>
                                    <td>
                                        <span class="ieditable mountPath"><%- v.mountPath %></span>
                                    </td>
                                    <% if (v.isPersistent){ %>
                                        <td>
                                            <label class="custom">
                                                <input class="persistent" checked type="checkbox"/>
                                                <span></span>
                                            </label>
                                        </td>
                                        <td>
                                            <% if (hasPersistent){ %>
                                                <% if (showPersistentAdd && showPersistentAdd === v.name){ %>
                                                    <div class="input-wrap">
                                                        <input type="text" class="pd-name" placeholder="Name">
                                                    </div>
                                                <% } else { %>
                                                    <% if (v.persistentDisk.pdName) {%>
                                                        <span class="iveditable pdName">
                                                            <%- v.persistentDisk.pdName %>
                                                            <span class="caret"></span>
                                                        </span>
                                                    <% } else { %>
                                                        none
                                                    <% } %>
                                                <% } %>
                                            <% } else { %>
                                                <span>No drives found</span>
                                            <% } %>
                                        </td>
                                        <td>
                                            <% if (hasPersistent){ %>
                                                <% if (showPersistentAdd && showPersistentAdd === v.name){ %>
                                                    <div class="input-wrap">
                                                        <input type="text" class="pd-size" placeholder="Size">
                                                    </div>
                                                <% } else { %>
                                                    <%= v.persistentDisk.pdSize ? v.persistentDisk.pdSize : 'none' %>
                                                <% } %>
                                            <% } else { %>
                                                none
                                            <% } %>
                                        </td>
                                        <td class="actions">
                                            <% if (hasPersistent){ %>
                                                <% if (!showPersistentAdd){ %>
                                                    <span class="add-drive" title="Add new drive"></span>
                                                    <span class="remove-volume"></span>
                                                <% } %>
                                                <% if (showPersistentAdd && showPersistentAdd === v.name){ %>
                                                    <span class="add-drive" title="Add this drive">Add</span>
                                                    <span class="add-drive-cancel" title="Cancel">>Cancel</span>
                                                <% } %>
                                            <% } %>
                                        </td>
                                    <% } else { %>
                                    <td>
                                        <label class="custom">
                                            <input class="persistent" type="checkbox"/>
                                            <span></span>
                                        </label>
                                    </td>
                                    <td></td>
                                    <td></td>
                                     <td>
                                        <span class="remove-volume"></span>
                                    </td>
                                    <% } %>
                                </tr>
                            <% }) %>
                        <% } else { %>
                            <tr>
                                <td colspan="5" class="text-center disabled-color-text">To add volume click on a button below</td>
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
        <button class="prev-step gray">Back</button>
        <button class="next-step">Next</button>
    </span>
</div>

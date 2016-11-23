<div class="container create-app">
    <div class="row">
        <div class="col-sm-3 col-md-2 sidebar">
            <img src="<%- icon %>" alt="PA icon" class="pa-img img-responsive <%- icon ? '' : 'empty'%>">
            <input type="file" id="icon">
            <label class="add-icon" for="icon"><span>Add icon</span></label>
            <label class="edit-icon" for="icon"><span>Edit icon</span></label>
            <div class="remove-icon"><span>Remove icon</span></div>
        </div>
        <div class="col-md-10 col-sm-9">
            <div>
                <label for="app-name">App name</label>
                <input type="text" id="app-name" placeholder="Enter app name" value="<%= name %>">
                <input type="hidden" id="app-origin" value="<%= origin %>">
            </div>
            <label class="upload" for="app-upload">Upload yaml
                <input type="file" id="app-upload">
            </label>
            <label class="custom visible-for-users">
                <input class="visible" type="checkbox" value="true" <%- search_available ? 'checked': ''%>>
                <span></span>
                <span>Visible for users</span>
            </label>
            <div class="app-wrapper <%= errorData ? 'error' : '' %> ">
                <% if (errorData) { %>
                    <div class="accordion" id="accordion2">
                        <div class="accordion-group">
                            <div class="accordion-heading text-center">
                                <span>We found problems with YAML specification</span>
                                <a class="accordion-toggle pull-right" data-toggle="collapse" data-parent="#accordion2" href="#collapseOne">
                                    <span class="title"></span>
                                </a>
                            </div>
                            <div id="collapseOne" class="accordion-body collapse in">
                                <div class="accordion-inner">
                                    <% var forceArray = function(msg){ return _.isArray(msg) ? msg : [msg]; } %>
                                    <% if (errorData.common) { %>
                                        <p><%- jsyaml.safeDump(forceArray(errorData.common)) %></p>
                                    <% } if (errorData.customFields) { %>
                                        <h5>Invalid custom variables:</h5>
                                        <p><%- jsyaml.safeDump(forceArray(errorData.customFields)) %></p>
                                    <% } if (errorData.schema) { %>
                                        <h5>Invalid schema:</h5>
                                        <p><%- jsyaml.safeDump(forceArray(errorData.schema)) %></p>
                                    <% } if (errorData.appPackages) { %>
                                        <h5>Invalid packages:</h5>
                                        <p><%- jsyaml.safeDump(forceArray(errorData.appPackages)) %></p>
                                    <% } if (!(errorData.common || errorData.customFields || errorData.schema || errorData.appPackages)) { %>
                                        <h5>Invalid template:</h5>
                                        <p><%- jsyaml.safeDump(errorData) %></p>
                                    <% } %>
                                </div>
                            </div>
                        </div>
                    </div>
                <% } %>
                <div class="yaml-textarea-wrapper"></div>
            </div>
            <div class="more-info">
                <div>You can specify custom fields to let user fill it or to be generated automatically while starting an application if you need.<br>
                    More information on <a href="http://docs.kuberdock.com/index.html?predefined_applications.htm" target="_blank">docs.kuberdock.com</a> section "<b>Administration</b>" -> "<b>Predefined application</b>"
                </div>
            </div>
            <div class="buttons">
                <a href="#predefined-apps" class="cancel-app gray">Cancel</a>
                <button class="save-app blue <%= errorData ? 'anyway' : '' %>">
                    <%= isNew ? (errorData ? 'Add anyway' : 'Add') : (errorData ? 'Save anyway' : 'Save') %>
                </button>
            </div>
        </div>
    </div>
</div>

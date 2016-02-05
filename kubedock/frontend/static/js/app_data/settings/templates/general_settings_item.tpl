<label><%- label %></label>
<% if (options) { %>
    <select class="settings-item selectpicker" id="<%= name %>">
        <% _.each(options, function(option, i){ %>
        <option value="<%- i %>"><%- option %></option>
        <% }) %>
    </select>
<% } else { %>
    <input type="text" id="<%= name %>" class="settings-item"
           value="<%- typeof value !== 'undefined' ? value : '' %>"
           placeholder="<%- placeholder %>"/>
<% } %>
<div class="link-description"><%- description %></div>

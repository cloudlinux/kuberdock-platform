<label><%- label %></label>
<input type="text" id="<%= name %>" class="settings-item" value="<%- typeof value !== 'undefined' ? value : '' %>"
    placeholder="<%- placeholder %>"/>
<div class="link-description"><%- description %></div>

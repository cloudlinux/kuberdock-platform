<label><%- label %></label>
<% if (options) { %>
    <select id="<%= name %>" class="settings-item selectpicker">
        <% _.each(options, function(option, i){ %>
        <option value="<%- i %>"><%- typeof optionNames == 'object' ? optionNames[i] : option %></option>
        <% }) %>
    </select>
<% } else { %>
    <% if (name === 'dns_management_cpanel_dnsonly_token' || name === 'dns_management_cloudflare_certtoken') { %>
        <textarea id="<%= name %>" class="settings-item" type="text"
            placeholder="<%- placeholder %>"><%- typeof value !== 'undefined' ? value : '' %></textarea>
    <% } else { %>
        <input id="<%= name %>" class="settings-item"
            type="<%= name === 'billing_password' ? 'password' : 'text' %>"
            value="<%- typeof value !== 'undefined' ? value : '' %>"
            placeholder="<%- placeholder %>"/>
    <% } %>
<% } %>
<div class="link-description "><%- description %></div>

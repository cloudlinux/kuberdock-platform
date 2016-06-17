<div class="validation-error">
    Your template contains some errors.
    Are you sure you want to save it with those errors?
    <hr/>
    <% var forceArray = function(msg){ return _.isArray(msg) ? msg : [msg]; } %>
    <% if (data.common) { %>
        <p><%- jsyaml.safeDump(forceArray(data.common)) %></p>
    <% } if (data.customFields) { %>
        <h5>Invalid custom variables:</h5>
        <p><%- jsyaml.safeDump(forceArray(data.customFields)) %></p>
    <% } if (data.schema) { %>
        <h5>Invalid schema:</h5>
        <p><%- jsyaml.safeDump(forceArray(data.schema)) %></p>
    <% } if (data.appPackages) { %>
        <h5>Invalid packages:</h5>
        <p><%- jsyaml.safeDump(forceArray(data.appPackages)) %></p>
    <% } if (!(data.common || data.customFields || data.schema || data.appPackages)) { %>
        <h5>Invalid template:</h5>
        <p><%- jsyaml.safeDump(data) %></p>
    <% } %>
</div>

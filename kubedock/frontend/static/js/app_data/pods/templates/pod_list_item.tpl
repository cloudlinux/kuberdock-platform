<!-- table data row -->
<td class="checkboxes">
    <label class="custom">
        <% if (checked){ %>
        <input type="checkbox" class="checkbox" checked>
        <% } else { %>
        <input type="checkbox" class="checkbox">
        <% } %>
        <span></span>
    </label>
</td>
<td>
    <span class="poditem-page-btn" title="Edit <%- name %> pod" ><%- name %></span>
</td>
<td>
    <span><%- replicas || 1 %></span>
</td>
<td>
    <% if (status) { %>
        <span class="<%- status %>"><%- status %></span>
    <% } else { %>
        <span class="stopped">stopped</span>
    <% } %>
</td>
<td><%- _.find(backendData.kubeTypes, function(e) { return e.id == kube_type; }).name %></td>
<td><%- kubes %></td>
<td class="actions">
    <% if (status) { %>
        <% if (_.contains(['running', 'waiting', 'pending'], status)) { %>
            <span class="stop-btn" title="Stop <%- name %> pod">Stop</span>
        <% } else if (_.contains(['stopped', 'succeeded', 'failed'], status)) { %>
            <span class="start-btn" title="Start <%- name %> pod">Start</span>
        <% } %>
    <% } else { %>
        <span class="start-btn" title="Start <%- name %> pod">Start</span>
    <% } %>
</td>

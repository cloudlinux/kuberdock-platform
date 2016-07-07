<!-- table data row -->
<td class="checkboxes">
    <% if (status !== 'deleting') { %>
        <label class="custom">
            <% if (checked){ %>
            <input type="checkbox" class="checkbox" checked>
            <% } else { %>
            <input type="checkbox" class="checkbox">
            <% } %>
            <span></span>
        </label>
    <% } %>
</td>
<td>
    <% if (status !== 'deleting') { %>
        <a href="#pods/<%= id %>" title='"<%- name %>" pod page'><%- name %></a>
    <% } else {%>
        <span><%- name %></span>
    <% } %>
</td>
<!-- <td>
    <span><%- replicas || 1 %></span>
</td> -->
<td>
    <% if (status === 'deleting') { %>
        <span class="pending">pending</span>
    <% } else { %>
        <span class="<%- prettyStatus %>"><%- prettyStatus %></span>
    <% } %>
</td>
<td><%- kubeType.get('name') %></td>
<td><%- kubes %></td>
<td class="actions">
    <% if (ableTo('start')) { %> <span class="start-btn" data-toggle="tooltip" data-placement="top" title="Run <%- name %> pod"></span> <% } %>
    <% if (ableTo('redeploy')) { %> <span class="restart-btn" data-toggle="tooltip" data-placement="top" title="Restart <%- name %> pod"></span> <% } %>
    <% if (ableTo('stop')) { %> <span class="stop-btn" data-toggle="tooltip" data-placement="top" title="Stop <%- name %> pod"></span> <% } %>
    <% if (ableTo('pay-and-start')) { %> <span class="pay-and-start-btn" data-toggle="tooltip" data-placement="top" title="Pay then Run <%- name %> pod"></span> <% } %>
    <% if (ableTo('delete')) { %> <span class="terminate-btn" data-toggle="tooltip" data-placement="top" title="Delete <%- name %> pod"></span> <% } %>
</td>

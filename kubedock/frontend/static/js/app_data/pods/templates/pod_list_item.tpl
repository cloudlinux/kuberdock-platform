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
    <span class="<%= status !== 'deleting' ? 'poditem-page-btn' : '' %>" title="Edit <%- name %> pod" ><%- name %></span>
</td>
<!-- <td>
    <span><%- replicas || 1 %></span>
</td> -->
<td>
    <% if (status === 'deleting') { %>
        <span class="pending">pending</span>
    <% } else if (status) { %>
        <span class="<%- status %>"><%- status %></span>
    <% } else { %>
        <span class="stopped">stopped</span>
    <% } %>
</td>
<td><%- kubeType.get('name') %></td>
<td><%- kubes %></td>
<td class="actions">
    <% if (ableTo('start')) { %> <span class="start-btn" title="Run <%- name %> pod"></span> <% } %>
    <% if (ableTo('redeploy')) { %> <span class="restart-btn" title="Restart <%- name %> pod"></span> <% } %>
    <% if (ableTo('stop')) { %> <span class="stop-btn" title="Stop <%- name %> pod"></span> <% } %>
    <% if (ableTo('pay-and-start')) { %> <span class="pay-and-start-btn" title="Pay then Run <%- name %> pod"></span> <% } %>
    <% if (ableTo('delete')) { %> <span class="terminate-btn" title="Delete <%- name %> pod"></span> <% } %>
</td>

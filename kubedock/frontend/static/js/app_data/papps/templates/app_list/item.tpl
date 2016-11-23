<td class="col-sm-4 image">
    <a href="<%- urlPath + qualifier %>"><%- name %></a>
    <% if(icon) { %>
        <img src="<%- icon %>" alt="<%- name %> icon">
    <% } %>
</td>
<td class="col-sm-3"><%- modified %></td>
<td class="col-sm-2"><%= search_available ? 'Yes' : 'No' %></td>
<td class="actions col-sm-3">
    <a href="#predefined-apps/<%- id %>/edit" class="edit-item" data-toggle="tooltip" data-placement="top" title="Edit <%- name %> app"></a>
    <span class="delete-item" data-toggle="tooltip" data-placement="top" title="Delete <%- name %> app"></span>
    <span data-toggle="tooltip" data-placement="top" title="Copy <%- name %> link app" class="copy-link"></span>
</td>
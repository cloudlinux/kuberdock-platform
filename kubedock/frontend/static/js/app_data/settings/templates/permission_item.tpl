<td class="resource-name"><%- name %></td>
<% $.each(all_roles, function(id, role){ %>
    <td>
        <% _.each(roles[role.rolename], function(perm){ %>
        <label class="custom">
            <input type="checkbox" name="perm" data-pid="<%- perm.id %>" class="perm-toggle"
                   <% if(perm.allow) { %> checked<% } %> /><span></span>
            <%- perm.name %>
        </label><br/>
        <% }) %>
    </td>
<% }) %>

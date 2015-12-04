<td><button class="profileUser" title="Show <%- username %> profile"><%- username %></button></td>
<td><%- podsCount %></td>
<td><%- containersCount %></td>
<td><%- email ? email : 'No email' %></td>
<td><%- package  %></td>
<td><%- rolename  %></td>
<td><span class="<%- active ? 'active' : 'locked' %>"><%- active ? 'Active' : 'Locked' %></span></td>
<td class="actions">
    <% if (active) { %>
        <span class="blockUser" title="Lock user <%- username %>"></span>
    <% } else { %>
        <span class="activeteUser" title="Activate user <%- username %>"></span>
    <% } %>
    <span class="deleteUser" class="pull-right" title="Remove <%- username %>"></span>
</td>
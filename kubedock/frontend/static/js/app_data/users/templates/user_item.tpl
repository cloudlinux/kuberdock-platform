<td><span class="profileUser" title="Show <%- username %> profile"><%- username %></span></td>
<td><%- podsCount %></td>
<td><%- containersCount %></td>
<td><%- email ? email : 'No email' %></td>
<td><%- package  %></td>
<td><%- rolename  %></td>
<td>
<% if(!active) { %>
    <span class="locked">Locked</span>
<% } else if(suspended) { %>
    <span class="suspended">Suspended</span>
<% } else { %>
    <span class="active">Active</span>
<% } %>
</td>
<td class="actions">
    <% if (active) { %>
        <span class="blockUser" title="Lock user <%- username %>"></span>
    <% } else { %>
        <span class="activeteUser" title="Activate user <%- username %>"></span>
    <% } %>
    <% if (deletable){ %>
    <span class="deleteUser" class="pull-right" title="Remove <%- username %>"></span>
    <% } %>
</td>
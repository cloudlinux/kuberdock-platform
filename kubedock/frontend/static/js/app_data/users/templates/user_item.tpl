<td class="col-sm-2">
    <span class="profileUser" title="Show <%- username %> profile"><%- username %></span>
</td>
<td class="col-sm-1"><%- podsCount %></td>
<td class="col-sm-1"><%- containersCount %></td>
<td class="col-sm-2"><%- email ? email : 'No email' %></td>
<td class="col-sm-2"><%- package  %></td>
<td class="col-sm-2"><%- rolename  %></td>
<td class="col-sm-1">
    <% if(!active) { %>
        <span class="locked">Locked</span>
    <% } else if(suspended) { %>
        <span class="suspended">Suspended</span>
    <% } else { %>
        <span class="active">Active</span>
    <% } %>
</td>
<td class="actions col-sm-1">
    <% if (!active) { %>
        <span class="activeteUser" title="Activate user <%- username %>"></span>
    <% } else if (actions.lock){ %>
        <span class="blockUser" title="Lock user <%- username %>"></span>
    <% } %>
    <% if (actions.delete){ %>
        <span class="deleteUser" class="pull-right" title="Remove <%- username %>"></span>
    <% } %>
</td>

<td class="col-md-7"><%- ip %></td>
<% if (isAWS){ %>
<td class="col-md-2"><%- userName %></td>
<td class="col-md-3"><%- podName %></td>
<% } else { %>
<td class="col-md-2">
    <% if(status === 'busy') { %>
        <span class="<%- status %>">Pod "<%- podName %>" uses this IP</span>
    <% } else { %>
        <span class="<%- podName ? podName : status %>"><%- podName ? podName : status %></span>
    <% }%>
</td>
<td class="actions col-md-3">
    <% if(status === 'blocked') { %>
        <span class="unblock_ip" data-toggle="tooltip" data-placement="top" title="Unblock <%= ip %> IP"></span>
    <% } else if(status === 'free') { %>
        <span class="block_ip" data-toggle="tooltip" data-placement="top" title="Block <%= ip %> IP"></span>
    <% } %>
</td>
<% } %>
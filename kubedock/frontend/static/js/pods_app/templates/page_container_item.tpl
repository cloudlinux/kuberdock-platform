<td><label class="custom"><input type="checkbox"><span></span></label></td>
<td class="index"><%- index %></td>
<td><span class="container-page-btn"><%- image %></span></td>
<td>
    <% if (state == 'running' )  { %>
        <span class="<%- state %>"><%- state %></span>
        <span class="stop-btn" title="Stop <%- image %> container">Stop</span>
    <%} else if (state == 'terminated' ) { %>
        <span class="<%- state %>"><%- state %></span>
    <% } else { %>
        <span class="<%- state %>"><%- state %></span>
        <span class="start-btn" title="Stop <%- image %> container">Start</span>
    <% } %>
</td>
<td><span><%- kubes ? kubes : 'unknown' %></span></td>
<td>
    <span><%- startedAt ? startedAt : '' %></span>
    <!-- <span class="terminate-btn pull-right" title="Delete <%- image %> container">Delete</span> -->
</td>
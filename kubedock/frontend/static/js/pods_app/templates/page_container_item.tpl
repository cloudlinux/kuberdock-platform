<td class="checkboxes"><label class="custom"><input type="checkbox"><span></span></label></td>
<td class="index"><%- index %></td>
<td><span class="container-page-btn"><%- image %></span></td>
<td><span class="<%- state %>"><%- state %></span></td>
<td><span><%- kubes ? kubes : 'unknown' %></span></td>
<td>
    <span><%- startedAt ? startedAt : '' %></span>
    <% if (state == 'running' )  { %>
        <span class="stop-btn pull-right" title="Stop <%- image %> container">Stop</span>
    <%} else if (state == 'stopped' ) { %>
        <span class="start-btn pull-right" title="Stop <%- image %> container">Start</span>
    <% } %>
    <!-- <span class="terminate-btn pull-right" title="Delete <%- image %> container">Delete</span> -->
</td>
<td><label class="custom"><input type="checkbox"><span></span></label></td>
<td class="index"><%- index %></td>
<td>
    <a href="#poditem/<%- parentID %>/<%- name %>"><%- image %></a>
</td>
<!--
<td><span>10.10.10.10</span></td>
-->
<td>
    <% if (state == 'running' )  { %>
        <span class="<%- state %>"><%- state %></span>
        <span class="stop-btn" title="Stop <%- image %> container">Stop</span>
    <% } else { %>
        <span class="<%- state %>"><%- state %></span>
        <span class="start-btn" title="Stop <%- image %> container">Start</span>
    <% } %>
</td>
<td>
    <span><%- kubes ? kubes : 'unknown' %></span>
</td>
<td>
    <span><%- startedAt ? startedAt : '' %></span>
    <span class="terminate-btn pull-right" title="Delete <%- image %> container">Delete</span>
</td>
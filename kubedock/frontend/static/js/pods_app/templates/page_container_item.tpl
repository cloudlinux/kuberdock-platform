<td><label class="custom"><input type="checkbox"><span></span></label></td>
<td class="index"><%- index %></td>
<td>
    <a href="#poditem/<%- parentID %>/<%- name %>"><%- image %></a>
    <span class="terminate-btn">Delete</span>
</td>
<!--
<td><span>10.10.10.10</span></td>
-->
<td>
    <% if (state_repr == 'running' )  { %>
        <span class="<%- state_repr %>"><%- state_repr %></span>
        <span class="stop-btn">Stop</span>
    <% } else { %>
        <span class="<%- state_repr %>"><%- state_repr %></span>
        <span class="start-btn">Start</span>
    <% } %>
</td>
<td>
    <span><%- kubes ? kubes : 'unknown' %></span>
</td>
<td>
    <span><%- startedAt ? startedAt : '' %></span>
</td>
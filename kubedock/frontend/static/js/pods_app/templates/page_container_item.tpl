<!-- <td class="checkboxes"><label class="custom"><input type="checkbox"><span></span></label></td> -->
<td><span class="container-page-btn"><%- image %></span></td>
<td><span class="<%- state %>"><%- state %></span></td>
<td><span><%- kubes ? kubes : 'unknown' %></span></td>
<td><span><%- startedAt ? startedAt : '' %></span></td>
<td class="actions">
    <% if (state == 'running' )  { %>
        <% if (!updateIsAvailable) { %>
            <span class="check-for-update" title="Check <%- image %> for updates">Check for updates</span>
        <% } else { %>
            <span class="container-update" title="Update <%- image %> container">Update</span>
        <% } %>
    <% }%>
    <!--   <span class="stop-btn" title="Stop <%- image %> container">Stop</span>
           <span class="start-btn" title="Start <%- image %> container">Start</span>
           <span class="terminate-btn pull-right" title="Delete <%- image %> container">Delete</span> -->
</td>
<td class="checkboxes"><label class="custom"><input type="checkbox"><span></span></label></td>
<td><span class="container-page-btn"><%- image %></span></td>
<td><span class="<%- state %>"><%- state %></span></td>
<td><span><%- kubes ? kubes : 'unknown' %></span></td>
<td>
    <span><%- startedAt ? startedAt : '' %></span>
</td>
<td class="actions">
    <% if (state == 'running' )  { %>
        <span class="stop-btn" title="Stop <%- image %> container">Stop</span>
        <!-- AC-1279 -->
        <!--
        <% if (updateIsAvailable === undefined) { %>
            <span class="check-for-update-btn pull-right" title="Check <%- image %> for updates">Check for updates</span>
        <% } else if (updateIsAvailable === false) { %>
            <span class="check-for-update-btn pull-right" title="No updates found for <%- image %>">No updates found</span>
        <% } else if (updateIsAvailable === true) { %>
            <span class="update-btn pull-right" title="Update <%- image %> container">Update</span>
        <% } %>
         -->
    <%} else if (state == 'stopped' ) { %>
        <span class="start-btn" title="Start <%- image %> container">Start</span>
    <% } %>
    <!-- <span class="terminate-btn pull-right" title="Delete <%- image %> container">Delete</span> -->
</td>
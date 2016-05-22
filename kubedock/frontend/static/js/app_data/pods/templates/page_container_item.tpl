<!-- <td class="checkboxes"><label class="custom"><input type="checkbox"><span></span></label></td> -->
<td>
    <a href="#pods/<%- podID %>/container/<%- name %>" class="container-page-btn">
        <%- imagename %>
    </a>
    <% if (imagetag) { %>
    <span title="image tag" class="image-tag"><%- imagetag %></span>
    <% } %>
</td>
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
</td>

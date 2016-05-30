<!-- <td class="checkboxes"><label class="custom"><input type="checkbox"><span></span></label></td> -->
<td>
    <a href="#pods/<%- pod.id %>/container/<%- id %><%- !before && after ? '/general' : '' %>"
        class="container-page-btn">
        <%- imagename %>
    </a>
    <% if (imagetag) { %>
    <span title="image tag" class="image-tag"><%- imagetag %></span>
    <% } %>
</td>
<td>
    <% if (before) { %>
        <span class="<%- before.state %>"><%- before.state %></span>
    <% } %>
    <% if (before && !after) { %>
        <span class="diff-deleted" data-toggle="tooltip" data-placement="top"
            title="This container will be deleted after you apply changes.">
            -> deleted
        </span>
    <% } else if (!before && after) { %>
        <span class="diff-added" data-toggle="tooltip" data-placement="top"
            title="This container will be added after you apply changes.">new</span>
    <% } else if (changed) { %>
        <span class="diff-changed" data-toggle="tooltip" data-placement="top"
            title="This container will be modified after you apply changes.">
            -> modified
        </span>
        <% console.log(before, after); %>
    <% } %>
</td>
<td><span>
    <% if (before && after && before.kubes !== after.kubes) { %>
        <span class="diff-changed" data-toggle="tooltip" data-placement="top"
            title="The number of kubes will be changed after you apply changes.">
            <%- before.kubes %> -> <%- after.kubes %>
        </span>
    <% } else { %>
        <%- (before || after).kubes %>
    <% } %>
</span></td>
<td><span><%- startedAt %></span></td>
<td class="actions">
    <% if (before && before.state == 'running')  { %>
        <% if (!updateIsAvailable) { %>
            <span class="check-for-update" title="Check <%- before.image %> for updates">Check for updates</span>
        <% } else { %>
            <span class="container-update" title="Update <%- before.image %> container">Update</span>
        <% } %>
    <% }%>
</td>

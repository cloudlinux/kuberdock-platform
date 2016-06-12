<td><span class="containerPort">
    <% if (before && !after){ %>
        <span class="deleted" data-toggle="tooltip" data-placement="right" title="Deleted"></span>
    <% } else if (!before && after) { %>
        <span class="added" data-toggle="tooltip" data-placement="right" title="Added"></span>
    <% } else if (!_.isEqual(before, after)) { %>
        <span class="changed" data-toggle="tooltip" data-placement="right" title="Changed"></span>
    <% } %>
    <%- (before || after).containerPort %>
</span></td>
<td class="containerProtocol">
    <% if (before && after && before.protocol !== after.protocol){ %>
        <%- before.protocol %>
        <span class="diff-arrow" data-toggle="tooltip" data-placement="top"
        title="This container will be modified after you apply changes."></span>
        <%- after.protocol %>
    <% } else { %>
        <%- (before || after).protocol %>
    <% } %>
</td>
<td class="hostPort">
    <% if (before && after
           && (before.hostPort || before.containerPort) !== (after.hostPort || after.containerPort)){ %>
        <%- before.hostPort || before.containerPort %>
        <span class="diff-arrow" data-toggle="tooltip" data-placement="top"
        title="This container will be modified after you apply changes."></span>
        <%- after.hostPort || after.containerPort %>
    <% } else { %>
        <%- (before || after).hostPort || (before || after).containerPort %>
    <% } %>
</td>
<td>
    <% if (before && after && !before.isPublic !== !after.isPublic){ %>
        <%- before.isPublic ? 'yes' : 'no' %>
        <span class="diff-arrow" data-toggle="tooltip" data-placement="top"
        title="This container will be modified after you apply changes."></span>
        <%- after.isPublic ? 'yes' : 'no' %>
    <% } else { %>
        <%- (before || after).isPublic ? 'yes' : 'no' %>
    <% } %>
</td>

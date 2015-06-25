<!-- table data row -->
<td>
    <label class="custom"><input type="checkbox" class="checkbox"><span></span></label>
</td>
<td class="index"><%- index %></td>
<td>
    <a href="/#pods/<%- id %>" title="Edit <%- name %> pod" ><%- name %></a>
    <a href="/#pods/<%- id %>" title="Edit <%- name %> pod" class="editPod" >&nbsp;</a>
</td>
<td>
    <% if (replicationController){ %>
        <!-- <span class="reditable editable editable-click" style="display: inline-block;"><%- replicas %></span> -->
        <span><%- replicas %></span>
    <% }  else { %>
        none
    <% } %>
</td>
<td>
    <% if (status) { %>
        <% if ( status == 'running') { %>
            <span class="<%- status %>"><%- status %></span>
            <span class="stop-btn" title="Stop <%- name %> pod">Stop</span>
        <% } else if ( status == 'stopped' ) { %>
            <span class="<%- status %>"><%- status %></span>
            <span class="start-btn" title="Start <%- name %> pod">Start</span>
        <% } else if ( status == 'waiting' ) { %>
            <span class="<%- status %>"><%- status %></span>
            <span class="start-btn" title="Start <%- name %> pod">Start</span>
        <% } else { %>
            <span class="<%- status %>"><%- status %></span>
        <% } %>
    <% } else { %>
        <span class="stopped">stopped</span>
        <span class="start-btn" title="Start <%- name %> pod">Start</span>
    <% } %>
</td>
<td>
    <%- kubeTypes[kube_type].name %> (<%- kubes %>)
</td>
<td class="col-md-2">
    <a href="#pods/<%- pod_id %>" title='"<%= pod %>" pod page'><%- id %></a>
</td>
<td>
    <% if (pod){ %>
    <span class="busy" title="Used by pod &quot;<%- pod %>&quot;">"<%- pod %>"</span>
    <%} else {%>
    <span class="running"><%- pod %></span>
    <%}%>
</td>

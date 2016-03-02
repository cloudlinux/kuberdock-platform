<td class="col-md-2">
    <%- id %>
</td>
<td>
    <% if (pod){ %>
    <span class="busy" title="Used by pod &quot;<%- pod %>&quot;">"<%- pod %>"</span>
    <%} else {%>
    <span class="running"><%- pod %></span>
    <%}%>
    <!-- <span class="terminate-btn pull-right"></span> -->
</td>

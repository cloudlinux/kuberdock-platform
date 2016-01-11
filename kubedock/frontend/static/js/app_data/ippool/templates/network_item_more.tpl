<div data-id="<%- network %>" class="table-wrapper">
    <div class="network-name"><%- network %></div>
    <table class="table ip_table">
        <thead>
            <tr>
                <th class="col-xs-6">IP</th>
                <th class="col-xs-6">Status</th>
                <!-- <th>Assigned</th> -->
            </tr>
        </thead>
        <tbody class="networks-list-more">
            <% _.each(allocation, function(itm){ %>
                <tr>
                    <td>
                        <%- itm[0] %>
                    </td>
                    <td>
                        <% if(itm[2] == 'busy') { %>
                            <span class="<%- itm[2] %>">"<%- itm[1] %>"</span>
                            <span class="unbind_ip pull-right" data-ip="<%- itm[0] %>"></span>
                        <% } else { %>
                            <span class="<%- itm[1] ? itm[1] : itm[2] %>"><%- itm[1] ? itm[1] : itm[2] %></span>
                        <% }%>
                        <% if(itm[2] == 'blocked') { %>
                            <span class="unblock_ip pull-right" data-ip="<%- itm[0] %>"></span>
                        <% } else if(itm[2] == 'free') { %>
                            <span class="block_ip pull-right" data-ip="<%- itm[0] %>"></span>
                        <% } %>
                    </td>
                    <!-- <td>
                        yes or no
                    </td> -->
                </tr>
            <% }); %>
        </tbody>
    </table>
</div>
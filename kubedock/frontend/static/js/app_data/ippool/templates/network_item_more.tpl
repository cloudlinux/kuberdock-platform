<div data-id="<%- network %>" class="table-wrapper">
    <div class="network-name"><%- network %></div>
    <table class="table ip_table">
        <thead>
            <tr>
                <th class="col-xs-6">IP</th>
                <th class="col-xs-6">Status</th>
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
                            <span class="<%- itm[2] %>" title="1">"<%- itm[1] %>"</span>
                            <!-- <span class="unbind_ip pull-right" data-ip="<%- itm[0] %>"></span> -->
                        <% } else { %>
                            <span class="<%- itm[1] ? itm[1] : itm[2] %>"><%- itm[1] ? itm[1] : itm[2] %></span>
                        <% }%>
                        <% if(itm[2] == 'blocked') { %>
                            <span class="unblock_ip pull-right" data-ip="<%- itm[0] %>" title="Unblock <%- itm[0] %> IP"></span>
                        <% } else if(itm[2] == 'free') { %>
                            <span class="block_ip pull-right" data-ip="<%- itm[0] %>" title="Block <%- itm[0] %> IP"></span>
                        <% } %>
                    </td>
                </tr>
            <% }); %>
        </tbody>
    </table>
</div>
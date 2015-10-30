        <% switch (status) { case 'running': %>
        <% var ram = (resources.memory / (1024*1024*1024)).toFixed(2); %>
        <div class="row placeholders">
            <div class="col-xs-10 clearfix">
                <div class="col-xs-6 info no-padding">
                    <div>IP: <%- ip %></div>
                    <!--
                    <div>Kube capacity: 100</div>
                    <div>Used kubes: 50</div>
                    -->
                </div>
                <div class="col-xs-6 servers no-padding">
                    <div class="server-ico">CPU: <%- resources.cpu %> cores <!-- with 3GHz --></div>
                    <div class="server-ico">RAM: <%- ram %> GB <!--DDR3 - 2000 --></div>
                    <div class="server-ico"><!-- SDD: 0GB in Raid 0 --></div>
                </div>
            </div>
        </div>
        <% break; case 'pending': %>
        <div class="details">Node is in installation progress</div>
        <div class="reason">
            <p>Node installation log</p>
            <% _.each(install_log.split('\n'), function(line){ %>
                <p><%- line %></p>
            <% }) %>
        </div>
        <% break; case 'troubles': %>
        <div class="reason">
        <% _.each(reason.split('\n'), function(line){ %>
            <p><%- line %></p>
        <% }) %>
            <p>Node installation log</p>
            <% _.each(install_log.split('\n'), function(line){ %>
                <p><%- line %></p>
            <% }) %>
        </div>
        <% break; } %>
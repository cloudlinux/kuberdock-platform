<div id="item-controls" class="licenseTab">
    <div class="license-status-line">
        <span><b>License Status</b></span>
        <span class="icon <%= status %>"><%= status ? status : 'unknown'%></span>
        <span class="icon clock">Expiration date:
            <%= formatDate(expiration) %>
        </span>
        <span class="icon award">License type:
            <% if (type){ %>
                <%= type %>
            <% } else { %>
                unknown
            <% }%>
        </span>
    </div>
    <div class="row">
        <div class="col-xs-10 col-xs-offset-2">
            <div class="col-xs-6 info">
                <div class="editGroup">
                    <b>Instalattion ID:</b> <span class="edit-field peditable"> <%= installationID %></span>
                </div>
                <div><b>Platform:</b> <%= platform %></div>
                <div><b>Storage:</b> <%= storage %></div>
            </div>
            <div class="col-xs-6 servers">
                <div><b>KuberDock version:</b> <%= version.KuberDock %></div>
                <div><b>Kubernetes version:</b> <%= version.kubernetes %></div>
                <div><b>Docker version:</b> <%= version.docker %></div>
                <div><b>Support:</b> <a href="mailto:helpdesk@kuberdock.com">helpdesk@kuberdock.com</a></div>
            </div>
        </div>
    </div>
</div>
<div id="item-info">
    <table id="license-table" class="table">
        <thead>
            <tr>
                <th><b>License Usage</b></th>
                <th>Nodes</th>
                <th>Cores</th>
                <th>Memory (GB)</th>
                <th>Containers</th>
                <th>Users pods</th>
                <th>Predefined apps</th>
                <th>Persistent volume</th>
            </tr>
        </thead>
        <tbody>
            <tr>
                <td><b>License limits</b></td>
                <td><%= data.nodes[0] %></td>
                <td><%= data.cores[0] %></td>
                <td><%= data.memory[0] %></td>
                <td><%= data.containers[0] %></td>
                <td><%= data.pods[0] %></td>
                <td><%= data.apps[0] %></td>
                <td><%= data.persistentVolume[0] %></td>
            </tr>
            <tr class="atention">
                <td><b>Current state</b></td>
                <td><%= data.nodes[1] %></td>
                <td><%= data.cores[1] %></td>
                <td><%= data.memory[1] %></td>
                <td class="critical"><%= data.containers[1] %></td>
                <td><%= data.pods[1] %></td>
                <td><%= data.apps[1] %></td>
                <td><%= data.persistentVolume[1] %></td>
            </tr>
        </tbody>
    </table>
</div>

<div class="container" id="add-image" image_name_id="<%- image_name_id %>">
    <div class="col-md-3 sidebar no-padding">
        <ul class="nav nav-sidebar">
            <li role="presentation" class="success">Choose image</li>
            <li role="presentation" class="success">Set up image</li>
            <li role="presentation" class="success">Environment variables</li>
            <li role="presentation" class="active">Final</li>
        </ul>
    </div>
    <div id="details_content" class="col-sm-9 set-up-image no-padding">
        <div id="tab-content" class="clearfix complete">
            <div class="col-md-6 no-padding left">
                <div class="row policy">
                    <div class="col-xs-12">
                        <label>Restart policy</label>
                    </div>
                    <div class="col-md-<%= containers.length > 1 ? '11' : '12 no-padding-right' %>">
                        <select class="restart-policy selectpicker"<%= containers.length > 1 ? ' disabled' : '' %>>
                            <% _.each(restart_policies, function(value, key) {%>
                            <option value="<%- key %>"<%= key === restart_policy ? ' selected' : '' %>><%- value %></option>
                            <% }) %>
                        </select>
                    </div>
                    <div class="col-xs-12 edit-polycy-description">Type will apply for each container</div>
                    <% if (containers.length > 1){ %>
                    <div class="col-md-1 no-padding edit-policy"></div>
                    <% } %>
                </div>
                <div class="row kube-type-wrapper">
                    <% if (containers.length > 1){ %>
                    <label class="col-xs-8">Kube type</label>
                    <div class="col-xs-7">
                        <select class="kube_type selectpicker" id="extra-options" disabled>
                            <% _.each(kube_types, function(k_type){ %>
                            <option value="<%- k_type.id %>"<%= k_type.id === kube_type ? ' selected' : '' %>><%- k_type.name %></option>
                            <% }) %>
                        </select>
                    </div>
                    <div class="col-xs-1 no-padding edit-kube-type"></div>
                    <% } else { %>
                    <div class="col-xs-8">
                        <label>Kube type</label>
                        <select class="kube_type selectpicker" id="extra-options">
                            <% _.each(kube_types, function(kube_type){ %>
                            <option value="<%- kube_type.id %>"><%- kube_type.name %></option>
                            <% }) %>
                        </select>
                    </div>
                    <% } %>
                    <label>Kubes/replicas:</label>
                    <div class="col-xs-4 no-padding">
                        <select class="kube-quantity selectpicker">
                            <option value="1">1</option>
                            <option value="2">2</option>
                            <option value="3">3</option>
                            <option value="4">4</option>
                            <option value="5">5</option>
                            <option value="6">6</option>
                            <option value="7">7</option>
                            <option value="8">8</option>
                            <option value="9">9</option>
                            <option value="10">10</option>
                        </select>
                    </div>
                    <div class="col-xs-12 edit-kube-type-description">Type will apply for each container</div>
                </div>
            </div>
            <div class="col-md-5 col-xs-offset-1 servers">
                <div>CPU: <span id="total_cpu"><%- cpu_data %></span></div>
                <div>RAM: <span id="total_ram"><%- ram_data %></span></div>
                <div>HDD: <span id="hdd_data"><%- hdd_data %></span></div>
            </div>
            <div class="col-md-12 total-wrapper">
                <table>
                    <thead>
                       <tr>
                           <th class="col-xs-5 no-padding">Name</th>
                           <th class="col-xs-4 no-padding">Kybe QTY</th>
                           <th class="col-xs-2 no-padding">Price</th>
                           <th class="col-xs-1 no-padding"></th>
                       </tr>
                    </thead>
                    <tbody>
                        <% _.each(containers, function(c){ %>
                            <tr class="added-containers">
                                 <td id="<%- c.name %>"><b><%- c.image %></b></td>
                                 <td><%- c.kubes %></td>
                                 <td><%- container_price %> / <%- package.period %></td>
                                 <td>
                                     <button class="delete-item pull-right">&nbsp;</button>
                                     <!-- <button class="edit-item">&nbsp;</button> -->
                                 </td>
                            </tr>
                        <% }) %>
                        <% if (isPublic) { %>
                            <tr>
                                <td><b>IP Adress:</b></td>
                                <td></td>
                                <td><span id="ipaddress_price"><%- price_ip %> / <%- package.period %></td>
                                <td></td>
                            </tr>
                        <% } %>
                        <% if (isPerSorage) { %>
                            <tr>
                                <td><b>Persistent storage:</b></td>
                                <td></td>
                                <td colspan="2">
                                    <span id="pstorage_price"><%- price_pstorage %> per 1 MB / <%- package.period %></span>
                                </td>
                            </tr>
                        <% } %>
                        <tr>
                            <td class="total" colspan="3">
                                Total price: <span id="total_price"><%- total_price %> / <%- package.period %></span>
                            </td>
                        </tr>
                    </tbody>
                </table>
            </div>
        </div>
    </div>
    <div class="buttons pull-right">
        <button class="prev-step gray">Back</button>
        <button class="add-more blue">Add more container</button>
        <button class="save-container">Save</button>
    </div>
</div>
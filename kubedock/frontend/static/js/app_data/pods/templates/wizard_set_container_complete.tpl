<div class="container" id="add-image">
    <div class="col-md-3 sidebar no-padding">
        <ul class="nav nav-sidebar">
            <li role="presentation" class="success">Choose image</li>
            <li role="presentation" class="success">Set up image</li>
            <li role="presentation" class="success">Environment variables</li>
            <li role="presentation" class="active">Final setup</li>
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
                    <label class="col-xs-8">Kube Type</label>
                    <div class="col-xs-7">
                        <select class="kube_type selectpicker" id="extra-options" disabled>
                    <% } else { %>
                    <div class="col-xs-8">
                        <label>Kube Type</label>
                        <select class="kube_type selectpicker" id="extra-options">
                    <% } %>
                            <% kubeTypes.each(function(kubeType){ %>
                            <option value="<%- kubeType.id %>" <%= kubeType.disabled ? '' : 'disabled'%>>
                                <%- kubeType.formattedName %>
                            </option>
                            <% }) %>
                        </select>
                    </div>
                    <% if (containers.length > 1){ %>
                    <div class="col-xs-1 no-padding edit-kube-type"></div>
                    <% } %>
                    <label>Number of Kubes:</label>
                    <div class="col-xs-4 no-padding">
                        <select class="kube-quantity selectpicker">
                            <% for (var i = 1; i <= kubesLimit; i++) { %>
                                <option value="<%= i %>"><%= i %></option>
                            <% } %>
                        </select>
                    </div>
                    <div class="col-xs-12 edit-kube-type-description">Type will apply for each container</div>
                </div>
            </div>
            <div class="col-md-5 col-xs-offset-1 servers">
                <div>CPU: <span id="total_cpu"><%- limits.cpu %></span></div>
                <div>RAM: <span id="total_ram"><%- limits.ram %></span></div>
                <div>HDD: <span id="hdd_data"><%- limits.hdd %></span></div>
            </div>
            <div class="col-md-12 total-wrapper">
                <table>
                    <thead>
                       <tr>
                           <th class="col-xs-5 no-padding">Name</th>
                           <th class="col-xs-4 no-padding">Number of Kubes</th>
                           <th class="col-xs-2 no-padding">Price</th>
                           <th class="col-xs-1 no-padding"></th>
                       </tr>
                    </thead>
                    <tbody>
                        <% _.each(containers, function(c, i){ %>
                            <tr class="added-containers">
                                <td id="<%- c.name %>">
                                    <b><%- c.image %></b>
                                    <!-- <%- (c.name === last_edited) ? '*' : '' %> -->
                                </td>
                                <td><%- c.kubes %></td>
                                <td><%- containerPrices[i] %> / <%- period %></td>
                                <td>
                                    <button class="delete-item pull-right">&nbsp;</button>
                                    <button class="edit-item">&nbsp;</button>
                                </td>
                            </tr>
                        <% }) %>
                        <% if (isPublic) { %>
                            <tr>
                                <td><b>IP Address:</b></td>
                                <td></td>
                                <td><span id="ipaddress_price"><%- price_ip %> / <%- period %></td>
                                <td></td>
                            </tr>
                        <% } %>
                        <% if (isPerSorage) { %>
                            <tr>
                                <td><b>Persistent storage:</b></td>
                                <td></td>
                                <td colspan="2">
                                    <span id="pstorage_price"><%- price_pstorage %> per 1 GB / <%- period %></span>
                                </td>
                            </tr>
                        <% } %>
                        <tr>
                            <td class="total" colspan="3">
                                Total price: <span id="total_price"><%- totalPrice %> / <%- period %></span>
                            </td>
                        </tr>
                    </tbody>
                </table>
            </div>
        </div>
    </div>
    <div class="row">
        <div class="col-xs-12">
            <div class="col-xs-3"></div>
            <div class="buttons col-xs-9 no-padding">
                <button class="prev-step gray pull-left">Back</button>
                <button class="add-more blue pull-left">Add more containers</button>
                <button class="save-container blue pull-left">Save</button>
                <% if (hasBilling && !payg){ %>
                <button class="pay-and-run-container blue pull-right">Pay and Run</button>
                <% } %>
            </div>
        </div>
    </div>
</div>

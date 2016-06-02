<div class="container" id="add-image">
    <div class="col-md-3 col-sm-12 sidebar no-padding">
        <ul class="nav nav-sidebar">
            <li role="presentation" class="success">Choose image</li>
            <li role="presentation" class="success">Set up image</li>
            <li role="presentation" class="success">Environment variables</li>
            <li role="presentation" class="active">Final setup</li>
        </ul>
    </div>
    <div id="details_content" class="col-md-9 col-sm-12 set-up-image no-padding">
        <div id="tab-content" class="clearfix complete">
            <div class="col-md-6 no-padding left">
                <div class="row policy">
                    <div class="col-xs-12">
                        <label>Restart policy</label><!-- <span class="help" data-toggle="tooltip" data-placement="right" title="Defines if a container in the pod should be restarted, after it has been executed"></span> -->
                    </div>
                    <div class="col-xs-<%= containers.length > 1 ? '11' : '12 no-padding-right' %>">
                        <select class="restart-policy selectpicker"<%= containers.length > 1 ? ' disabled' : '' %>>
                            <% _.each(restart_policies, function(value, key) {%>
                            <option value="<%- key %>"<%= key === restart_policy ? ' selected' : '' %>><%- value %></option>
                            <% }) %>
                        </select>
                    </div>
                    <div class="col-xs-12 edit-polycy-description">Type will apply for each container</div>
                    <% if (containers.length > 1){ %>
                    <div class="col-xs-1 no-padding edit-policy" data-toggle="tooltip"
                        data-placement="left" title="Edit restart policy"></div>
                    <% } %>
                </div>
                <div class="row kube-type-wrapper">
                    <% if (containers.length > 1){ %>
                    <label class="col-xs-11">Kube Type</label>
                    <div class="col-xs-11">
                        <select class="kube_type selectpicker" id="extra-options" disabled>
                    <% } else { %>
                    <div class="col-xs-12 no-padding-right">
                        <label>Kube Type</label><!-- <span class="help" data-toggle="tooltip" data-placement="right" title="A particular set of resources predefined for each containe"></span> -->
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
                    <div class="col-xs-1 no-padding edit-kube-type" data-toggle="tooltip"
                    data-placement="left" title="Edit pod kube type"></div>
                    <% } %>
                    <div class="col-xs-12 edit-kube-type-description">Type will apply for each container</div>
                </div>
            </div>
            <div class="col-md-5 col-md-offset-1 col-sm-offset-0  servers">
                <div>CPU: <span id="total_cpu"><%- limits.cpu %></span></div>
                <div>RAM: <span id="total_ram"><%- limits.ram %></span></div>
                <div>HDD: <span id="hdd_data"><%- limits.hdd %></span></div>
            </div>
            <div class="col-md-12 total-wrapper">
                <table id="pod-payment-table">
                    <thead>
                       <tr>
                           <th class="col-xs-5 no-padding">Name</th>
                           <th class="col-xs-3 no-padding">Number of Kubes</th>
                           <th class="col-xs-3 no-padding">Price</th>
                           <th class="col-xs-1 no-padding"></th>
                       </tr>
                    </thead>
                    <tbody class="wizard-containers-list"></tbody>
                    <tbody>
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
                    </tbody>
                </table>
            </div>
            <div class="col-md-12 no-padding payment-summary">
                <% if (edited && diffTotalPrice > 0){ %>
                    <div class="diff-total pull-left">
                        <p>Additional costs: <span id="total_price"><%- formatPrice(diffTotalPrice) %> / <%- period %></span></p>
                    </div>
                    <div class="new-total pull-right">
                        New total price: <span id="total_price"><%- formatPrice(totalPrice) %> / <%- period %></span>
                    </div>
                <% } else { %>
                    <div class="total pull-right">
                        Total price: <span id="total_price"><%- formatPrice(totalPrice) %> / <%- period %></span>
                    </div>
                <% } %>
            </div>
            <div class="buttons col-md-12 no-padding text-right">
                <% if (edited){ %>
                    <button class="cancel-edit gray">Cancel</button>
                <% } %>
                <% if (wizardState.container){ %>
                    <button class="prev-step gray">Back</button>
                <% } %>
                <button class="add-more blue">Add more containers</button>
                <% if (!edited){ %>
                    <button class="save-container blue">Save</button>
                    <% if (hasBilling && !payg){ %>
                        <button class="pay-and-run-container blue">Pay and Run</button>
                    <% } %>
                <% } else { %>
                    <% if (hasBilling && !payg && diffTotalPrice > 0){ %>
                        <button class="pay-and-apply-changes blue">Pay and Apply changes *</button>
                        <button class="save-changes">Save for later</button>
                        <span class="edit-pod-note" style="clear: both; font-size: 12px">
                            * Pod will be restarted
                        </span>
                    <% } else { %>
                        <button class="save-changes blue">Save</button>
                    <% } %>
                <% } %>
            </div>
        </div>
    </div>
</div>

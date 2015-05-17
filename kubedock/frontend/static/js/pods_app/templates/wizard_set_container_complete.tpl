<div class="container" id="add-image">
    <div class="col-md-3 sidebar no-padding">
        <ul class="nav nav-sidebar">
            <li role="presentation" class="success">Choose image</li>
            <li role="presentation" class="success">Set up image</li>
            <li role="presentation" class="success">Environment variables</li>
            <li role="presentation" class="active">Final</li>
        </ul>
        <% if (containers.length > 1){ %>
        <div class="added-containers">
            <label>Added containers</label>
                <% _.each(containers, function(c){ %>
                    <div>
                        <span><%- c.image %></span>
                        <span>
                            <!-- <button class="edit-item">&nbsp;</button> -->
                            <button class="delete-item">&nbsp;</button>
                        </span>
                    </div>
                <% }) %>
        </div>
        <% } %>
    </div>
    <div id="details_content" class="col-sm-9 set-up-image no-padding">
        <div id="tab-content" class="clearfix complete">
            <div class="col-md-6 no-padding left">
                <div class="row policy">
                    <div class="col-xs-12">
                        <label>Restart policy</label>
                    </div>
                    <div class="col-md-6">
                        <select class="restart-policy">
                            <option selected="selected" value="always">Always</option>
                            <option value="never">Never</option>
                            <option value="onFailure">On Failure</option>
                        </select>
                    </div>
               <!--     <div class="col-md-3">
                        <select>
                            <option>Replication QTU</option>
                            <option>2</option>
                        </select>
                    </div> -->
                </div>
                <label>Type</label>
                <select class="kube_type" id="extra-options">
                    <option value="Available kube types" disabled selected>Available kube types</option>
                    <option value="0">Standard</option>
                </select>
                <label>Kubes per container:</label>
                <select class="kube-quantity">
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
            <div class="col-md-4 col-md-offset-2 right">
                <p class="clearfix">
                    <span class="pull-left"><b>Container(s):</b></span>
                    <span class="pull-right"><span id="containers_price"><%- container_price %></span></span>
                </p>
                <p class="clearfix">
                    <span class="pull-left"><b>IP Adress:</b></span>
                    <span class="pull-right"><span id="ipaddress_price"></span></span>
                </p>
                <p class="total"><b>Total price:</b> <span id="total_price"><%- total_price %></span></p>
            </div>
            <div class="col-xs-12 no-padding servers">
                <div>CPU: <span id="total_cpu"><%- cpu_data %></span></div>
                <div>RAM: <span id="total_ram"><%- ram_data %></span></div>
            </div>
        </div>
    </div>
    <div class="buttons pull-right">
        <button class="prev-step gray">Back</button>
        <button class="add-more blue">Add more container</button>
        <button class="save-container">Save</button>
    </div>
</div>
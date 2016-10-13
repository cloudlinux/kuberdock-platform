<div id="add-node" class="container">
    <div class="col-md-10 col-md-offset-2">
        <div class="clearfix information col-md-9">
            <label>Keep in mind please</label>
            <div>To successfully add a node you must first create a pair of keys with ssh-keygen and then place them to a node to be added with ssh-copy-id under user nginx</div>
        </div>
        <div class="form-field row">
            <div class="col-md-6 col-sm-12">
                <label for="node_address">Node name</label>
                <input class="find-input" type="text" placeholder="Enter node hostname here" id="node_address" name="node_address" value="<%= hostname %>"/>
            </div>
        </div>
        <% if (setupInfo.ZFS && !setupInfo.AWS) { %>
            <div class="form-field row">
                <div class="col-md-6 col-sm-12">
                    <label>Block devices for ZFS pool</label>
                    <% _.each(lsdevices, function(device, index){ %>
                        <div class="relative">
                            <input class="find-input block-device" type="text" placeholder="Enter block device name" value="<%= device %>" />
                            <%= index > 0 ? '<span class="remove">Remove item</span>' : '' %>
                        </div>
                    <% }); %>
                    <span class="add"><span>Add more</span></span>
                </div>
            </div>
        <% } %>
        <div class="form-field last row">
            <div class="col-md-6 col-sm-12">
                <label for="extra-options">Kube Type</label>
                <select class="kube_type selectpicker" id="extra-options">
                <% _.each(kubeTypes, function(kube){ %>
                    <option value="<%= kube.id %>"><%= kube.get('name') %></option>
                <% }) %>
                </select>
            </div>
        </div>
        <div class="row">
            <div class="col-lg-12 col-md-12 col-sm-12 col-xs-12">
                <div class="buttons pull-right">
                    <a href="#nodes" class="gray">Cancel </a>
                    <button id="node-add-btn" type="submit">Add</button>
                </div>
            </div>
        </div>
    </div>
</div>

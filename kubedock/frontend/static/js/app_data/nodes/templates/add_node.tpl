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
                    <select class="selectpicker block-device" multiple data-live-search="true"
                        <%= findLsdevice ? 'title="Select block device"' : 'disabled title="Enter node name to enable this field"' %> >
                        <% _.each(findLsdevice, function(device){ %>
                            <option
                                value="<%= device.DEVICE %>"
                                data-content="<span class='label label-kuberdock'>
                                    <span>
                                        <%= device.NAME %> (<%= Math.round(device.SIZE/1073741824) %>GB)
                                        <%= device.MOUNTPOINT ? ' - mounted to <b>' +  device.MOUNTPOINT + '</b>' : '' %>
                                    </span>
                                </span>"
                                <%= device.MOUNTPOINT ? 'disabled' : '' %>>
                            </option>
                        <% }) %>
                    </select>
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

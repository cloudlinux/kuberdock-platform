<div class="row">
    <div class="col-md-12">
        <div class="clearfix information">
            <label>Keep in mind please</label>
            <div>To successfully add a node you must first create a pair of keys with ssh-keygen and then place them to a node to be added with ssh-copy-id under user nginx</div>
        </div>
    </div>
</div>
<div class="form-field row">
    <div class="col-md-6 col-sm-12">
        <label for="node_address">Node name</label>
        <input class="find-input" type="text" placeholder="Enter node hostname here" id="node_address" name="node_address"/>
    </div>
</div>
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
            <button id="node-cancel-btn" type="submit">Cancel</button>
            <button id="node-add-btn" type="submit">Add</button>
        </div>
    </div>
</div>

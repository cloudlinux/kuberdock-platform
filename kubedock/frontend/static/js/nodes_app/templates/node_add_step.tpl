<div id="address-spinner"></div>
<div class="col-md-12 clearfix no-padding information">
    <label>Keep in mind please</label>
    <div>
        To successfully add a node you must first create a pair of keys with ssh-keygen and then place them to a node to be added with ssh-copy-id under user nginx
    </div>
</div>
<div class="form-field col-lg-6">
    <label for="node_address">Node name</label>
    <input class="find-input" type="text" placeholder="Enter node hostname here" id="node_address" name="node_address"/>
</div>
<div class="col-lg-12">
    <div class="col-lg-6">
        <label for="extra-options">Kube type</label>
        <select class="kube_type selectpicker" id="extra-options">
        <% _.each(kubeTypes, function(t){ %>
            <option value="<%= t.id %>"><%= t.name %></option>
        <% }) %>
        </select>
       </div>
    <div class="col-lg-6 right">
       <!-- <div class="info">
            <p></p>
        </div> -->
    </div>
</div>
<div class="buttons pull-right">
    <button id="node-cancel-btn" type="submit">Cancel</button>
    <button id="node-add-btn" type="submit">Add</button>
</div>
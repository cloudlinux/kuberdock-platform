<div class="row">
    <div id="network-controls" class="col-sm-10 col-sm-offset-2 no-padding">
        <div class="row">
            <div class="form-group col-sm-5 sol-xs-12">
                <label for="network">Subnet</label>
                <input type="text" name="network" class="masked-ip" id="network" placeholder="1.2.3.4/32">
            </div>
        </div>
        <div class="row">
            <div class="form-group col-sm-5 sol-xs-12">
                <label for="autoblock">Exclude IPs</label>
                <input type="text" name="autoblock" placeholder="eg 2,3,4 or 2-4 or both">
            </div>
        </div>
        <% if (!isFloating){ %>
            <div class="row">
                <div class="form-group col-sm-5 sol-xs-12">
                    <label for="hostname">Node hostname</label>
                    <select name="hostname" class="selectpicker hostname">
                        <% _.each(nodelist, function(node){ %>
                            <option value="<%= node %>"><%= node %></option>
                        <% }) %>
                    </select>
                </div>
            </div>
        <% } %>
    </div>
    <div class="buttons pull-right">
        <a href="#ippool" class="gray">Cancel</a>
        <button id="network-add-btn" class="blue <%= nodelist.length !== 0 ? '' : 'disabled' %>">Add</button>
    </div>
</div>

<div id="createNetwork">
    <div class="breadcrumbs-wrapper">
        <div class="container breadcrumbs" id="breadcrumbs">
            <ul class="breadcrumb">
                <li>
                    <div class="back">IP Pool</div>
                </li>
                <li class="active">Add subnet</li>
            </ul>
        </div>
    </div>
    <div id="network-contents" class="container">
        <div class="row">
            <div id="network-controls" class="col-sm-9 col-sm-offset-3 no-padding">
                <div class="form-group">
                    <label for="network">Subnet</label>
                    <input type="text" name="network" class="masked-ip" id="network" placeholder="1.2.3.4/32">
                </div>
                <div class="form-group">
                    <label for="network">Exclude IPs</label>
                    <input type="text" name="autoblock" class="" placeholder="eg 2,3,4 or 2-4 or both">
                </div>
            </div>
            <div class="buttons pull-right">
                <button class="gray back">Cancel</button>
                <button id="network-add-btn" type="submit">Add</button>
            </div>
        </div>
    </div>
</div>

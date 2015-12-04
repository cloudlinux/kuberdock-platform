<div id="settingsGeneralTab">
    <div class="content-body">
        <div class="col-md-12 no-padding">
            <div class="row">
              <div class="col-xs-5 col-xs-offset-1">
                <% if(backendData.administrator) { %>
                    <div class="link-wrapper">
                        <label>Link to billing system scrypt</label>
                        <input type="text" name="billingAppsLink" id="billingAppsLink"
                            value="<%- typeof value !== 'undefined' ? value : '' %>"
                            placeholder="http://whmcs.com/script.php"/>
                        <div class="link-description">Link to predefined application request processing script</div>
                    </div>
                <% } %>
              </div>
              <div class="col-xs-5 image"></div>
            </div>
        </div>
    </div>
    <div class="buttons pull-right">
        <button id="user-add-btn" class="" type="submit">Save</button>
    </div>
</div>
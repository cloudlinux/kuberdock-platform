<div class="row">
    <div id="domain-controls" class="col-sm-10 col-sm-offset-2 no-padding">
        <div class="status-line clearfix">
            <a class="hidden-sm hidden-xs pull-right image-link" href="http://docs.kuberdock.com" target="blank">
                <span>Learn more about this</span>
            </a>
        </div>
        <div class="row">
            <div class="form-group col-sm-5 sol-xs-12">
                <label for="domain">Domain name</label>
                <input type="text" name="domain" id="domain" value="<%= name ? name : '' %>" placeholder="Enter name" <%= isNew ? '' : 'disabled' %>>
            </div>
        </div>
        <div class="row">
            <div class="form-group col-sm-9 sol-xs-12">
                <label class="radio-inline custom">
                    <input type="radio" name="custom-certificate" value="false"
                    <%- !certificate ?'checked':''%>><span></span><i>Automatically generated</i>
                </label>
                <label class="radio-inline custom">
                    <input type="radio" name="custom-certificate" value="true"
                    <%- certificate ?'checked':'' %>><span></span><i>Custom</i>
                </label>
            </div>
        </div>
        <% if (certificate) { %>
            <div class="row">
                <div class="form-group col-sm-9 sol-xs-12">
                    <label for="certificate">SSL Certificate</label>
                    <textarea name="certificate" id="certificate" placeholder="Paste a certificate to secure connection"><%= certificate ? certificate.cert : '' %></textarea>
                </div>
            </div>
            <div class="row">
                <div class="form-group col-sm-9 sol-xs-12">
                    <label for="key">Private Key for SSL Ceriticate</label>
                    <textarea name="key" id="key" placeholder="Paste a private key for your certificate"><%= certificate ? certificate.key : '' %></textarea>
                </div>
            </div>
        <% } %>
    </div>
    <div class="buttons pull-right">
        <a href="#domains" class="gray">Cancel</a>
        <button id="domain-add-btn" class="blue"><%= isNew ? 'Add' : 'Save' %></button>
    </div>
</div>

<div class="col-xs-12 no-padding clearfix">
    <div class="col-md-2 col-sm-2 hidden-xs container-image<%- icon ? '':' empty' %>">
    <% if(icon) { %>
        <img src="<%- icon %>" alt="<%- name %> icon"
             class="pa-img img-responsive">
    <% } %>
    </div>
    <div class="col-md-8 col-sm-8 col-xs-8">
        <div class="item-header-title"><%= name || 'nameless' %></div>
        <div class="item-body-info"><%= description() || 'No description'
            %></div>
    </div>
    <div class="col-md-2 col-sm-2 col-xs-4">
        <!--button class="like"><span></span></button-->
        <button class="add-item">Select</button>
    </div>
</div>
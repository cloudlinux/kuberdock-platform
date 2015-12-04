<div class="breadcrumbs-wrapper">
    <div class="container breadcrumbs" id="breadcrumbs">
        <ul class="breadcrumb">
            <li>
                <div id="users-page">Users</div>
            </li>
            <li>
                <% if( typeof username == "undefined" ) { %>
                    Create user
                <% } else { %>
                    <%- username %>
                <% } %>
            </li>
            <li class="active">Login history</li>
        </ul>
        <div class="control-group">
            <button id="edit_user">Edit user</button>
            <button id="login_this_user">Login as this user</button>
            <button id="delete_user">Delete</button>
        </div>
    </div>
</div>
<div class="container">
    <div class="row">
        <div class="col-xs-12 col-sm-12 col-md-2 sidebar">
            <ul class="nav nav-sidebar list-unstyled" role="tablist">
                <li class="general generalTab">General</li>
                <li class="logHistory active">Login history</li>
            </ul>
        </div>
        <div id="details_content" class="col-xs-12 col-sm-12 col-md-10">
            <div class="row placeholders">
                <div class="tab-content col-xs-12 no-padding-right">
                    <div class="tab-pane fade in active" id="userLogsTab">
                        <div class="col-xs-12 no-padding-right">
                            <table id="user-profile-logs-table" class="table">
                                <thead>
                                    <tr>
                                        <th class="col-md-4">Login</th>
                                        <th class="col-md-2">Duration</th>
                                        <th class="col-md-4">Logout</th>
                                        <th class="col-md-2">IP</th>
                                    </tr>
                                </thead>
                                <tbody></tbody>
                            </table>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
</div>
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
            <li class="active">General</li>
        </ul>
        <div class="control-group">
            <button id="edit_user">Edit user</button>
            <button id="login_this_user">Login as this user</button>
            <% if (actions.delete){ %>
                <button id="delete_user">Delete</button>
            <% } %>
        </div>
    </div>
</div>
<div class="container">
    <div class="row">
        <div class="col-sm-12 col-md-2 sidebar">
            <ul class="nav nav-sidebar list-unstyled" role="tablist">
                <li class="general active">General</li>
                <li class="logHistory">Login history</li>
            </ul>
        </div>
        <div id="details_content" class="col-sm-12 col-md-10">
            <div class="row placeholders">
                <div class="tab-content col-xs-12">
                    <div class="tab-pane fade in active" id="userGeneralTab">
                        <% if (username || join_date || last_login || last_activity || package) { %>
                            <div class="col-xs-12 col-sm-12 col-md-6 col-lg-6">
                                <div class="col-xs-4 user"></div>
                                <div class="col-xs-8">
                                    <% if (username) { %> <div>Username: <%- username %></div><% } %>
                                    <% if (join_date) { %> <div>Registered: <%- join_date %></div><% } %>
                                    <% if (last_login) { %> <div>Last login: <%- last_login %></div><% } %>
                                    <% if (last_activity) { %> <div>Last activity: <%- last_activity %></div><% } %>
                                    <% if (package) { %> <div>Package: <%- package %></div><% } %>
                                </div>
                            </div>
                        <% } %>
                        <% if (first_name || last_name || middle_initials || email) { %>
                            <div class="col-xs-12 col-sm-12 col-md-6 col-lg-6">
                                <div class="col-xs-4 info"></div>
                                <div class="col-xs-8">
                                    <% if (first_name) { %> <div>First name: <%- first_name %></div><% } %>
                                    <% if (last_name) { %> <div>Last name: <%- last_name %></div><% } %>
                                    <% if (middle_initials) { %><div>Middle initials: <%- middle_initials %></div><% } %>
                                    <% if (email) { %> <div>E-mail: <a href="mailto:<%- email %>"><%- email %></a></div><% } %>
                                </div>
                            </div>
                        <% } %>
                        <div class="col-xs-12 no-padding">
                            <table id="user-profile-general-table" class="table">
                                <thead>
                                    <tr>
                                        <th class="col-md-6">Pods</th>
                                        <th class="col-md-3">Kube Type</th>
                                        <th class="col-md-3">Number of Kubes</th>
                                    </tr>
                                </thead>
                                <tbody>
                                <% if (pods.length != 0) { %>
                                    <% _.each(pods, function(pod){ %>
                                        <tr>
                                            <%
                                                var podConfig = JSON.parse(pod.config),
                                                    kubeType = kubeTypes.get(podConfig.kube_type);
                                            %>
                                            <td><%- pod.name %></td>
                                            <td><%- kubeType ? kubeType.get('name') : '' %></td>
                                            <td><%- pod.kubes %></td>
                                        </tr>
                                    <% }) %>
                                <% } else { %>
                                    <tr>
                                        <td colspan="3" class="text-center disabled-color-text">This user doesn't have any pods</td>
                                    </tr>
                                <% } %>
                                </tbody>
                            </table>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
</div>

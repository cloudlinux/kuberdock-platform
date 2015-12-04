<div class="breadcrumbs-wrapper">
    <div class="container breadcrumbs" id="breadcrumbs">
        <ul class="breadcrumb">
            <li>
                <div id="users-page">Users</div>
            </li>
            <% if (typeof username !== "undefined") { %>
                <li><%= username %></li>
                <li class="active">Edit user</li>
            <% } else { %>
                <li class="active">Create User</li>
            <% } %>
        </ul>
    </div>
</div>
<div class="container">
    <div id="user-contents">
        <div class="row">
            <div class="col-md-3"></div>
            <div id="user-controls" class="col-md-9">
                <% if (typeof username == "undefined") { %>
                    <div class="form-group">
                        <label for="username">Username</label>
                        <input type="text" name="username" class="form-control" id="username">
                    </div>
                <% } %>
                <div class="form-group">
                    <label for="firstname">First name</label>
                    <input type="text" name="firstname" class="form-control" id="firstname">
                </div>
                <div class="form-group">
                    <label for="lastname">Last name</label>
                    <input type="text" name="lastname" class="form-control" id="lastname">
                </div>
                <div class="form-group">
                    <label for="middle_initials">Middle initials</label>
                    <input type="text" name="middle_initials" class="form-control" id="middle_initials">
                </div>
                <div class="form-group">
                    <label for="password">Password</label>
                    <input type="password" class="form-control" id="password" name="password" placeholder="Password">
                    <input type="password" class="form-control" id="password-again" name="password-again" placeholder="Repeat password">
                </div>
                <div class="form-group">
                    <label for="email">E-mail</label>
                    <input type="email" name="email" class="form-control" id="email">
                </div>
                <div class="form-group">
                    <label for="timezone">Timezone</label>
                    <input type="text" name="timezone" class="form-control" id="timezone">
                </div>
                <div class="form-group">
                    <label for="role-select">Role</label>
                    <select id="role-select" name="role-select" class="selectpicker">
                    <% _.each(roles, function(role){ %>
                        <% if (role === defaultRole){ %>
                            <option selected="selected"><%= role %></option>
                        <% } else { %>
                            <option><%= role %></option>
                        <% } %>
                    <% }) %>
                    </select>
                </div>
                <div class="form-group">
                    <label for="package-select">Package</label>
                    <select id="package-select" name="package-select" class="selectpicker">
                    <% _.each(packages, function(p){ %>
                        <option><%= p.name %></option>
                    <% }) %>
                    </select>
                </div>
                <div class="form-group">
                    <label for="status-select">Status</label>
                    <select id="status-select" name="status-select" class="selectpicker">
                        <option selected="selected" value="1">Active</option>
                        <option value="0">Locked</option>
                    </select>
                </div>
            </div>
            <div class="buttons pull-right">
                <button id="user-cancel-btn" type="submit">Cancel</button>
                <% if (typeof username !== "undefined") { %>
                    <button id="user-add-btn" class="hideButton" type="submit">Create</button>
                <% } else { %>
                    <button id="user-add-btn" type="submit">Create</button>
                <% } %>

            </div>
        </div>
    </div>
</div>
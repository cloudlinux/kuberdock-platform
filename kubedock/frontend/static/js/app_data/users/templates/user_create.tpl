<div class="breadcrumbs-wrapper">
    <div class="container breadcrumbs" id="breadcrumbs">
        <ul class="breadcrumb">
            <li>
                <div id="users-page">Users</div>
            </li>
            <% if (!isNew) { %>
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
                <% if (isNew) { %>
                    <div class="form-group">
                        <label for="username">Username</label>
                        <input type="text" name="username" class="form-control" id="username">
                    </div>
                <% } %>
                <div class="form-group">
                    <label for="firstname">First name</label>
                    <input type="text" name="firstname" class="form-control" id="firstname" value="<%- first_name %>">
                </div>
                <div class="form-group">
                    <label for="lastname">Last name</label>
                    <input type="text" name="lastname" class="form-control" id="lastname" value="<%- last_name %>">
                </div>
                <div class="form-group">
                    <label for="middle_initials">Middle initials</label>
                    <input type="text" name="middle_initials" class="form-control" id="middle_initials" value="<%- middle_initials %>">
                </div>
                <div class="form-group">
                    <label for="password">Password</label>
                    <input type="password" class="form-control" id="password" name="password" placeholder="Password">
                    <input type="password" class="form-control" id="password-again" name="password-again" placeholder="Repeat password">
                </div>
                <div class="form-group">
                    <label for="email">E-mail</label>
                    <input type="email" name="email" class="form-control" id="email" value="<%- email %>">
                </div>
                <div class="form-group">
                    <label for="timezone">Timezone</label>
                    <select id="timezone" class="selectpicker" data-live-search="true" placeholder="Select timezone">
                        <% _.each(timezones, function(t){ %>
                            <option value="<%= t %>" <%= timezone === t ? 'selected' : '' %>><%= t %></option>
                        <% }) %>
                    </select>
                </div>
                <div class="form-group">
                    <label for="role-select">Role</label>
                    <select id="role-select" name="role-select" class="selectpicker">
                    <% _.each(roles, function(role){ %>
                        <option <%= rolename === role ? 'selected' : '' %>><%= role %></option>
                    <% }) %>
                    </select>
                </div>
                <div class="form-group">
                    <label for="package-select">Package</label>
                    <select id="package-select" name="package-select" class="selectpicker">
                    <% packages.each(function(p){ %>
                        <option <%= (typeof package != 'undefined'
                                     && package === p.name) ? 'selected' : '' %>>
                            <%= p.get('name') %>
                        </option>
                    <% }) %>
                    </select>
                </div>
                <div class="form-group clearfix">
                    <div>
                        <label for="status-select" class="pull-left">Status</label>
                        <label class="custom pull-right">
                            <input type="checkbox" id="suspended" name="suspended"
                                   class="checkbox" <%= suspended ? 'checked' : '' %>>
                            <span></span>
                        </label>
                        <label class="checkbox-label pull-right" for="suspended">Suspended</label>
                    </div>
                    <select id="status-select" name="status-select" class="selectpicker">
                        <option value="1" <%= active ? 'selected' : '' %>>Active</option>
                        <option value="0" <%= active ? '' : 'selected' %>>Locked</option>
                    </select>
                </div>
                <div class="form-group">

                </div>
            </div>
            <div class="buttons pull-right">
                <button id="user-cancel-btn" type="submit">Cancel</button>
                <% if (isNew) { %>
                    <button id="user-add-btn" type="submit">Create</button>
                <% } else { %>
                    <button id="user-add-btn" class="hideButton" type="submit">Save</button>
                <% } %>

            </div>
        </div>
    </div>
</div>

<% if (user.isImpersonated()){ %>
<div class="login-view-mode-wrapper">
    <span class="glass pull-left">User View Mode</span>
    <span>Logged in as user: <b><%= user.get('username') %></b></span>
    <a href="/logoutA">Exit Mode</a>
</div>
<% } %>
<div class="container">
    <div class="navbar" role="navigation">
        <div class="container-fluid">
            <div class="navbar-header">
                <button type="button" class="navbar-toggle" data-toggle="collapse" data-target=".navbar-collapse">
                    <span class="sr-only">Toggle navigation</span>
                    <span class="icon-bar"></span>
                    <span class="icon-bar"></span>
                    <span class="icon-bar"></span>
                </button>
                <a class="navbar-brand" href="/">
                    <img alt="CloudLinux Kuberdock" class="logo" src="/static/img/logo.png">
                </a>
            </div>
            <div class="navbar-collapse collapse">
                <ul id="menu-items" class="nav navbar-nav"></ul>
                <ul class="nav navbar-nav navbar-right">
                    <li class="dropdown profile-menu">
                        <a href="#" class="dropdown-toggle" data-toggle="dropdown"><%- user.get('username') %><b class="caret"></b></a>
                        <ul class="dropdown-menu">
                            <% if (user.get('rolename') !== 'Admin'){ %>
                                <li><a class="routable" href="#settings">Settings</a></li>
                            <% } %>
                            <% if (!user.isImpersonated()){ %>
                                <li><a href="/logout">Logout </a></li>
                            <% } %>
                        </ul>
                    </li>
                </ul>
            </div>
        </div>
    </div>
</div>

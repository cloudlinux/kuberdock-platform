

<div class="hidden-xs col-sm-2 isv-block text-center settings-ethernet"></div>
<div class="col-xs-12 col-sm-10 isv-block">
    <p>SSH link:
        <% if (link) { %>
            <span class="ssh-link"><%- link %></span>
            <span class="copy-ssh-link" data-toggle="tooltip" data-placement="top" data-original-title="Copy ssh link to clipboard"></span>
        <% } else { %>
            SSH access credentials are outdated.
        <% } %>
    </p>
    <p>SSH password:
        <% if (auth) { %>
            ******
            <span class="copy-ssh-password" data-toggle="tooltip" data-placement="top" data-original-title="Copy ssh password to clipboard"></span>
        <% } else { %>
            SSH access credentials are outdated.
        <% } %>
        <span class="reset-ssh-password" data-toggle="tooltip" data-placement="top" data-original-title="Reset ssh password"></span>
    </p>
</div>

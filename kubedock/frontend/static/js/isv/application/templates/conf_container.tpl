<div class="col-sm-12 col-md-6">
    <div>SSH link:
        <% if (link) { %>
            <span class="ssh-link"><%- link %></span>
            <span class="copy-ssh-link">[copy]</span>
        <% } else { %>
            SSH access credentials are outdated.
        <% } %>
    </div>
    <div>SSH password:
        <% if (auth) { %>
            ******
            <span class="copy-ssh-password">[copy]</span>
        <% } else { %>
            SSH access credentials are outdated.
        <% } %>
        <span class="reset-ssh-password">[update]</span>
    </div>
</div>

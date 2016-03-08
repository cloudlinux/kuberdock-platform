<td class="col-md-2">
    <a class="container-page-btn" href="#pods/poditem/<%- pod.id %>/<%- name %>"><%- imagename %></a>
    <% if (imagetag) { %>
        <span title="image tag" class="image-tag"><%- imagetag %></span>
    <% } %>
</td>
<td class="col-md-2"><span class="upgrade-price"><%- upgradePrice %></span></td>
<td class="inline-fix">
    <span class="upgrade-kubes-less">-</span>
    <input class="upgrade-kubes" type="number" min="1" max="<%- kubesLimit %>" value="<%- kubes %>"/>
    <span class="upgrade-kubes-more">+</span>
</td>
<td class="col-md-2">CPU: <%- limits.cpu %></td>
<td class="col-md-2">RAM: <%- limits.ram %></td>
<td class="col-md-2">HDD: <%- limits.hdd %></td>

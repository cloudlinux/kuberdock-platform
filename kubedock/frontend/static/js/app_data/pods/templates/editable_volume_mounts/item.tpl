<td>
    <span class="ieditable mountPath"><%- mountPath %></span>
</td>
<td>
    <label class="custom">
        <input class="persistent" value="0" <%= isPersistent ? '' : 'checked' %>
               type="radio" name="persistent-<%- name %>">
        <span></span><i>Container<sup>**</sup></i>
    </label>
    <label class="custom">
        <input class="persistent" value="1" <%= isPersistent ? 'checked' : '' %>
               type="radio" name="persistent-<%- name %>">
        <span></span><i>Persistent</i>
    </label>
</td>
<% if (isPersistent){ %>
    <td>
        <select id="pd-<%- name %>" class="selectpicker pd-select">
            <% if (persistentDrives){ persistentDrives.each(function(pd){ %>
                <% var self = persistentDisk === pd,
                       conflicts = pd.conflictsWith(pod, /*ignored=*/persistentDisk) %>
                <option value="<%- pd.get('name') %>" <%- !self && pd.get('in_use') ? 'disabled' : '' %>>
                    <%- pd.get('name') %> <%= self && pd.isNewPD          ? '(new)'
                                              : !self && pd.get('in_use') ? '(busy)'
                                                  : conflicts.length      ? '(conflict)'
                                                  : '' %>
                </option>
            <% })} %>
        </select>
    </td>
    <td>
        <div class="input-wrap">
            <input type="number" class="pd-size" placeholder="Size"
                   value="<%- persistentDisk ? persistentDisk.get('size') : '' %>"
                   max="<%- pdSizeLimit %>" min="1"
                   <%- persistentDisk && persistentDisk.isNewPD ? '' : 'disabled' %>>
        </div>
    </td>
<% } else { %>
    <td></td>
    <td></td>
<% } %>
<td><span class="remove-volume"></span></td>

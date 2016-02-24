
<td class="containerPort">
    <span class="ieditable"><%- containerPort %></span>
</td>
<td class="containerProtocol"><span class="iseditable"><%- protocol %></span></td>
<td class="hostPort"><span class="ieditable"><%- hostPort ? hostPort : containerPort %></span></td>
<td class="public">
    <label class="custom">
        <input class="public" type="checkbox" <%- isPublic ? 'checked' : '' %>/>
        <span></span>
    </label>
</td>
<td class="actions">
    <span class="remove-port"></span>
</td>

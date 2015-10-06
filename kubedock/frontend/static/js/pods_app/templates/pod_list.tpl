<div class="col-md-12 no-padding">
    <div class="podsControl" style="display:<%- checked ? 'block' : 'none' %>">
        <span class="count"><%- checked %><%- checked ? ' Items' : ' Item' %></span>
        <span class="runPods">Run</span>
        <span class="stopPods">Stop</span>
        <span class="removePods">Delete</span>
    </div>
    <table id="podlist-table" class="table">
        <thead>
            <tr>
                <th class="checkboxes">
                    <label class="custom">
                        <% if (allChecked){ %>
                        <input type="checkbox" checked>
                        <% } else { %>
                        <input type="checkbox">
                        <% } %>
                        <span></span>
                    </label>
                </th>
                <th class="name">Pod name<b class="caret"></th>
                <th class="replicas">Replicated<b class="caret"></b></th>
                <th class="status">Status<b class="caret"></b></th>
                <th>Kube type</th>
                <th>Kubes quantity</th>
                <th>Actions</th>
            </tr>
        </thead>
        <tbody>
            <% if(collectionLenght == 0){ %>
                <tr>
                    <td colspan="7" class="text-center disabled-color-text">You don't have any pods</td>
                </tr>
            <% } %>
        </tbody>
    </table>
</div>

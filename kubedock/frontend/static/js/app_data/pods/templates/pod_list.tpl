<div class="col-md-12 no-padding">
    <div class="podsControl" style="display:<%- checked.length ? 'block' : 'none' %>">
        <span class="count"><%- checked.length %><%- (checked.length > 1) ? ' Items' : ' Item' %></span>
        <% if (_.any(_.invoke(checked, 'ableTo', 'start'))) { %>
            <span class="runPods" title="Run">Run</span>
        <% } %>
        <% if (_.any(_.invoke(checked, 'ableTo', 'redeploy'))) { %>
            <span class="restartPods" title="Restart">Restart</span>
        <% } %>
        <% if (_.any(_.invoke(checked, 'ableTo', 'stop'))) { %>
            <span class="stopPods" title="Stop">Stop</span>
        <% } %>
        <% if (_.any(_.invoke(checked, 'ableTo', 'delete'))) { %>
            <span class="removePods" title="Delete">Delete</span>
        <% } %>
    </div>
    <table id="podlist-table" class="table">
        <thead class="<%- checked.length ? 'pods-checked' : '' %>">
            <tr>
                <th class="checkboxes">
                    <label class="custom">
                        <input type="checkbox" <%- allChecked? 'checked' : '' %> <%- isCollection %> >
                        <span></span>
                    </label>
                </th>
                <th class="name">Pod name<b class="caret <%= sortingType.name == -1 ? 'rotate' : '' %>"></th>
                <!-- <th class="replicas">Replicated<b class="caret <%= sortingType.replicas == -1 ? 'rotate' : '' %>"></b></th> -->
                <th class="status">Status<b class="caret <%= sortingType.status == -1 ? 'rotate' : '' %>"></b></th>
                <th class="kube_type">Kube Type<b class="caret <%= sortingType.kube_type == -1 ? 'rotate' : '' %>"></th>
                <th class="kubes">Number of Kubes<b class="caret <%= sortingType.kubes == -1 ? 'rotate' : '' %>"></th>
                <th>Actions</th>
            </tr>
        </thead>
        <tbody></tbody>
    </table>
</div>

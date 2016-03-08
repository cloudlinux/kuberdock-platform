<table class="table" id="imagelist-table">
<thead>
    <tr class="main-table-head">
        <th>Container name</th>
        <th>Upgrade Price</th>
        <th>Kubes</th>
        <th colspan="3">Resources</th>
    </tr>
</thead>
<tbody></tbody>
</table>
<div class="col-md-12 upgrade-summary no-padding">
    <div class="upgrade-total-price pull-left">
        <p>Total pod price: <%- totalPrice %> / <%- period %></p>
        <small>Begin from <%- new Date().toLocaleDateString() %></small>
    </div>
    <div class="upgrade-diff-price pull-right">
        Upgrade price: <%- upgradePrice %>
    </div>
</div>
<div class="buttons col-md-12 text-right no-padding">
    <button class="gray cancel-upgrade">Cancel</button>
    <button class="apply-upgrade">Upgrade now</button>
</div>